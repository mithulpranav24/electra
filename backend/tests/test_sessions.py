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
