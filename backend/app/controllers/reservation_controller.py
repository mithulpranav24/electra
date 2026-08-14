from fastapi import APIRouter, Depends, HTTPException, Request, status
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
from app.models.vehicle import Vehicle
from app.models.audit import AuditLog
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
            from app.models.transient import Waitlist
            from app.models.vehicle import Vehicle
            waitlist_entry = db.query(Waitlist).join(Vehicle).filter(
                Waitlist.station_id == port.station_id,
                Waitlist.offered_port_id.is_(None),
                Vehicle.connector_type == port.connector_type
            ).order_by(Waitlist.joined_at.asc()).first()

            if waitlist_entry:
                port.status = "Pending Waitlist"
                waitlist_entry.offered_port_id = port.port_id
                waitlist_entry.offered_at = func.now()
            else:
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
    fastapi_req: Request,
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
        from sqlalchemy import text
        ip_address = fastapi_req.client.host if fastapi_req.client else "unknown"
        
        # If port_id is not provided, automatically recommend an optimal port
        target_port_id = request.port_id
        if not target_port_id:
            if not request.station_id:
                raise HTTPException(status_code=400, detail="Must provide either station_id or port_id")
                
            from app.models.vehicle import Vehicle
            vehicle = db.query(Vehicle).filter(Vehicle.vehicle_id == request.vehicle_id).first()
            if not vehicle:
                raise HTTPException(status_code=404, detail="Vehicle not found")
                
            available_port = db.query(ChargingPort).filter(
                ChargingPort.station_id == request.station_id,
                ChargingPort.status == "Available",
                ChargingPort.is_active == True,
                ChargingPort.connector_type == vehicle.connector_type,
                ChargingPort.has_health_warning == False,
                ChargingPort.has_blocked_warning == False
            ).first()
            
            if not available_port:
                raise HTTPException(status_code=404, detail="No available ports matching your vehicle at this station")
                
            target_port_id = str(available_port.port_id)

        # Call the stored procedure to enforce concurrency and hierarchy
        db.execute(
            text("""
                CALL sp_CreateReservation(
                    :p_user_id,
                    :p_port_id,
                    :p_vehicle_id,
                    :p_grace_period_minutes,
                    :p_cooldown_minutes,
                    :p_ip_address
                )
            """),
            {
                "p_user_id": current_user.user_id,
                "p_port_id": target_port_id,
                "p_vehicle_id": request.vehicle_id,
                "p_grace_period_minutes": SLA_TIMEOUT_MINUTES,
                "p_cooldown_minutes": 60, # Standard cooldown
                "p_ip_address": str(ip_address)
            }
        )
        
        # After successful SP execution, fetch the newly created reservation
        # The SP commits the transaction implicitly? No, SPs in Postgres participate in the current transaction.
        # But wait, we shouldn't commit here if the SP fails.
        db.commit()
        
        new_res = db.query(Reservation).filter(
            Reservation.user_id == current_user.user_id,
            Reservation.port_id == request.port_id,
            Reservation.status == "Confirmed"
        ).order_by(Reservation.created_at.desc()).first()
        
        if not new_res:
            raise HTTPException(status_code=500, detail="Failed to retrieve created reservation")
            
        audit = AuditLog(
            user_id=current_user.user_id,
            action="Reservation Created",
            entity_type="RESERVATIONS",
            entity_id=new_res.reservation_id,
            details={"port_id": str(target_port_id), "vehicle_id": str(request.vehicle_id)},
            ip_address=str(ip_address)
        )
        db.add(audit)
        db.commit()

        return new_res

    except Exception as e:
        db.rollback()
        # Parse common postgres exceptions from SP
        error_msg = str(e)
        if "Insufficient wallet balance" in error_msg:
            raise HTTPException(status_code=400, detail=f"Insufficient wallet balance. Minimum ₹{ESCROW_AMOUNT} required for escrow.")
        elif "Port is not Available" in error_msg:
            raise HTTPException(status_code=409, detail="Port is not available")
        elif "User already has an active reservation" in error_msg:
            raise HTTPException(status_code=400, detail="You already have an active reservation")
        elif "Port not found" in error_msg:
            raise HTTPException(status_code=404, detail="Port not found")
        else:
            raise HTTPException(status_code=400, detail=error_msg)

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
    fastapi_req: Request,
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

        # Step 2: Acquire locks in correct order: STATIONS -> CHARGING_PORTS -> VEHICLES -> USERS -> RESERVATIONS
        station = db.query(Station).join(ChargingPort).with_for_update().filter(
            ChargingPort.port_id == reservation_read.port_id
        ).first()

        port = db.query(ChargingPort).with_for_update().filter(
            ChargingPort.port_id == reservation_read.port_id
        ).first()

        vehicle = db.query(Vehicle).with_for_update().filter(
            Vehicle.vehicle_id == reservation_read.vehicle_id
        ).first()

        user = db.query(User).with_for_update().filter(
            User.user_id == current_user.user_id
        ).first()

        reservation = db.query(Reservation).with_for_update().filter(
            Reservation.reservation_id == reservation_id,
            Reservation.user_id == current_user.user_id
        ).first()

        # Re-check status after acquiring lock (guard against race conditions)
        if reservation.status != "Confirmed":
            raise HTTPException(status_code=400, detail="Only confirmed reservations can be cancelled")

        # --- DD-24: Determine if escrow should be refunded or forfeited ---
        
        # Check if user is a Trusted Account (>100 successful sessions)
        from app.models.session import ChargingSession
        successful_sessions = db.query(ChargingSession).join(Reservation).filter(
            Reservation.user_id == current_user.user_id,
            ChargingSession.end_time.isnot(None),
            ChargingSession.status == "Completed"
        ).count()
        is_trusted_account = successful_sessions > 100

        cancel_window_minutes = 10 if is_trusted_account else FREE_CANCEL_HOLD_MINUTES
        hold_duration_minutes = (now - reservation.created_at).total_seconds() / 60
        is_short_hold = hold_duration_minutes < cancel_window_minutes

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
            response_message = f"Reservation cancelled and escrow refunded. (Trusted: {is_trusted_account})"
        else:
            # Escrow is forfeited as cancellation penalty
            cancel_reason = "User cancelled (Penalty)"
            wallet_tx = WalletTransaction(
                user_id=current_user.user_id,
                amount=Decimal("0.00"),  # Escrow already deducted; no release
                transaction_type="Escrow Forfeited (Cancellation Penalty)",
                reference_id=reservation.reservation_id
            )
            response_message = f"Reservation cancelled. Escrow of ₹1000 has been forfeited as a cancellation penalty per DD-24. (Trusted: {is_trusted_account})"

        db.add(wallet_tx)

        # Free port
        if port:
            port.status = "Available"

        # Cancel reservation
        reservation.status = "Cancelled"
        reservation.cancellation_reason = cancel_reason
        reservation.status_updated_at = now

        audit = AuditLog(
            user_id=current_user.user_id,
            action="Reservation Cancelled",
            entity_type="RESERVATIONS",
            entity_id=reservation.reservation_id,
            details={"reason": cancel_reason},
            ip_address=fastapi_req.client.host if fastapi_req.client else "unknown"
        )
        db.add(audit)

        db.commit()
        return {"success": True, "message": response_message}

    except HTTPException as e:
        db.rollback()
        raise e
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
