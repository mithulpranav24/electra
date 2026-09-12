from datetime import timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user, verify_not_banned
from app.models.user import User
from app.schemas.reservation_schema import ReservationResponse
from app.schemas.waitlist_schema import WaitlistJoinRequest, WaitlistStatusResponse
from app.services.waitlist_service import OFFER_WINDOW_SECONDS, WaitlistService

router = APIRouter(prefix="/waitlist", tags=["Waitlist"])


def _to_status_response(db: Session, entry) -> WaitlistStatusResponse:
    position = WaitlistService.get_queue_position(db, entry)
    offer_expires_at = entry.offered_at + timedelta(seconds=OFFER_WINDOW_SECONDS) if entry.offered_at else None
    return WaitlistStatusResponse(
        waitlist_id=entry.waitlist_id,
        station_id=entry.station_id,
        vehicle_id=entry.vehicle_id,
        joined_at=entry.joined_at,
        joined_tariff=entry.joined_tariff,
        joined_minimum_fee=entry.joined_minimum_fee,
        position=position,
        offered_port_id=entry.offered_port_id,
        offered_at=entry.offered_at,
        offer_expires_at=offer_expires_at,
    )


@router.post("", response_model=WaitlistStatusResponse)
def join_waitlist(
    request: WaitlistJoinRequest,
    fastapi_req: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(verify_not_banned),
):
    if current_user.role != "Driver":
        raise HTTPException(status_code=403, detail="Only drivers can join a waitlist")

    ip_address = fastapi_req.client.host if fastapi_req.client else "unknown"
    entry = WaitlistService.join_waitlist(db, current_user, request, ip_address)
    return _to_status_response(db, entry)


@router.get("/status", response_model=Optional[WaitlistStatusResponse])
def get_waitlist_status(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    entry = WaitlistService.get_status(db, current_user)
    if not entry:
        return None
    return _to_status_response(db, entry)


@router.delete("")
def leave_waitlist(
    fastapi_req: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ip_address = fastapi_req.client.host if fastapi_req.client else "unknown"
    WaitlistService.leave_waitlist(db, current_user, ip_address)
    return {"success": True, "message": "You have left the waitlist"}


@router.post("/{waitlist_id}/confirm", response_model=ReservationResponse)
def confirm_waitlist_offer(
    waitlist_id: str,
    fastapi_req: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(verify_not_banned),
):
    ip_address = fastapi_req.client.host if fastapi_req.client else "unknown"
    return WaitlistService.confirm_offer(db, current_user, waitlist_id, ip_address)
