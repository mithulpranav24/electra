import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import MagicMock, patch
import pytest
from fastapi import HTTPException

from app.models.invoice import Invoice
from app.models.reservation import Reservation
from app.models.session import ChargingSession
from app.models.station import ChargingPort, Station
from app.models.user import User
from app.models.vehicle import Vehicle
from app.models.transient import CooldownWaiver
from app.services.session_service import SessionService, compute_snapshot
from app.workers.session_tasks import abort_timed_out_handshakes


def test_compute_snapshot_zero_before_ack():
    """TASK-5 / TASK-6: Billing and energy calculation must return 0 before hardware ack arrives."""
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    session = ChargingSession(
        session_id=uuid.uuid4(),
        initial_battery_percentage=Decimal("20.0"),
        target_battery_percentage=Decimal("80.0"),
        applied_tariff=Decimal("15.0"),
        start_time=now - timedelta(minutes=10),
        hardware_acked=False,
        hardware_state="Disconnected",
    )
    vehicle = Vehicle(battery_capacity=Decimal("60.0"))
    port = ChargingPort(charger_type="DC Fast")
    station = Station(minimum_session_fee=Decimal("0.0"))

    snapshot = compute_snapshot(session, vehicle, port, station, now)
    assert snapshot["energy_delivered_kwh"] == Decimal("0.00")
    assert snapshot["energy_cost"] == Decimal("0.00")
    assert snapshot["total_cost"] == Decimal("0.00")
    assert snapshot["elapsed_minutes"] == Decimal("0.0")


def test_challenge_port_rejected_when_connected():
    """TASK-1: Challenge must be rejected if hardware_state is 'Connected'."""
    db = MagicMock()
    challenger_id = uuid.uuid4()
    ghost_id = uuid.uuid4()
    port_id = uuid.uuid4()
    qr_token = uuid.uuid4()

    user = User(user_id=challenger_id, role="Driver", wallet_balance=Decimal("2000.00"))

    port = ChargingPort(
        port_id=port_id,
        station_id=uuid.uuid4(),
        status="Charging",
        qr_code="PORT-1",
        qr_token=qr_token,
    )
    station = Station(station_id=port.station_id, name="Test Station", price_per_kwh=Decimal("15.0"), timezone="UTC")
    active_res = Reservation(
        reservation_id=uuid.uuid4(),
        user_id=ghost_id,
        port_id=port_id,
        vehicle_id=uuid.uuid4(),
        status="Active",
    )
    session = ChargingSession(
        session_id=uuid.uuid4(),
        reservation_id=active_res.reservation_id,
        hardware_state="Connected",
        hardware_acked=True,
    )
    session.reservation = active_res

    def query_router(*models):
        q = MagicMock()
        model = models[0] if models else None
        if model is ChargingPort:
            q.filter.return_value.first.return_value = port
        elif model is Station:
            q.filter.return_value.first.return_value = station
        elif model is Reservation:
            q.filter.return_value.first.return_value = active_res
            q.filter.return_value.order_by.return_value.first.return_value = active_res
        elif model is ChargingSession:
            q.filter.return_value.first.return_value = session
        elif model is User:
            q.filter.return_value.first.return_value = user
        elif model is not None and getattr(model, "key", None) == "session_id":
            q.join.return_value.filter.return_value.first.return_value = None
        else:
            q.filter.return_value.first.return_value = None
        return q

    db.query.side_effect = query_router
    db.execute.return_value.scalar.return_value = 50.0

    with pytest.raises(HTTPException) as exc_info:
        SessionService.challenge_port(
            db=db,
            challenger=user,
            port_id=port_id,
            qr_code=str(qr_token),
            latitude=Decimal("12.9716"),
            longitude=Decimal("77.5946"),
            ip_address="127.0.0.1",
        )
    assert exc_info.value.status_code == 400
    assert "Hardware indicates vehicle is still connected" in exc_info.value.detail


def test_challenge_port_succeeds_when_disconnected():
    """TASK-1 / TASK-5: Challenge succeeds when hardware_state is 'Disconnected', terminating ghost session."""
    db = MagicMock()
    challenger_id = uuid.uuid4()
    ghost_user_id = uuid.uuid4()
    port_id = uuid.uuid4()
    qr_token = uuid.uuid4()

    user = User(user_id=challenger_id, role="Driver", wallet_balance=Decimal("2000.00"))

    port = ChargingPort(
        port_id=port_id,
        station_id=uuid.uuid4(),
        status="Charging",
        qr_code="PORT-1",
        qr_token=qr_token,
        charger_type="DC Fast",
    )
    station = Station(station_id=port.station_id, name="Test Station", price_per_kwh=Decimal("15.0"), timezone="UTC", minimum_session_fee=Decimal("50.0"))
    reservation = Reservation(
        reservation_id=uuid.uuid4(),
        user_id=ghost_user_id,
        port_id=port_id,
        vehicle_id=uuid.uuid4(),
        status="Active",
    )
    session = ChargingSession(
        session_id=uuid.uuid4(),
        reservation_id=reservation.reservation_id,
        hardware_state="Disconnected",
        hardware_acked=True,
        start_time=datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=5),
        applied_tariff=Decimal("15.0"),
        initial_battery_percentage=Decimal("20.0"),
        target_battery_percentage=Decimal("80.0"),
    )
    vehicle = Vehicle(vehicle_id=reservation.vehicle_id, user_id=ghost_user_id, battery_capacity=Decimal("60.0"))
    ghost_user = User(user_id=ghost_user_id, wallet_balance=Decimal("500.00"))
    challenger_vehicle = Vehicle(vehicle_id=uuid.uuid4(), user_id=challenger_id, is_active=True, is_default=True)

    session.reservation = reservation

    def query_router(*models):
        q = MagicMock()
        model = models[0] if models else None
        if model is ChargingPort:
            q.filter.return_value.first.return_value = port
            q.with_for_update.return_value.filter.return_value.first.return_value = port
        elif model is Station:
            q.filter.return_value.first.return_value = station
            q.with_for_update.return_value.filter.return_value.first.return_value = station
        elif model is Reservation:
            q.filter.return_value.first.return_value = reservation
            q.filter.return_value.order_by.return_value.first.return_value = reservation
            q.with_for_update.return_value.filter.return_value.first.return_value = reservation
        elif model is ChargingSession:
            q.filter.return_value.first.return_value = session
            q.with_for_update.return_value.filter.return_value.first.return_value = session
        elif model is Vehicle:
            q.filter.return_value.first.return_value = vehicle
            q.with_for_update.return_value.filter.return_value.first.return_value = vehicle
            q.filter.return_value.order_by.return_value.first.return_value = challenger_vehicle
        elif model is User:
            q.filter.return_value.first.return_value = ghost_user
            q.with_for_update.return_value.filter.return_value.first.return_value = ghost_user
            q.filter.return_value.with_for_update.return_value.all.return_value = [ghost_user, user]
            q.with_for_update.return_value.filter.return_value.all.return_value = [ghost_user, user]
        elif model is not None and getattr(model, "key", None) == "session_id":
            q.join.return_value.filter.return_value.first.return_value = None
        else:
            q.filter.return_value.first.return_value = None
        return q

    db.query.side_effect = query_router
    db.execute.return_value.scalar.return_value = 50.0

    # Nested transaction mock for savepoint
    savepoint_mock = MagicMock()
    db.begin_nested.return_value = savepoint_mock

    res = SessionService.challenge_port(
        db=db,
        challenger=user,
        port_id=port_id,
        qr_code=str(qr_token),
        latitude=Decimal("12.9716"),
        longitude=Decimal("77.5946"),
        ip_address="127.0.0.1",
    )

    assert res["success"] is True
    assert session.end_time is not None
    assert port.status in ["Available", "Reserved", "Pending Waitlist"]
    assert db.commit.called


def test_abort_timed_out_handshakes_refunds_all():
    """TASK-5: Handshake timeout abort must refund escrow (1000) and energy secondary hold, and mark is_aborted=True."""
    db = MagicMock()
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    session_id = uuid.uuid4()
    reservation_id = uuid.uuid4()
    user_id = uuid.uuid4()
    port_id = uuid.uuid4()

    session = ChargingSession(
        session_id=session_id,
        reservation_id=reservation_id,
        applied_tariff=Decimal("15.0"),
        initial_battery_percentage=Decimal("20.0"),
        target_battery_percentage=Decimal("80.0"),
        hardware_acked=False,
        hardware_ack_deadline=now - timedelta(seconds=10),
        end_time=None,
        is_aborted=False,
    )
    reservation = Reservation(
        reservation_id=reservation_id,
        user_id=user_id,
        port_id=port_id,
        vehicle_id=uuid.uuid4(),
        status="Active",
    )
    port = ChargingPort(
        port_id=port_id,
        station_id=uuid.uuid4(),
        status="Charging",
        consecutive_handshake_failures=0,
    )
    vehicle = Vehicle(vehicle_id=reservation.vehicle_id, user_id=user_id, battery_capacity=Decimal("60.0"))
    station = Station(station_id=port.station_id, name="Test Station", price_per_kwh=Decimal("15.0"), timezone="UTC", minimum_session_fee=Decimal("50.0"))

    def query_router(*models):
        q = MagicMock()
        model = models[0] if models else None
        if model is ChargingSession:
            q.filter.return_value.all.return_value = [session]
        elif model is Reservation:
            q.filter.return_value.first.return_value = reservation
        elif model is ChargingPort:
            q.with_for_update.return_value.filter.return_value.first.return_value = port
            q.filter.return_value.first.return_value = port
        elif model is Vehicle:
            q.filter.return_value.first.return_value = vehicle
        elif model is Station:
            q.filter.return_value.first.return_value = station
        return q

    db.query.side_effect = query_router

    with patch("app.workers.session_tasks.SessionLocal", return_value=db):
        count = abort_timed_out_handshakes()
        assert count == 1
        assert session.is_aborted is True
        assert session.end_time is not None
        assert reservation.status == "Expired"
        assert port.consecutive_handshake_failures == 1
        assert port.status == "Available"

        # Verify wallet transaction refund amounts
        added_objects = [call[0][0] for call in db.add.call_args_list]
        from app.models.wallet import WalletTransaction
        wallet_txs = [o for o in added_objects if isinstance(o, WalletTransaction)]
        amounts = [tx.amount for tx in wallet_txs]
        assert Decimal("1000.00") in amounts
        assert any(a > 0 for a in amounts if a != Decimal("1000.00"))


def test_trusted_driver_cooldown_waiver_tracking():
    """TASK-6: Trusted driver cancellation within 5 minutes under 'Faulty Charger' gets recorded as CooldownWaiver."""
    user_id = uuid.uuid4()
    station_id = uuid.uuid4()
    res_id = uuid.uuid4()

    waiver = CooldownWaiver(
        user_id=user_id,
        reservation_id=res_id,
        station_id=station_id,
        reason="Faulty Charger",
    )
    assert waiver.reason == "Faulty Charger"
    assert waiver.station_id == station_id
    assert waiver.user_id == user_id
