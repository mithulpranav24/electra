import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest


class _Query:
    """Minimal chainable query double (see test_waitlist.py / test_sessions.py
    for the same pattern): any non-terminal attribute access returns self,
    the configured terminal method returns the configured value."""

    def __init__(self, terminal, value):
        self._terminal = terminal
        self._value = value

    def __getattr__(self, name):
        if name == self._terminal:
            return lambda *a, **k: self._value
        return lambda *a, **k: self


def _port(status, port_id=None, station_id=None, connector_type="CCS2", is_pending_maintenance=False):
    from app.models.station import ChargingPort

    return ChargingPort(
        port_id=port_id or uuid.uuid4(),
        station_id=station_id or uuid.uuid4(),
        connector_type=connector_type,
        charger_type="dc fast",
        status=status,
        is_pending_maintenance=is_pending_maintenance,
    )


def _station(station_id, company_id=None):
    from app.models.station import Station

    return Station(station_id=station_id, company_id=company_id or uuid.uuid4())


def _payload(port_id, start_time, end_time=None):
    from app.schemas.maintenance_schema import MaintenanceScheduleCreate

    return MaintenanceScheduleCreate(port_id=port_id, start_time=start_time, end_time=end_time or start_time + timedelta(hours=2))


@patch("app.services.maintenance_service.StationService._check_operator_permission")
def test_schedule_maintenance_future_on_available_port_just_creates_schedule(mock_permission):
    from app.services.maintenance_service import MaintenanceService

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    port = _port("Available")
    station = _station(port.station_id)

    db = MagicMock()
    db.query.side_effect = [
        _Query("first", port),  # initial port fetch
        _Query("first", station),  # station fetch for permission check
        _Query("first", station),  # Tier 1 STATIONS FOR SHARE
        _Query("first", port),  # Tier 2 CHARGING_PORTS FOR UPDATE
    ]

    schedule = MaintenanceService.schedule_maintenance(
        db, MagicMock(user_id=uuid.uuid4()), _payload(port.port_id, now + timedelta(hours=1)), "127.0.0.1"
    )

    assert schedule.status == "Scheduled"
    assert port.status == "Available"  # untouched - maintenance is in the future
    assert port.is_pending_maintenance is False
    db.commit.assert_called_once()


@patch("app.services.maintenance_service.StationService._check_operator_permission")
def test_schedule_maintenance_future_on_charging_port_sets_pending_flag(mock_permission):
    from app.services.maintenance_service import MaintenanceService

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    port = _port("Charging")
    station = _station(port.station_id)

    db = MagicMock()
    db.query.side_effect = [
        _Query("first", port),
        _Query("first", station),
        _Query("first", station),
        _Query("first", port),
    ]

    MaintenanceService.schedule_maintenance(db, MagicMock(user_id=uuid.uuid4()), _payload(port.port_id, now + timedelta(hours=1)), "127.0.0.1")

    assert port.status == "Charging"  # session runs to completion
    assert port.is_pending_maintenance is True


@patch("app.services.maintenance_service.StationService._check_operator_permission")
def test_schedule_maintenance_immediate_on_reserved_port_cancels_without_penalty(mock_permission):
    """FR-27: an immediate maintenance window (start_time in the past/now)
    forces the port into Maintenance right away, refunding the full escrow
    on any unstarted reservation rather than penalizing the driver."""
    from app.models.reservation import Reservation
    from app.services.maintenance_service import MaintenanceService

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    port = _port("Reserved")
    station = _station(port.station_id)
    reservation = Reservation(reservation_id=uuid.uuid4(), user_id=uuid.uuid4(), port_id=port.port_id, status="Confirmed")

    db = MagicMock()
    db.query.side_effect = [
        _Query("first", port),
        _Query("first", station),
        _Query("first", station),  # Tier 1 lock
        _Query("first", port),  # Tier 2 lock
        _Query("first", reservation),  # reservation lookup inside _cancel_reservation_for_maintenance
    ]

    schedule = MaintenanceService.schedule_maintenance(db, MagicMock(user_id=uuid.uuid4()), _payload(port.port_id, now), "127.0.0.1")

    assert schedule.status == "Active"
    assert reservation.status == "Cancelled"
    assert reservation.cancellation_reason == "Maintenance"
    assert port.status == "Maintenance"
    assert port.is_pending_maintenance is False

    wallet_tx = next(c.args[0] for c in db.add.call_args_list if type(c.args[0]).__name__ == "WalletTransaction")
    assert wallet_tx.transaction_type == "Escrow Release"
    assert wallet_tx.amount == pytest.approx(1000.00)


@patch("app.services.maintenance_service.StationService._check_operator_permission")
def test_schedule_maintenance_immediate_on_pending_waitlist_port_reoffers_stranded_entry(mock_permission):
    from app.models.transient import Waitlist
    from app.services.maintenance_service import MaintenanceService

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    port = _port("Pending Waitlist")
    station = _station(port.station_id)
    entry = Waitlist(waitlist_id=uuid.uuid4(), user_id=uuid.uuid4(), station_id=port.station_id, offered_port_id=port.port_id)

    db = MagicMock()
    db.query.side_effect = [
        _Query("first", port),
        _Query("first", station),
        _Query("first", station),
        _Query("first", port),
        _Query("first", entry),  # waitlist entry holding the offer on this port
        _Query("first", None),  # no other Available port at the station to re-offer
    ]

    MaintenanceService.schedule_maintenance(db, MagicMock(user_id=uuid.uuid4()), _payload(port.port_id, now), "127.0.0.1")

    assert entry.offered_port_id is None
    assert entry.offered_at is None
    assert port.status == "Maintenance"


def test_complete_maintenance_requires_port_currently_in_maintenance():
    from fastapi import HTTPException
    from app.services.maintenance_service import MaintenanceService

    port = _port("Available")
    station = _station(port.station_id)
    schedule = MagicMock(maintenance_id=uuid.uuid4(), port_id=port.port_id)

    db = MagicMock()
    db.query.side_effect = [
        _Query("first", schedule),
        _Query("first", port),
        _Query("first", station),
    ]

    with patch("app.services.maintenance_service.StationService._check_operator_permission"), pytest.raises(HTTPException) as exc_info:
        MaintenanceService.complete_maintenance(db, MagicMock(user_id=uuid.uuid4()), schedule.maintenance_id, "127.0.0.1")
    assert exc_info.value.status_code == 409


@patch("app.services.maintenance_service.WaitlistService.apply_promotion_or_release")
@patch("app.services.maintenance_service.WaitlistService.find_candidate_waitlist_entry", return_value=None)
@patch("app.services.maintenance_service.StationService._check_operator_permission")
def test_complete_maintenance_resets_port_and_clears_rejection_reputation(mock_permission, mock_find, mock_apply):
    from app.services.maintenance_service import MaintenanceService

    port = _port("Maintenance")
    station = _station(port.station_id)
    schedule = MagicMock(maintenance_id=uuid.uuid4(), port_id=port.port_id, status="Active")

    rejection_query = MagicMock()

    db = MagicMock()
    db.query.side_effect = [
        _Query("first", schedule),
        _Query("first", port),
        _Query("first", station),
        _Query("first", station),  # Tier 1 lock
        _Query("first", port),  # Tier 2 lock
        rejection_query,  # WAITLIST_REJECTIONS cleared for this port
    ]

    result = MaintenanceService.complete_maintenance(db, MagicMock(user_id=uuid.uuid4()), schedule.maintenance_id, "127.0.0.1")

    assert schedule.status == "Completed"
    mock_apply.assert_called_once_with(db, port, None)
    rejection_query.filter.return_value.delete.assert_called_once()
    db.commit.assert_called_once()


class TestCheckScheduledMaintenanceCron:
    def test_transitions_due_available_port_to_maintenance(self):
        from app.models.maintenance import MaintenanceSchedule
        from app.services.maintenance_service import MaintenanceService

        now = datetime.now(timezone.utc).replace(tzinfo=None)
        port = _port("Available")
        station = _station(port.station_id)
        maintenance_id = uuid.uuid4()
        schedule = MaintenanceSchedule(maintenance_id=maintenance_id, port_id=port.port_id, start_time=now - timedelta(minutes=1), end_time=now + timedelta(hours=1), status="Scheduled")

        db = MagicMock()
        db.query.side_effect = [
            _Query("all", [(maintenance_id,)]),  # due_ids
            _Query("first", schedule),  # optimistic re-read
            _Query("first", station),  # Tier 1 lock
            _Query("first", port),  # Tier 2 lock
            _Query("first", schedule),  # schedule re-read under lock
            _Query("first", station),  # station lookup for _apply_immediate_maintenance
        ]

        triggered = MaintenanceService.check_scheduled_maintenance(db)

        assert triggered == 1
        assert port.status == "Maintenance"
        assert schedule.status == "Active"
        db.commit.assert_called_once()

    def test_charging_port_is_soft_frozen_not_transitioned(self):
        """A port still Charging when its scheduled maintenance start_time
        arrives must not be forced offline mid-session - it gets flagged
        is_pending_maintenance and the session's own end flow routes it into
        Maintenance later."""
        from app.models.maintenance import MaintenanceSchedule
        from app.services.maintenance_service import MaintenanceService

        now = datetime.now(timezone.utc).replace(tzinfo=None)
        port = _port("Charging")
        station = _station(port.station_id)
        maintenance_id = uuid.uuid4()
        schedule = MaintenanceSchedule(maintenance_id=maintenance_id, port_id=port.port_id, start_time=now - timedelta(minutes=1), end_time=now + timedelta(hours=1), status="Scheduled")

        db = MagicMock()
        db.query.side_effect = [
            _Query("all", [(maintenance_id,)]),
            _Query("first", schedule),
            _Query("first", station),  # Tier 1 lock
            _Query("first", port),  # Tier 2 lock
            _Query("first", schedule),  # schedule re-read under lock
            _Query("first", station),  # station lookup (unconditional, before the Charging branch)
        ]

        triggered = MaintenanceService.check_scheduled_maintenance(db)

        assert triggered == 0
        assert port.status == "Charging"
        assert port.is_pending_maintenance is True
        assert schedule.status == "Scheduled"  # left for the session's own end-of-charge flow to flip
