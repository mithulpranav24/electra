from typing import Optional

from fastapi import APIRouter, Depends, Request

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.schemas.invoice_schema import InvoiceResponse
from app.schemas.session_schema import SessionStartRequest, SessionStatusResponse
from app.services.session_service import SessionService
from sqlalchemy.orm import Session

router = APIRouter(prefix="/sessions", tags=["Sessions"])


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
