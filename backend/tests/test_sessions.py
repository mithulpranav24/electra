import pytest
import os
from decimal import Decimal
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.main import app
from app.core.dependencies import get_db, get_current_user
from app.models.user import User

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/electra_test")

try:
    engine = create_engine(TEST_DATABASE_URL)
    with engine.connect() as conn:
        pass
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    DB_AVAILABLE = True
except Exception:
    DB_AVAILABLE = False

def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

def mock_get_current_user():
    import uuid
    user = User()
    user.user_id = uuid.UUID("12345678-1234-5678-1234-567812345678")
    user.role = "Driver"
    user.wallet_balance = 5000.00
    return user

app.dependency_overrides[get_current_user] = mock_get_current_user

if DB_AVAILABLE:
    app.dependency_overrides[get_db] = override_get_db
else:
    def mock_get_db_when_offline():
        from unittest.mock import MagicMock
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        # _load_active_session_context queries as .query().join().filter().first()
        db.query.return_value.join.return_value.filter.return_value.first.return_value = None
        yield db
    app.dependency_overrides[get_db] = mock_get_db_when_offline

client = TestClient(app)


def test_start_session_missing_fields():
    response = client.post("/api/v1/sessions/start", json={"reservation_id": "12345678-1234-5678-1234-567812345678"})
    assert response.status_code == 422


def _no_active_session_db():
    """A local, self-contained mock (not routed through the shared
    app.dependency_overrides[get_db], which other test modules in this same
    pytest process also reassign at import time) whose query chain returns
    None regardless of how many .filter()/.join() calls precede .first()."""
    from unittest.mock import MagicMock

    class _AlwaysNoneQuery:
        def __getattr__(self, name):
            if name == "first":
                return lambda: None
            return lambda *a, **k: self

    db = MagicMock()
    db.query.side_effect = lambda *a, **k: _AlwaysNoneQuery()
    return db


def test_get_active_session_none_when_no_session():
    from app.services.session_service import SessionService
    from app.models.user import User
    import uuid

    user = User()
    user.user_id = uuid.UUID("12345678-1234-5678-1234-567812345678")
    result = SessionService.get_active_session_status(_no_active_session_db(), user)
    assert result is None


def test_stop_session_no_active_session():
    from fastapi import HTTPException
    from app.services.session_service import SessionService
    from app.models.user import User
    import uuid

    user = User()
    user.user_id = uuid.UUID("12345678-1234-5678-1234-567812345678")
    with pytest.raises(HTTPException) as exc_info:
        SessionService.stop_session(_no_active_session_db(), user, "127.0.0.1")
    assert exc_info.value.status_code == 404


class TestChargingCurveMath:
    """Pure-function tests for the non-linear charging simulation (DD-05) and
    idle fee escalation (DD-06) - no DB required."""

    def test_minutes_to_reach_target_full_and_throttled_segments(self):
        from app.services.session_service import minutes_to_reach_target
        # 40kWh battery, 50kW port, 20% -> 100%: 60% at full rate (28.8min) + 20% at throttled rate (48min)
        minutes = minutes_to_reach_target(Decimal("20"), Decimal("100"), Decimal("40"), Decimal("50"))
        assert abs(minutes - Decimal("76.8")) < Decimal("0.01")

    def test_minutes_to_reach_target_starting_above_80_percent(self):
        # Regression: starting already inside the throttled segment (e.g. 85%)
        # must measure distance from initial_pct, not from the 80% boundary -
        # the entire 20 -> 100% curve above only differs by starting later.
        from app.services.session_service import minutes_to_reach_target
        throttled_only = minutes_to_reach_target(Decimal("85"), Decimal("100"), Decimal("40"), Decimal("50"))
        # 15% at throttled rate (20% of 50kW = 10kW): 6kWh / 10kW * 60 = 36 min
        assert abs(throttled_only - Decimal("36")) < Decimal("0.01")

        full_curve_throttled_leg = minutes_to_reach_target(Decimal("80"), Decimal("100"), Decimal("40"), Decimal("50"))
        # 85% is 5 percentage points further into the same throttled segment
        # than 80%, so it must take proportionally less time, not the same time.
        assert throttled_only < full_curve_throttled_leg

    def test_current_battery_percentage_caps_at_target(self):
        from app.services.session_service import current_battery_percentage
        pct = current_battery_percentage(Decimal("20"), Decimal("30"), Decimal("40"), Decimal("50"), Decimal("1000"))
        assert pct == Decimal("30")

    def test_current_battery_percentage_within_full_rate_segment(self):
        from app.services.session_service import current_battery_percentage
        # Midpoint of the 20->80 full-rate segment (28.8 min total) should read exactly 50%
        pct = current_battery_percentage(Decimal("20"), Decimal("100"), Decimal("40"), Decimal("50"), Decimal("14.4"))
        assert abs(pct - Decimal("50")) < Decimal("0.01")

    def test_idle_fee_grace_and_cap_and_blockage_tier(self):
        from app.services.session_service import calculate_idle_fee
        assert calculate_idle_fee(Decimal("0")) == Decimal("0.00")
        assert calculate_idle_fee(Decimal("15")) == Decimal("150.00")
        assert calculate_idle_fee(Decimal("100")) == Decimal("1000.00")
        assert calculate_idle_fee(Decimal("160")) == Decimal("1500.00")

    def test_billable_idle_minutes_applies_30_minute_grace(self):
        from app.services.session_service import billable_idle_minutes
        assert billable_idle_minutes(Decimal("20")) == Decimal("0")
        assert billable_idle_minutes(Decimal("45")) == Decimal("15")

    def test_compute_secondary_hold_includes_battery_capacity(self):
        from app.services.session_service import compute_secondary_hold
        from app.models.session import ChargingSession
        from app.models.vehicle import Vehicle
        from app.models.station import Station

        session = ChargingSession(initial_battery_percentage=Decimal("20"), target_battery_percentage=Decimal("30"), applied_tariff=Decimal("15.50"))
        vehicle = Vehicle(battery_capacity=Decimal("40"))
        station = Station(minimum_session_fee=Decimal("50.00"))
        # GREATEST(50.00, 10% * 40kWh * 15.50) = GREATEST(50.00, 62.00) = 62.00
        assert compute_secondary_hold(session, vehicle, station) == Decimal("62.00")


class _RecordingQuery:
    """Like the _AlwaysNoneQuery pattern above, but returns a configured
    terminal value and records every chained call (with its args/kwargs) so
    tests can assert on lock modes (with_for_update(read=True, of=...)) and
    call order, not just the final returned value."""

    def __init__(self, terminal, value):
        self._terminal = terminal
        self._value = value
        self.calls = {}

    def __getattr__(self, name):
        if name == self._terminal:
            return lambda *a, **k: self._value

        def _chain(*a, **k):
            self.calls.setdefault(name, []).append((a, k))
            return self

        return _chain


class TestEnforceOverstayPenaltiesClosurePause:
    """FR-21 / Architecture.md 3.4: while a station's gate is locked, the
    driver cannot physically retrieve their vehicle, so that time must not
    count toward the 30-minute idle grace period."""

    def _base_objects(self, now, locked_gate, locked_gate_at, cumulative_closure_seconds=0):
        import uuid
        from datetime import timedelta

        from app.models.reservation import Reservation
        from app.models.session import ChargingSession
        from app.models.station import ChargingPort, Station
        from app.models.user import User
        from app.models.vehicle import Vehicle

        session_id = uuid.uuid4()
        reservation_id = uuid.uuid4()
        port_id = uuid.uuid4()
        station_id = uuid.uuid4()
        user_id = uuid.uuid4()

        # 40kWh battery, 50kW ("dc fast") port, 20% -> 100% takes 76.8 minutes
        # (matches TestChargingCurveMath.test_minutes_to_reach_target_full_and_throttled_segments).
        minutes_to_target = Decimal("76.8")
        start_time = now - timedelta(minutes=float(minutes_to_target) + 40)

        session = ChargingSession(
            session_id=session_id,
            reservation_id=reservation_id,
            initial_battery_percentage=Decimal("20"),
            target_battery_percentage=Decimal("100"),
            applied_tariff=Decimal("15.50"),
            start_time=start_time,
            end_time=None,
            is_overstay_penalized=False,
            cumulative_closure_seconds=cumulative_closure_seconds,
        )
        reservation = Reservation(reservation_id=reservation_id, port_id=port_id, vehicle_id=uuid.uuid4(), user_id=user_id)
        port = ChargingPort(port_id=port_id, station_id=station_id, charger_type="dc fast")
        vehicle = Vehicle(battery_capacity=Decimal("40"))
        station = Station(station_id=station_id, locked_gate=locked_gate, locked_gate_at=locked_gate_at)
        user = User(user_id=user_id)

        return session_id, session, reservation, port, vehicle, station, user

    def test_no_penalty_while_gate_currently_locked_since_idle_start(self):
        """40 minutes of wall-clock idle time, but the gate has been locked
        for all 40 of those minutes (locked exactly when charging finished) -
        none of it should count, so no penalty is applied."""
        from datetime import datetime, timedelta, timezone
        from unittest.mock import MagicMock

        from app.services.session_service import SessionService

        now = datetime.now(timezone.utc).replace(tzinfo=None)
        idle_start = now - timedelta(minutes=40)
        session_id, session, reservation, port, vehicle, station, user = self._base_objects(
            now, locked_gate=True, locked_gate_at=idle_start
        )

        db = MagicMock()
        db.query.side_effect = [
            _RecordingQuery("all", [(session_id,)]),  # candidate_ids
            _RecordingQuery("first", session),  # optimistic
            _RecordingQuery("first", reservation),
            _RecordingQuery("first", port),
            _RecordingQuery("first", vehicle),
            _RecordingQuery("first", station),  # station_optimistic - gate locked -> should stop here
        ]

        result = SessionService.enforce_overstay_penalties(db)

        assert result == 0
        assert session.is_overstay_penalized is False
        # Only the 6 optimistic-read queries above should have run - no locks acquired.
        assert db.query.call_count == 6

    def test_penalty_still_applies_once_open_station_time_exceeds_grace(self):
        """The gate is currently open (not locked) and 40 minutes of idle
        time have genuinely elapsed with the station open the whole time -
        the overstay penalty must still fire."""
        from datetime import datetime, timezone
        from unittest.mock import MagicMock, patch

        from app.models.station import ChargingPort, Station
        from app.models.user import User
        from app.services.session_service import SessionService

        now = datetime.now(timezone.utc).replace(tzinfo=None)
        session_id, session, reservation, port, vehicle, station, user = self._base_objects(
            now, locked_gate=False, locked_gate_at=None
        )

        db = MagicMock()
        db.query.side_effect = [
            _RecordingQuery("all", [(session_id,)]),  # candidate_ids
            _RecordingQuery("first", session),  # optimistic
            _RecordingQuery("first", reservation),
            _RecordingQuery("first", port),
            _RecordingQuery("first", vehicle),
            _RecordingQuery("first", station),  # station_optimistic
            (tier1 := _RecordingQuery("first", station)),  # Tier 1: STATIONS FOR SHARE
            (tier2 := _RecordingQuery("first", port)),  # Tier 2: CHARGING_PORTS FOR SHARE
            _RecordingQuery("first", user),  # Tier 3: USERS FOR UPDATE
            _RecordingQuery("first", session),  # Tier 6: CHARGING_SESSIONS FOR UPDATE
        ]

        with patch("app.services.session_service.PenaltyService.assign_penalty_point") as mock_assign:
            result = SessionService.enforce_overstay_penalties(db)

        assert result == 1
        assert session.is_overstay_penalized is True
        mock_assign.assert_called_once_with(db, user, "Overstay After Charging Complete")

        # Global lock hierarchy (Architecture.md 3.5): Tier 1 STATIONS FOR SHARE
        # before Tier 2 CHARGING_PORTS FOR SHARE before Tier 3/6.
        assert tier1.calls["with_for_update"] == [((), {"read": True, "of": Station})]
        assert tier2.calls["with_for_update"] == [((), {"read": True, "of": ChargingPort})]
        locked_models = [args[0] for args, _ in db.query.call_args_list[6:10]]
        assert locked_models == [Station, ChargingPort, User, session.__class__]
