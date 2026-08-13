from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func, or_
from typing import List
from decimal import Decimal
import uuid
from datetime import datetime, timedelta, timezone

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.models.station import Station, ChargingPort
from app.models.reservation import Reservation
from app.models.wallet import WalletTransaction
from app.schemas.reservation_schema import ReservationCreate, ReservationResponse

router = APIRouter(prefix="/reservations", tags=["Reservations"])

# DD-23 / DD-24: Escrow pre-authorization must be 1000 INR
ESCROW_AMOUNT = Decimal("1000.00")
SLA_TIMEOUT_MINUTES = 15
# DD-24: Free cancellation window — reservation held for less than this is eligible
FREE_CANCEL_HOLD_MINUTES = 5

def clean_expired_reservations(db: Session):
    """
    DD-02: Expire reservations by checking CURRENT_TIMESTAMP against expires_at,
    not by checking created_at age. This correctly handles extended reservations.
    """
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    expired = db.query(Reservation).filter(
        Reservation.status == "Confirmed",
        Reservation.expires_at < now
    ).with_for_update().all()

    for res in expired:
        res.status = "Cancelled"
        res.cancellation_reason = "SLA Timeout (No Show)"

        # Free port — lock order: CHARGING_PORTS before RESERVATIONS (already locked above)
        port = db.query(ChargingPort).with_for_update().filter(
            ChargingPort.port_id == res.port_id
        ).first()
        if port:
            port.status = "Available"

        # SLA timeout: escrow is forfeited (no refund) per DD-24
        penalty_tx = WalletTransaction(
            user_id=res.user_id,
            amount=-Decimal("0.00"),  # escrow was already deducted; no release
            transaction_type="Escrow Forfeited (SLA Timeout)",
            reference_id=res.reservation_id
        )
        db.add(penalty_tx)

    if expired:
        db.commit()

@router.post("", response_model=ReservationResponse)
def create_reservation(
    request: ReservationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    clean_expired_reservations(db)

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
        raise HTTPException(
            status_code=400,
            detail=f"Insufficient wallet balance. Minimum ₹{ESCROW_AMOUNT} required for escrow."
        )

    try:
        # DD-24 Lock order: STATIONS -> CHARGING_PORTS -> VEHICLES -> USERS -> RESERVATIONS
        # Lock port (CHARGING_PORTS)
        port = db.query(ChargingPort).with_for_update().filter(
            ChargingPort.port_id == request.port_id
        ).first()

        if not port:
            raise HTTPException(status_code=404, detail="Port not found")

        if port.status != "Available":
            raise HTTPException(status_code=409, detail="Port is not available")

        # Deduct escrow hold
        escrow_tx = WalletTransaction(
            user_id=current_user.user_id,
            amount=-ESCROW_AMOUNT,
            transaction_type="Escrow Hold"
        )
        db.add(escrow_tx)

        # Update port status
        port.status = "Reserved"

        # Create reservation with expires_at (DD-02)
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        reservation = Reservation(
            user_id=current_user.user_id,
            vehicle_id=request.vehicle_id,
            port_id=port.port_id,
            status="Confirmed",
            reserved_tariff=port.station.price_per_kwh,
            expires_at=now + timedelta(minutes=SLA_TIMEOUT_MINUTES)
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
    clean_expired_reservations(db)

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
    """
    DD-24: Cancellation Penalty Logic
    Escrow is FORFEITED unless ALL of the following are true:
      (A) Reservation was held for < FREE_CANCEL_HOLD_MINUTES (5 min), AND
          it is the user's 1st free cancellation in the last 24 hours,
      OR
      (B) A valid 'Faulty Charger' exemption claim exists for this reservation's port.
    """
    try:
        now = datetime.now(timezone.utc).replace(tzinfo=None)

        # DD-24 Lock order: CHARGING_PORTS -> USERS -> RESERVATIONS
        # Step 1: Optimistic read to get port_id without locking yet
        reservation_read = db.query(Reservation).filter(
            Reservation.reservation_id == reservation_id,
            Reservation.user_id == current_user.user_id
        ).first()

        if not reservation_read:
            raise HTTPException(status_code=404, detail="Reservation not found")

        if reservation_read.status != "Confirmed":
            raise HTTPException(status_code=400, detail="Only confirmed reservations can be cancelled")

        # Step 2: Acquire locks in correct order: CHARGING_PORTS -> RESERVATIONS
        port = db.query(ChargingPort).with_for_update().filter(
            ChargingPort.port_id == reservation_read.port_id
        ).first()

        reservation = db.query(Reservation).with_for_update().filter(
            Reservation.reservation_id == reservation_id,
            Reservation.user_id == current_user.user_id
        ).first()

        # Re-check status after acquiring lock (guard against race conditions)
        if reservation.status != "Confirmed":
            raise HTTPException(status_code=400, detail="Only confirmed reservations can be cancelled")

        # --- DD-24: Determine if escrow should be refunded or forfeited ---
        hold_duration_minutes = (now - reservation.created_at).total_seconds() / 60
        is_short_hold = hold_duration_minutes < FREE_CANCEL_HOLD_MINUTES

        # Check if user has used their free cancellation in the last 24 hours
        twenty_four_hours_ago = now - timedelta(hours=24)
        prior_free_cancels = db.query(Reservation).filter(
            Reservation.user_id == current_user.user_id,
            Reservation.status == "Cancelled",
            Reservation.cancellation_reason == "User cancelled (Free)",
            Reservation.status_updated_at >= twenty_four_hours_ago
        ).count()
        is_first_free_cancel = prior_free_cancels == 0

        # Check for valid Faulty Charger exemption claim for this port
        from app.models.transient import FaultExemptionClaim
        faulty_charger_claim = db.query(FaultExemptionClaim).filter(
            FaultExemptionClaim.user_id == current_user.user_id,
            FaultExemptionClaim.port_id == reservation.port_id
        ).first()
        is_faulty_charger = faulty_charger_claim is not None

        # Apply refund or penalty
        if (is_short_hold and is_first_free_cancel) or is_faulty_charger:
            # Eligible for escrow refund
            cancel_reason = "User cancelled (Free)"
            wallet_tx = WalletTransaction(
                user_id=current_user.user_id,
                amount=ESCROW_AMOUNT,
                transaction_type="Escrow Release",
                reference_id=reservation.reservation_id
            )
            response_message = "Reservation cancelled and escrow refunded."
        else:
            # Escrow is forfeited as cancellation penalty
            cancel_reason = "User cancelled (Penalty)"
            wallet_tx = WalletTransaction(
                user_id=current_user.user_id,
                amount=Decimal("0.00"),  # Escrow already deducted; no release
                transaction_type="Escrow Forfeited (Cancellation Penalty)",
                reference_id=reservation.reservation_id
            )
            response_message = "Reservation cancelled. Escrow of ₹1000 has been forfeited as a cancellation penalty per DD-24."

        db.add(wallet_tx)

        # Free port
        if port:
            port.status = "Available"

        # Cancel reservation
        reservation.status = "Cancelled"
        reservation.cancellation_reason = cancel_reason
        reservation.status_updated_at = now

        db.commit()
        return {"success": True, "message": response_message}

    except HTTPException as e:
        db.rollback()
        raise e
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
