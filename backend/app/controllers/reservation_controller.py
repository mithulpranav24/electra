from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func, or_
from typing import List
from decimal import Decimal
import uuid

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.models.station import Station, ChargingPort
from app.models.reservation import Reservation
from app.models.wallet import WalletTransaction
from app.schemas.reservation_schema import ReservationCreate, ReservationResponse

router = APIRouter(prefix="/reservations", tags=["Reservations"])

ESCROW_AMOUNT = Decimal("200.00")

@router.post("", response_model=ReservationResponse)
def create_reservation(
    request: ReservationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.role != "Driver":
        raise HTTPException(status_code=403, detail="Only drivers can reserve ports")
        
    # Check if user already has an active reservation
    existing = db.query(Reservation).filter(
        Reservation.user_id == current_user.user_id,
        Reservation.status.in_(["Confirmed", "Active"])
    ).first()
    
    if existing:
        raise HTTPException(status_code=400, detail="You already have an active reservation")
        
    # Check wallet balance
    if current_user.wallet_balance < ESCROW_AMOUNT:
        raise HTTPException(status_code=400, detail=f"Insufficient wallet balance. Minimum ₹{ESCROW_AMOUNT} required for escrow.")
        
    # Start transaction to securely lock port
    try:
        # Lock port
        port = db.query(ChargingPort).with_for_update().filter(
            ChargingPort.port_id == request.port_id
        ).first()
        
        if not port:
            raise HTTPException(status_code=404, detail="Port not found")
            
        if port.status != "Available":
            raise HTTPException(status_code=409, detail="Port is not available")
            
        # Deduct escrow
        escrow_tx = WalletTransaction(
            user_id=current_user.user_id,
            amount=-ESCROW_AMOUNT,
            transaction_type="Escrow Hold"
        )
        db.add(escrow_tx)
        
        # Update port status
        port.status = "Reserved"
        
        # Create reservation
        reservation = Reservation(
            user_id=current_user.user_id,
            vehicle_id=request.vehicle_id,
            port_id=port.port_id,
            status="Confirmed",
            reserved_tariff=port.station.price_per_kwh
        )
        db.add(reservation)
        
        db.commit()
        db.refresh(reservation)
        
        # Update escrow tx reference_id
        escrow_tx.reference_id = reservation.reservation_id
        db.commit()
        
        return reservation
    except HTTPException as e:
        db.rollback()
        raise e
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/active", response_model=List[ReservationResponse])
def get_active_reservations(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    reservations = db.query(Reservation).filter(
        Reservation.user_id == current_user.user_id,
        Reservation.status.in_(["Confirmed", "Active"])
    ).all()
    return reservations

@router.post("/{reservation_id}/cancel")
def cancel_reservation(
    reservation_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        reservation = db.query(Reservation).with_for_update().filter(
            Reservation.reservation_id == reservation_id,
            Reservation.user_id == current_user.user_id
        ).first()
        
        if not reservation:
            raise HTTPException(status_code=404, detail="Reservation not found")
            
        if reservation.status != "Confirmed":
            raise HTTPException(status_code=400, detail="Only confirmed reservations can be cancelled")
            
        # Free port
        port = db.query(ChargingPort).with_for_update().filter(
            ChargingPort.port_id == reservation.port_id
        ).first()
        if port:
            port.status = "Available"
            
        # Refund escrow
        refund_tx = WalletTransaction(
            user_id=current_user.user_id,
            amount=ESCROW_AMOUNT,
            transaction_type="Escrow Release",
            reference_id=reservation.reservation_id
        )
        db.add(refund_tx)
        
        # Cancel reservation
        reservation.status = "Cancelled"
        reservation.cancellation_reason = "User cancelled"
        
        db.commit()
        return {"success": True, "message": "Reservation cancelled and escrow refunded"}
        
    except HTTPException as e:
        db.rollback()
        raise e
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
