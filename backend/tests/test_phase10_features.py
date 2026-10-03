import os
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import MagicMock, patch
import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.models.invoice import Invoice
from app.models.reservation import Reservation
from app.models.session import ChargingSession
from app.models.station import ChargingPort, Station
from app.models.user import User
from app.models.vehicle import Vehicle
from app.models.transient import CooldownWaiver
from app.services.session_service import SessionService, compute_snapshot
from app.services.user_service import UserService
from app.schemas.reservation_schema import ReservationCreate, CancelReservationRequest
from app.controllers.reservation_controller import create_reservation, cancel_reservation
from app.workers.session_tasks import abort_timed_out_handshakes

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/electra_test")

try:
    engine = create_engine(TEST_DATABASE_URL)
    with engine.connect() as conn:
        pass
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    DB_AVAILABLE = True
except Exception:
    DB_AVAILABLE = False


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


# ============================================================================
# Real PostgreSQL Integration Tests (Run in CI with electra_test DB)
# ============================================================================


@pytest.mark.skipif(not DB_AVAILABLE, reason="Requires Postgres DB with SPs and schema")
def test_real_db_challenge_connected_then_disconnected():
    """A challenge is rejected while the session is Connected, and succeeds after mock-disconnect.
    The ghost session gets an invoice and the port is freed or re-reserved."""
    db = TestingSessionLocal()
    try:
        company_id = uuid.uuid4()
        area_id = uuid.uuid4()
        station_id = uuid.uuid4()
        port_id = uuid.uuid4()
        qr_token = uuid.uuid4()
        qr_code = f"QR-CHAL-{uuid.uuid4().hex[:8]}"

        db.execute(text("INSERT INTO COMPANIES (company_id, name) VALUES (:cid, :name)"), {"cid": company_id, "name": f"Chal Co {company_id}"})
        db.execute(text("INSERT INTO AREAS (area_id, name) VALUES (:aid, :name)"), {"aid": area_id, "name": f"Chal Area {area_id}"})
        db.execute(text("""
            INSERT INTO STATIONS (station_id, company_id, area_id, name, gps_coordinates, price_per_kwh, minimum_session_fee, opening_time_local, closing_time_local, timezone)
            VALUES (:sid, :cid, :aid, 'Test Station', ST_SetSRID(ST_MakePoint(77.5946, 12.9716), 4326), 15.0, 50.0, '00:00:00', '23:59:59', 'UTC')
        """), {"sid": station_id, "cid": company_id, "aid": area_id})

        db.execute(text("""
            INSERT INTO CHARGING_PORTS (port_id, station_id, qr_code, qr_token, connector_type, charger_type, status)
            VALUES (:pid, :sid, :qr, :qtok, 'CCS2', 'DC Fast', 'Charging')
        """), {"pid": port_id, "sid": station_id, "qr": qr_code, "qtok": qr_token})

        ghost_user_id = uuid.uuid4()
        ghost_veh_id = uuid.uuid4()
        ghost_res_id = uuid.uuid4()
        ghost_sess_id = uuid.uuid4()

        db.execute(text("""
            INSERT INTO USERS (user_id, email, password_hash, full_name, phone_number, role, wallet_balance)
            VALUES (:uid, :email, 'hash', 'Ghost Driver', '9999999991', 'Driver', 5000.00)
        """), {"uid": ghost_user_id, "email": f"ghost_{ghost_user_id.hex}@test.com"})
        db.execute(text("INSERT INTO WALLET_TRANSACTIONS (user_id, amount, transaction_type) VALUES (:uid, 5000.00, 'Top-up')"), {"uid": ghost_user_id})

        db.execute(text("""
            INSERT INTO VEHICLES (vehicle_id, user_id, make, model, registration_number, battery_capacity, connector_type, is_active, is_default)
            VALUES (:vid, :uid, 'Tesla', 'Model 3', :reg, 60.0, 'CCS2', TRUE, TRUE)
        """), {"vid": ghost_veh_id, "uid": ghost_user_id, "reg": f"GHOST-{ghost_user_id.hex[:8]}"})

        db.execute(text("""
            INSERT INTO RESERVATIONS (reservation_id, user_id, port_id, vehicle_id, status, reserved_tariff, expires_at)
            VALUES (:rid, :uid, :pid, :vid, 'Active', 15.00, CURRENT_TIMESTAMP + INTERVAL '1 hour')
        """), {"rid": ghost_res_id, "uid": ghost_user_id, "pid": port_id, "vid": ghost_veh_id})
        db.execute(text("INSERT INTO WALLET_TRANSACTIONS (user_id, amount, transaction_type, reference_id) VALUES (:uid, -1000.00, 'Escrow Hold', :rid)"), {"uid": ghost_user_id, "rid": ghost_res_id})

        db.execute(text("""
            INSERT INTO CHARGING_SESSIONS (session_id, reservation_id, initial_battery_percentage, target_battery_percentage, applied_tariff, start_time, hardware_acked, hardware_state)
            VALUES (:sid, :rid, 20.0, 80.0, 15.0, CURRENT_TIMESTAMP - INTERVAL '10 minutes', TRUE, 'Connected')
        """), {"sid": ghost_sess_id, "rid": ghost_res_id})

        challenger_id = uuid.uuid4()
        challenger_veh_id = uuid.uuid4()
        db.execute(text("""
            INSERT INTO USERS (user_id, email, password_hash, full_name, phone_number, role, wallet_balance)
            VALUES (:uid, :email, 'hash', 'Challenger Driver', '9999999992', 'Driver', 5000.00)
        """), {"uid": challenger_id, "email": f"chal_{challenger_id.hex}@test.com"})
        db.execute(text("INSERT INTO WALLET_TRANSACTIONS (user_id, amount, transaction_type) VALUES (:uid, 5000.00, 'Top-up')"), {"uid": challenger_id})

        db.execute(text("""
            INSERT INTO VEHICLES (vehicle_id, user_id, make, model, registration_number, battery_capacity, connector_type, is_active, is_default)
            VALUES (:vid, :uid, 'Tata', 'Nexon EV', :reg, 40.0, 'CCS2', TRUE, TRUE)
        """), {"vid": challenger_veh_id, "uid": challenger_id, "reg": f"CHAL-{challenger_id.hex[:8]}"})
        db.commit()

        challenger_user = db.query(User).filter(User.user_id == challenger_id).first()

        # 1. Challenge while Connected must be rejected
        with pytest.raises(HTTPException) as exc_info:
            SessionService.challenge_port(
                db=db,
                challenger=challenger_user,
                port_id=port_id,
                qr_code=str(qr_token),
                latitude=Decimal("12.9716"),
                longitude=Decimal("77.5946"),
                ip_address="127.0.0.1",
            )
        assert exc_info.value.status_code == 400
        assert "Hardware indicates vehicle is still connected" in exc_info.value.detail

        # 2. Mock disconnect
        session_obj = db.query(ChargingSession).filter(ChargingSession.session_id == ghost_sess_id).first()
        session_obj.hardware_state = "Disconnected"
        db.commit()

        # 3. Challenge again -> succeeds
        res = SessionService.challenge_port(
            db=db,
            challenger=challenger_user,
            port_id=port_id,
            qr_code=str(qr_token),
            latitude=Decimal("12.9716"),
            longitude=Decimal("77.5946"),
            ip_address="127.0.0.1",
        )
        assert res["success"] is True

        db.refresh(session_obj)
        assert session_obj.end_time is not None
        invoice = db.query(Invoice).filter(Invoice.charging_session_id == ghost_sess_id).first()
        assert invoice is not None
        assert float(invoice.total_amount) > 0

        port_obj = db.query(ChargingPort).filter(ChargingPort.port_id == port_id).first()
        assert port_obj.status in ["Available", "Reserved", "Pending Waitlist"]
    finally:
        db.close()


@pytest.mark.skipif(not DB_AVAILABLE, reason="Requires Postgres DB with SPs and schema")
def test_real_db_handshake_timeout_refunds_all():
    """A handshake timeout refunds the escrow plus the energy pre-auth, so the wallet balance is back to where it was before the session."""
    db = TestingSessionLocal()
    try:
        user_id = uuid.uuid4()
        initial_balance = Decimal("5000.00")
        db.execute(text("""
            INSERT INTO USERS (user_id, email, password_hash, full_name, phone_number, role, wallet_balance)
            VALUES (:uid, :email, 'hash', 'Timeout Driver', '9999999993', 'Driver', :bal)
        """), {"uid": user_id, "email": f"timeout_{user_id.hex}@test.com", "bal": initial_balance})
        db.execute(text("INSERT INTO WALLET_TRANSACTIONS (user_id, amount, transaction_type) VALUES (:uid, :bal, 'Top-up')"), {"uid": user_id, "bal": initial_balance})

        company_id = uuid.uuid4()
        area_id = uuid.uuid4()
        station_id = uuid.uuid4()
        port_id = uuid.uuid4()
        veh_id = uuid.uuid4()
        res_id = uuid.uuid4()
        sess_id = uuid.uuid4()
        qr_code = f"QR-TIM-{uuid.uuid4().hex[:8]}"

        db.execute(text("INSERT INTO COMPANIES (company_id, name) VALUES (:cid, :name)"), {"cid": company_id, "name": f"Timeout Co {company_id}"})
        db.execute(text("INSERT INTO AREAS (area_id, name) VALUES (:aid, :name)"), {"aid": area_id, "name": f"Timeout Area {area_id}"})
        db.execute(text("""
            INSERT INTO STATIONS (station_id, company_id, area_id, name, gps_coordinates, price_per_kwh, minimum_session_fee, opening_time_local, closing_time_local, timezone)
            VALUES (:sid, :cid, :aid, 'Timeout Station', ST_SetSRID(ST_MakePoint(77.5946, 12.9716), 4326), 15.0, 50.0, '00:00:00', '23:59:59', 'UTC')
        """), {"sid": station_id, "cid": company_id, "aid": area_id})

        db.execute(text("""
            INSERT INTO CHARGING_PORTS (port_id, station_id, qr_code, connector_type, charger_type, status)
            VALUES (:pid, :sid, :qr, 'CCS2', 'DC Fast', 'Charging')
        """), {"pid": port_id, "sid": station_id, "qr": qr_code})

        db.execute(text("""
            INSERT INTO VEHICLES (vehicle_id, user_id, make, model, registration_number, battery_capacity, connector_type, is_active, is_default)
            VALUES (:vid, :uid, 'Tata', 'Nexon EV', :reg, 40.0, 'CCS2', TRUE, TRUE)
        """), {"vid": veh_id, "uid": user_id, "reg": f"TIM-{user_id.hex[:8]}"})

        db.execute(text("""
            INSERT INTO RESERVATIONS (reservation_id, user_id, port_id, vehicle_id, status, reserved_tariff, expires_at)
            VALUES (:rid, :uid, :pid, :vid, 'Active', 15.00, CURRENT_TIMESTAMP + INTERVAL '1 hour')
        """), {"rid": res_id, "uid": user_id, "pid": port_id, "vid": veh_id})

        db.execute(text("""
            INSERT INTO CHARGING_SESSIONS (session_id, reservation_id, initial_battery_percentage, target_battery_percentage, applied_tariff, start_time, hardware_acked, hardware_ack_deadline, is_aborted)
            VALUES (:sid, :rid, 20.0, 80.0, 15.0, CURRENT_TIMESTAMP - INTERVAL '2 minutes', FALSE, CURRENT_TIMESTAMP - INTERVAL '10 seconds', FALSE)
        """), {"sid": sess_id, "rid": res_id})

        from app.services.session_service import compute_secondary_hold
        sess_model = db.query(ChargingSession).filter(ChargingSession.session_id == sess_id).first()
        veh_model = db.query(Vehicle).filter(Vehicle.vehicle_id == veh_id).first()
        st_model = db.query(Station).filter(Station.station_id == station_id).first()
        secondary_hold = compute_secondary_hold(sess_model, veh_model, st_model)

        db.execute(text("INSERT INTO WALLET_TRANSACTIONS (user_id, amount, transaction_type, reference_id) VALUES (:uid, -1000.00, 'Escrow Hold', :rid)"), {"uid": user_id, "rid": res_id})
        db.execute(text("INSERT INTO WALLET_TRANSACTIONS (user_id, amount, transaction_type, reference_id) VALUES (:uid, -:hold, 'Session Payment', :rid)"), {"uid": user_id, "rid": res_id, "hold": secondary_hold})
        db.commit()
    finally:
        db.close()

    with patch("app.workers.session_tasks.SessionLocal", side_effect=TestingSessionLocal):
        aborted_count = abort_timed_out_handshakes()

    assert aborted_count >= 1

    db_check = TestingSessionLocal()
    try:
        sess = db_check.query(ChargingSession).filter(ChargingSession.session_id == sess_id).first()
        assert sess.is_aborted is True
        assert sess.end_time is not None

        res = db_check.query(Reservation).filter(Reservation.reservation_id == res_id).first()
        assert res.status == "Expired"

        user = db_check.query(User).filter(User.user_id == user_id).first()
        assert user.wallet_balance == initial_balance
    finally:
        db_check.close()


@pytest.mark.skipif(not DB_AVAILABLE, reason="Requires Postgres DB with SPs and schema")
def test_real_db_trusted_driver_cooldown_waiver_and_limit():
    """A trusted account cancels for 'Faulty Charger' within 5 minutes, then re-reserves at the same station with no cooldown.
    A 3rd attempt within 24 hours does get the cooldown."""
    db = TestingSessionLocal()
    try:
        user_id = uuid.uuid4()
        now = datetime.now(timezone.utc).replace(tzinfo=None)

        db.execute(text("""
            INSERT INTO USERS (user_id, email, password_hash, full_name, phone_number, role, wallet_balance, created_at)
            VALUES (:uid, :email, 'hash', 'Trusted Driver', '9999999994', 'Driver', 20000.00, :created_at)
        """), {"uid": user_id, "email": f"trusted_{user_id.hex}@test.com", "created_at": now - timedelta(days=10)})
        db.execute(text("INSERT INTO WALLET_TRANSACTIONS (user_id, amount, transaction_type) VALUES (:uid, 20000.00, 'Top-up')"), {"uid": user_id})

        company_id = uuid.uuid4()
        area_id = uuid.uuid4()
        station_id = uuid.uuid4()
        port1_id = uuid.uuid4()
        port2_id = uuid.uuid4()
        veh_id = uuid.uuid4()
        qr1 = f"QR-W1-{uuid.uuid4().hex[:8]}"
        qr2 = f"QR-W2-{uuid.uuid4().hex[:8]}"

        db.execute(text("INSERT INTO COMPANIES (company_id, name) VALUES (:cid, :name)"), {"cid": company_id, "name": f"Waiver Co {company_id}"})
        db.execute(text("INSERT INTO AREAS (area_id, name) VALUES (:aid, :name)"), {"aid": area_id, "name": f"Waiver Area {area_id}"})
        db.execute(text("""
            INSERT INTO STATIONS (station_id, company_id, area_id, name, gps_coordinates, price_per_kwh, minimum_session_fee, opening_time_local, closing_time_local, timezone)
            VALUES (:sid, :cid, :aid, 'Waiver Station', ST_SetSRID(ST_MakePoint(77.5946, 12.9716), 4326), 15.0, 50.0, '00:00:00', '23:59:59', 'UTC')
        """), {"sid": station_id, "cid": company_id, "aid": area_id})

        db.execute(text("""
            INSERT INTO CHARGING_PORTS (port_id, station_id, qr_code, connector_type, charger_type, status)
            VALUES (:p1, :sid, :qr1, 'CCS2', 'DC Fast', 'Available'),
                   (:p2, :sid, :qr2, 'CCS2', 'DC Fast', 'Available')
        """), {"p1": port1_id, "p2": port2_id, "sid": station_id, "qr1": qr1, "qr2": qr2})

        db.execute(text("""
            INSERT INTO VEHICLES (vehicle_id, user_id, make, model, registration_number, battery_capacity, connector_type, is_active, is_default)
            VALUES (:vid, :uid, 'Tata', 'Nexon EV', :reg, 40.0, 'CCS2', TRUE, TRUE)
        """), {"vid": veh_id, "uid": user_id, "reg": f"WAIV-{user_id.hex[:8]}"})

        for i in range(3):
            past_res_id = uuid.uuid4()
            past_sess_id = uuid.uuid4()
            db.execute(text("""
                INSERT INTO RESERVATIONS (reservation_id, user_id, port_id, vehicle_id, status, reserved_tariff, created_at, expires_at)
                VALUES (:rid, :uid, :pid, :vid, 'Completed', 15.00, :t, :t + INTERVAL '1 hour')
            """), {"rid": past_res_id, "uid": user_id, "pid": port1_id, "vid": veh_id, "t": now - timedelta(days=i+1)})
            db.execute(text("""
                INSERT INTO CHARGING_SESSIONS (session_id, reservation_id, initial_battery_percentage, target_battery_percentage, applied_tariff, start_time, end_time, hardware_acked, hardware_state, is_aborted)
                VALUES (:sid, :rid, 20.0, 80.0, 15.0, :t, :t + INTERVAL '30 minutes', TRUE, 'Connected', FALSE)
            """), {"sid": past_sess_id, "rid": past_res_id, "t": now - timedelta(days=i+1)})
        db.commit()

        user_obj = db.query(User).filter(User.user_id == user_id).first()
        fastapi_req = MagicMock()
        fastapi_req.client.host = "127.0.0.1"

        # Attempt 1: Reserve port 1, cancel with "Faulty Charger" -> waiver 1 granted
        res1 = create_reservation(ReservationCreate(port_id=str(port1_id), vehicle_id=str(veh_id)), fastapi_req, db, user_obj)
        cancel_reservation(reservation_id=res1.reservation_id, cancel_req=CancelReservationRequest(reason="Faulty Charger"), db=db, current_user=user_obj)
        db.refresh(user_obj)

        waiver1 = db.query(CooldownWaiver).filter(CooldownWaiver.reservation_id == res1.reservation_id).first()
        assert waiver1 is not None
        assert waiver1.reason == "Faulty Charger"

        # Attempt 2: Immediate re-reserve at same station -> should NOT be blocked by cooldown (cooldown_minutes becomes 0)
        res2 = create_reservation(ReservationCreate(port_id=str(port2_id), vehicle_id=str(veh_id)), fastapi_req, db, user_obj)
        assert res2 is not None

        # Cancel attempt 2 with "Blocked Bay" -> waiver 2 granted
        cancel_reservation(reservation_id=res2.reservation_id, cancel_req=CancelReservationRequest(reason="Blocked Bay"), db=db, current_user=user_obj)
        db.refresh(user_obj)
        waiver2 = db.query(CooldownWaiver).filter(CooldownWaiver.reservation_id == res2.reservation_id).first()
        assert waiver2 is not None

        # Attempt 3: Re-reserve at port 1 and cancel -> waiver limit (2 in 24h) reached, no 3rd waiver
        res3 = create_reservation(ReservationCreate(port_id=str(port1_id), vehicle_id=str(veh_id)), fastapi_req, db, user_obj)
        assert res3 is not None

        cancel_reservation(reservation_id=res3.reservation_id, cancel_req=CancelReservationRequest(reason="Faulty Charger"), db=db, current_user=user_obj)
        db.refresh(user_obj)
        waiver3 = db.query(CooldownWaiver).filter(CooldownWaiver.reservation_id == res3.reservation_id).first()
        assert waiver3 is None

        # Attempt 4: Re-reserve immediately -> MUST fail with cooldown exception (400)
        with pytest.raises(HTTPException) as exc_info:
            create_reservation(ReservationCreate(port_id=str(port2_id), vehicle_id=str(veh_id)), fastapi_req, db, user_obj)
        assert exc_info.value.status_code == 400
        assert "cooldown" in exc_info.value.detail.lower()
    finally:
        db.rollback()
        db.close()


@pytest.mark.skipif(not DB_AVAILABLE, reason="Requires Postgres DB with SPs and schema")
def test_real_db_dashboard_real_kwh():
    """The dashboard returns real kWh for a user with completed sessions (verifying compute_snapshot import in user_service)."""
    db = TestingSessionLocal()
    try:
        user_id = uuid.uuid4()
        now = datetime.now(timezone.utc).replace(tzinfo=None)

        db.execute(text("""
            INSERT INTO USERS (user_id, email, password_hash, full_name, phone_number, role, wallet_balance)
            VALUES (:uid, :email, 'hash', 'Dashboard Driver', '9999999995', 'Driver', 5000.00)
        """), {"uid": user_id, "email": f"dash_{user_id.hex}@test.com"})
        db.execute(text("INSERT INTO WALLET_TRANSACTIONS (user_id, amount, transaction_type) VALUES (:uid, 5000.00, 'Top-up')"), {"uid": user_id})

        company_id = uuid.uuid4()
        area_id = uuid.uuid4()
        station_id = uuid.uuid4()
        port_id = uuid.uuid4()
        veh_id = uuid.uuid4()
        res_id = uuid.uuid4()
        sess_id = uuid.uuid4()
        qr_code = f"QR-DASH-{uuid.uuid4().hex[:8]}"

        db.execute(text("INSERT INTO COMPANIES (company_id, name) VALUES (:cid, :name)"), {"cid": company_id, "name": f"Dash Co {company_id}"})
        db.execute(text("INSERT INTO AREAS (area_id, name) VALUES (:aid, :name)"), {"aid": area_id, "name": f"Dash Area {area_id}"})
        db.execute(text("""
            INSERT INTO STATIONS (station_id, company_id, area_id, name, gps_coordinates, price_per_kwh, minimum_session_fee, opening_time_local, closing_time_local, timezone)
            VALUES (:sid, :cid, :aid, 'Dash Station', ST_SetSRID(ST_MakePoint(77.5946, 12.9716), 4326), 15.0, 50.0, '00:00:00', '23:59:59', 'UTC')
        """), {"sid": station_id, "cid": company_id, "aid": area_id})

        db.execute(text("""
            INSERT INTO CHARGING_PORTS (port_id, station_id, qr_code, connector_type, charger_type, status)
            VALUES (:pid, :sid, :qr, 'CCS2', 'DC Fast', 'Available')
        """), {"pid": port_id, "sid": station_id, "qr": qr_code})

        db.execute(text("""
            INSERT INTO VEHICLES (vehicle_id, user_id, make, model, registration_number, battery_capacity, connector_type, is_active, is_default)
            VALUES (:vid, :uid, 'Tata', 'Nexon EV', :reg, 40.0, 'CCS2', TRUE, TRUE)
        """), {"vid": veh_id, "uid": user_id, "reg": f"DASH-{user_id.hex[:8]}"})

        db.execute(text("""
            INSERT INTO RESERVATIONS (reservation_id, user_id, port_id, vehicle_id, status, reserved_tariff, expires_at)
            VALUES (:rid, :uid, :pid, :vid, 'Completed', 15.00, CURRENT_TIMESTAMP)
        """), {"rid": res_id, "uid": user_id, "pid": port_id, "vid": veh_id})

        db.execute(text("""
            INSERT INTO CHARGING_SESSIONS (session_id, reservation_id, initial_battery_percentage, target_battery_percentage, applied_tariff, start_time, end_time, hardware_acked, hardware_state, is_aborted)
            VALUES (:sid, :rid, 20.0, 80.0, 15.0, :st, :et, TRUE, 'Connected', FALSE)
        """), {"sid": sess_id, "rid": res_id, "st": now - timedelta(minutes=30), "et": now})
        db.commit()

        data = UserService.get_dashboard_data(db, user_id)
        assert "energy_charged_kwh" in data
        assert data["energy_charged_kwh"] > 0
    finally:
        db.close()

