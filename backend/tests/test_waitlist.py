import pytest
import os
import uuid
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.main import app
from app.core.dependencies import get_db, get_current_user
from app.models.user import User

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL", "postgresql://postgres:postgres@localhost:5433/electra_test")

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
    user = User()
    user.user_id = "12345678-1234-5678-1234-567812345678"
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
        yield db
    app.dependency_overrides[get_db] = mock_get_db_when_offline

client = TestClient(app)


def test_join_waitlist_missing_vehicle_id():
    response = client.post("/api/v1/waitlist", json={
        "station_id": "11111111-1111-1111-1111-111111111111",
        "lat": 12.9716,
        "lng": 77.5946,
    })
    assert response.status_code == 422


@pytest.mark.skipif(DB_AVAILABLE, reason="Exercises the offline mock-db 404 path only")
def test_join_waitlist_vehicle_not_found_when_offline():
    response = client.post("/api/v1/waitlist", json={
        "station_id": "11111111-1111-1111-1111-111111111111",
        "vehicle_id": "22222222-2222-2222-2222-222222222222",
        "lat": 12.9716,
        "lng": 77.5946,
    })
    assert response.status_code == 404
    data = response.json()
    assert "Vehicle not found" in data.get("detail", data.get("message", ""))


@pytest.mark.skipif(DB_AVAILABLE, reason="Exercises the offline mock-db empty-state path only")
def test_get_waitlist_status_none_when_offline():
    response = client.get("/api/v1/waitlist/status")
    assert response.status_code == 200
    body = response.json()
    data = body.get("data") if isinstance(body, dict) else body
    assert data is None


@pytest.mark.skipif(DB_AVAILABLE, reason="Exercises the offline mock-db 404 path only")
def test_leave_waitlist_when_none_active():
    response = client.delete("/api/v1/waitlist")
    assert response.status_code == 404


@pytest.mark.skipif(DB_AVAILABLE, reason="Exercises the offline mock-db 404 path only")
def test_confirm_waitlist_offer_not_found():
    response = client.post("/api/v1/waitlist/33333333-3333-3333-3333-333333333333/confirm")
    assert response.status_code == 404


class _Query:
    """Minimal chainable query double: any non-terminal attribute access
    (.filter()/.join()/.with_for_update()/.order_by()) returns self, and the
    configured terminal method returns the configured value."""

    def __init__(self, terminal, value):
        self._terminal = terminal
        self._value = value

    def __getattr__(self, name):
        if name == self._terminal:
            return lambda *a, **k: self._value
        return lambda *a, **k: self


class TestLeaveWaitlistPenaltyEvasion:
    """Architecture.md 3.3.3 Rule 7: leaving the waitlist while holding an
    active offer must be penalized exactly like ignoring the offer would be -
    otherwise a driver could dodge the 1-point penalty by leaving manually
    instead of letting the 90-second offer window expire."""

    def _entry(self, offered_port_id):
        from app.models.transient import Waitlist

        return Waitlist(
            waitlist_id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            station_id=uuid.uuid4(),
            vehicle_id=uuid.uuid4(),
            offered_port_id=offered_port_id,
        )

    def test_leaving_with_an_active_offer_assigns_a_penalty_point(self):
        from unittest.mock import MagicMock, patch

        from app.models.station import ChargingPort
        from app.models.user import User
        from app.services.waitlist_service import WaitlistService

        current_user = User(user_id=uuid.uuid4())
        port_id = uuid.uuid4()
        entry_read = self._entry(offered_port_id=port_id)
        locked_entry = self._entry(offered_port_id=port_id)
        locked_entry.waitlist_id = entry_read.waitlist_id
        port = ChargingPort(port_id=port_id, status="Pending Waitlist", connector_type="CCS2")

        db = MagicMock()
        db.query.side_effect = [
            _Query("first", entry_read),  # entry_read
            _Query("first", None),  # STATIONS FOR SHARE (return value unused)
            _Query("first", port),  # CHARGING_PORTS FOR UPDATE (offer held)
            _Query("first", None),  # VEHICLES FOR UPDATE
            _Query("first", None),  # USERS FOR UPDATE
            _Query("first", locked_entry),  # WAITLIST FOR UPDATE
        ]

        with patch("app.services.waitlist_service.PenaltyService.assign_penalty_point") as mock_assign, patch(
            "app.services.waitlist_service.WaitlistService.find_candidate_waitlist_entry", return_value=None
        ), patch("app.services.waitlist_service.WaitlistService.apply_promotion_or_release"):
            WaitlistService.leave_waitlist(db, current_user, "127.0.0.1")

        mock_assign.assert_called_once_with(db, current_user, "Ignored Waitlist Offer")

    def test_leaving_without_an_active_offer_does_not_assign_a_penalty(self):
        from unittest.mock import MagicMock, patch

        from app.models.user import User
        from app.services.waitlist_service import WaitlistService

        current_user = User(user_id=uuid.uuid4())
        entry_read = self._entry(offered_port_id=None)
        locked_entry = self._entry(offered_port_id=None)
        locked_entry.waitlist_id = entry_read.waitlist_id

        db = MagicMock()
        db.query.side_effect = [
            _Query("first", entry_read),  # entry_read
            _Query("first", None),  # STATIONS FOR SHARE
            _Query("first", None),  # VEHICLES FOR UPDATE
            _Query("first", None),  # USERS FOR UPDATE
            _Query("first", locked_entry),  # WAITLIST FOR UPDATE
        ]

        with patch("app.services.waitlist_service.PenaltyService.assign_penalty_point") as mock_assign:
            WaitlistService.leave_waitlist(db, current_user, "127.0.0.1")

        mock_assign.assert_not_called()


class TestClearWaitlistForBannedUsersRaceCondition:
    """Architecture.md 3.3.3 Rule 7 rollback-and-retry: if a concurrent worker
    assigns an offer to this entry between the optimistic read and the
    WAITLIST FOR UPDATE lock, the port lock this sweep already holds (or
    skipped acquiring) no longer matches the entry's real state. Deleting the
    entry anyway would orphan the port in Pending Waitlist forever, since
    nothing would be left pointing at it to trigger promotion/release."""

    def test_offer_assigned_concurrently_after_optimistic_read_triggers_rollback(self):
        from datetime import datetime, timedelta, timezone
        from unittest.mock import MagicMock, patch

        from app.models.transient import Waitlist
        from app.models.user import User
        from app.services.waitlist_service import WaitlistService

        waitlist_id = uuid.uuid4()
        user_id = uuid.uuid4()
        now = datetime.now(timezone.utc).replace(tzinfo=None)

        # Optimistic read: no offer held yet.
        optimistic = Waitlist(waitlist_id=waitlist_id, user_id=user_id, station_id=uuid.uuid4(), offered_port_id=None)
        user = User(user_id=user_id, banned_until=now + timedelta(hours=1))
        # Locked re-read: a concurrent worker assigned an offer in the meantime.
        entry_locked = Waitlist(waitlist_id=waitlist_id, user_id=user_id, station_id=optimistic.station_id, offered_port_id=uuid.uuid4())

        db = MagicMock()
        db.query.side_effect = [
            _Query("all", [(waitlist_id,)]),  # stale_ids
            _Query("first", optimistic),  # optimistic re-read
            _Query("first", None),  # Tier 1: STATIONS FOR SHARE
            # optimistic.offered_port_id is None, so no Tier 2 CHARGING_PORTS query is issued.
            _Query("first", user),  # Tier 3: USERS FOR UPDATE
            _Query("first", entry_locked),  # Tier 3.5: WAITLIST FOR UPDATE
        ]

        with patch("app.services.waitlist_service.WaitlistService.find_candidate_waitlist_entry") as mock_find, patch(
            "app.services.waitlist_service.WaitlistService.apply_promotion_or_release"
        ) as mock_apply:
            cleared = WaitlistService.clear_waitlist_for_banned_users(db)

        assert cleared == 0
        db.rollback.assert_called()
        db.delete.assert_not_called()
        mock_find.assert_not_called()
        mock_apply.assert_not_called()
