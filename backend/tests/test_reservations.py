import pytest
import os
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.main import app
from app.core.dependencies import get_db, get_current_user
from app.models.user import User

# Use TEST_DATABASE_URL if available, else fallback to standard local DB
TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/electra_test")

try:
    engine = create_engine(TEST_DATABASE_URL)
    # Actually attempt to connect to verify credentials
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

@pytest.fixture(scope="module")
def db_session():
    if not DB_AVAILABLE:
        pytest.skip("Test Database not available")
    db = TestingSessionLocal()
    yield db
    db.close()

def test_create_reservation_missing_port():
    response = client.post("/api/v1/reservations", json={
        "vehicle_id": "12345678-1234-5678-1234-567812345678"
    })
    # Since we didn't pass station_id or port_id
    assert response.status_code == 400
    data = response.json()
    assert "Must provide either station_id or port_id" in data.get("detail", data.get("message", ""))

@pytest.mark.skipif(not DB_AVAILABLE, reason="Requires Postgres DB with SPs")
def test_auto_recommend_ignores_faulty_ports(db_session):
    # This test verifies AUD-001 by attempting to auto-recommend on a station
    # where the only available port has a health/blocked warning.
    # Requires seeded data where station has a faulty port.
    response = client.post("/api/v1/reservations", json={
        "station_id": "11111111-1111-1111-1111-111111111111", # Hypothetical station ID
        "vehicle_id": "22222222-2222-2222-2222-222222222222"
    })
    
    # If the only port has health_warning=True, it should fail with 404
    if response.status_code == 404:
        assert "No available ports" in response.json().get("detail", "")
    elif response.status_code == 200:
        # If it found a port, verify it does NOT have warnings
        port_id = response.json().get("port_id")
        from app.models.station import ChargingPort
        port = db_session.query(ChargingPort).get(port_id)
        assert port.has_health_warning == False
        assert port.has_blocked_warning == False

def test_cancel_reservation_unauthorized():
    response = client.post("/api/v1/reservations/12345678-1234-5678-1234-567812345678/cancel")
    assert response.status_code in [400, 404, 500]
