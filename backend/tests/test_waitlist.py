import pytest
import os
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
