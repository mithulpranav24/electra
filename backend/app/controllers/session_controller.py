from typing import Optional
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, Request, HTTPException

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.models.session import ChargingSession
from app.schemas.invoice_schema import InvoiceResponse
from app.schemas.session_schema import (
    ChallengePortRequest,
    ChallengePortResponse,
    SessionStartRequest,
    SessionStatusResponse,
)
from app.services.session_service import SessionService
from sqlalchemy.orm import Session

from app.core.response import UniformResponseRoute

router = APIRouter(route_class=UniformResponseRoute, prefix="/sessions", tags=["Sessions"])


@router.post("/start", response_model=SessionStatusResponse)
def start_session(
    request: SessionStartRequest,
    fastapi_req: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ip_address = fastapi_req.client.host if fastapi_req.client else "unknown"
    SessionService.start_session(
        db, current_user, request.reservation_id,
        request.initial_battery_percentage, request.target_battery_percentage, ip_address,
        qr_code=request.qr_code,
        latitude=request.latitude,
        longitude=request.longitude,
    )
    return SessionService.get_active_session_status(db, current_user)


@router.get("/active", response_model=Optional[SessionStatusResponse])
def get_active_session(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return SessionService.get_active_session_status(db, current_user)


@router.post("/stop", response_model=InvoiceResponse)
def stop_session(
    fastapi_req: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ip_address = fastapi_req.client.host if fastapi_req.client else "unknown"
    return SessionService.stop_session(db, current_user, ip_address)


@router.post("/{session_id}/hardware-ack")
def hardware_ack(
    session_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """FR-15: Mock hardware layer calls this within 60 seconds to confirm the charger is active.
    Resets the port's consecutive_handshake_failures counter on success, records start_time, and starts billing."""
    from app.models.station import ChargingPort
    from app.models.reservation import Reservation

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    session = db.query(ChargingSession).filter(ChargingSession.session_id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    reservation = db.query(Reservation).filter(
        Reservation.reservation_id == session.reservation_id
    ).first()
    if not reservation:
        raise HTTPException(status_code=404, detail="Reservation not found")

    if current_user.role not in ["Admin", "Operator"] and reservation.user_id != current_user.user_id:
        raise HTTPException(status_code=403, detail="Forbidden: You cannot acknowledge another driver's session")

    if session.hardware_acked:
        return {"success": True, "message": "Already acknowledged"}
    if session.hardware_ack_deadline and now > session.hardware_ack_deadline:
        raise HTTPException(status_code=408, detail="Hardware ack deadline expired. Session will be aborted by the background worker.")

    session.hardware_acked = True
    session.hardware_state = "Connected"
    session.start_time = now  # Billing strictly begins from the moment hardware handshake is acknowledged

    # Reset consecutive failures on the port on a successful ack
    port = db.query(ChargingPort).filter(ChargingPort.port_id == reservation.port_id).first()
    if port:
        port.consecutive_handshake_failures = 0

    db.commit()
    return {"success": True, "message": "Hardware handshake confirmed. Billing has begun."}


@router.post("/{session_id}/mock-disconnect")
def mock_disconnect(
    session_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Mocks physical vehicle disconnect (State A) on an active session to test ghost session resolution."""
    from app.models.reservation import Reservation

    session = db.query(ChargingSession).filter(ChargingSession.session_id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    reservation = db.query(Reservation).filter(
        Reservation.reservation_id == session.reservation_id
    ).first()
    if not reservation:
        raise HTTPException(status_code=404, detail="Reservation not found")

    if current_user.role not in ["Admin", "Operator"] and reservation.user_id != current_user.user_id:
        raise HTTPException(status_code=403, detail="Forbidden: You cannot modify another driver's session")

    session.hardware_state = "Disconnected"
    db.commit()
    return {"success": True, "message": "Hardware state set to Disconnected (State A)"}



@router.post("/challenge/{port_id}", response_model=ChallengePortResponse)
def challenge_port(
    port_id: UUID,
    request: ChallengePortRequest,
    fastapi_req: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """FR-32: Ghost Session Resolution / Port Challenge.
    If a port shows 'Charging' but vehicle is gone, challenger scans port QR within 200m.
    If hardware reports disconnected, terminates ghost session and grants 15-min reservation or waitlist promotion."""
    ip_address = fastapi_req.client.host if fastapi_req.client else "unknown"
    return SessionService.challenge_port(
        db,
        current_user,
        port_id,
        latitude=request.latitude,
        longitude=request.longitude,
        qr_code=request.qr_code,
        vehicle_id=request.vehicle_id,
        ip_address=ip_address,
    )


