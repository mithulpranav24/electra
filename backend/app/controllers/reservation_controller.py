from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session
from sqlalchemy import or_
from typing import List, Optional
from decimal import Decimal
import uuid
from datetime import datetime, timedelta, timezone

from app.core.database import get_db
from app.core.dependencies import get_current_user, verify_not_banned
from app.models.user import User
from app.models.station import Station, ChargingPort
from app.models.reservation import Reservation
from app.models.wallet import WalletTransaction
from app.models.vehicle import Vehicle
from app.schemas.reservation_schema import ReservationCreate, ReservationResponse, CancelReservationRequest
from app.services.audit_service import log_audit_event
from app.services.notification_service import create_notification
from app.services.waitlist_service import WaitlistService

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

    This now also runs autonomously from the Celery `expire-reservations` beat
    task every minute (in addition to the opportunistic inline calls below), so
    each expiry MUST be its own atomic, correctly-ordered transaction (Architecture.md
    3.4.1: STATIONS FOR SHARE -> CHARGING_PORTS FOR UPDATE -> USERS FOR UPDATE ->
    RESERVATIONS FOR UPDATE) with its own commit, or it will eventually deadlock
    against sp_ConfirmWaitlist / cancel_reservation, which lock in that same order.
    """
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    # Optimistic read only - no locks yet. Ordered by port_id (ascending PK, the
    # Tier-2 resource each expiry ultimately locks) so concurrent runs converge
    # on the same lock acquisition order.
    expired_ids = [
        row[0]
        for row in db.query(Reservation.reservation_id)
        .filter(Reservation.status == "Confirmed", Reservation.expires_at < now)
        .order_by(Reservation.port_id.asc())
        .all()
    ]

    for reservation_id in expired_ids:
        optimistic = db.query(Reservation).filter(Reservation.reservation_id == reservation_id).first()
        if not optimistic or optimistic.status != "Confirmed":
            continue

        # Tier 1: STATIONS FOR SHARE (read-only validation, of=Station so the join
        # doesn't also put CHARGING_PORTS under FOR SHARE ahead of its FOR UPDATE below)
        db.query(Station).join(ChargingPort).with_for_update(read=True, of=Station).filter(
            ChargingPort.port_id == optimistic.port_id
        ).first()
        # Tier 2: CHARGING_PORTS
        port = db.query(ChargingPort).with_for_update().filter(ChargingPort.port_id == optimistic.port_id).first()
        # Tier 3: USERS
        db.query(User).with_for_update().filter(User.user_id == optimistic.user_id).first()
        # Tier 4: RESERVATIONS - re-validate under lock (another request may have
        # cancelled/extended it in the meantime)
        res = db.query(Reservation).with_for_update().filter(Reservation.reservation_id == reservation_id).first()

        if not res or res.status != "Confirmed" or res.expires_at >= now:
            db.rollback()
            continue

        res.status = "Cancelled"
        res.cancellation_reason = "SLA Timeout (No Show)"

        if port:
            candidate = WaitlistService.find_candidate_waitlist_entry(db, port.station_id, port.connector_type, port.port_id)
            WaitlistService.apply_promotion_or_release(db, port, candidate)

        # SLA timeout: escrow is forfeited (no refund) per DD-24
        penalty_tx = WalletTransaction(
            user_id=res.user_id,
            amount=-Decimal("0.00"),  # escrow was already deducted; no release
            transaction_type="Escrow Forfeited (SLA Timeout)",
            reference_id=res.reservation_id
        )
        db.add(penalty_tx)
        create_notification(
            db,
            res.user_id,
            "Reservation expired",
            "Your reservation expired because check-in wasn't completed within 15 minutes. The escrow was forfeited per the no-show policy.",
            commit=False,
        )
        log_audit_event(
            db,
            user_id=res.user_id,
            action="Reservation Cancelled",
            entity_type="RESERVATIONS",
            entity_id=res.reservation_id,
            details={"reason": res.cancellation_reason},
            ip_address="system",
            commit=False,
        )
        db.commit()

@router.post("", response_model=ReservationResponse)
def create_reservation(
    request: ReservationCreate,
    fastapi_req: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(verify_not_banned)
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

    # FR-9: Compute cooldown_minutes (trusted account waiver logic)
    # Target station determination:
    target_port_id = request.port_id
    target_station_id = request.station_id
    if target_port_id and not target_station_id:
        port_row = db.query(ChargingPort).filter(ChargingPort.port_id == target_port_id).first()
        if port_row:
            target_station_id = str(port_row.station_id)

    from app.models.transient import CooldownWaiver as _CW
    _now_ts = datetime.now(timezone.utc).replace(tzinfo=None)
    _60m_ago = _now_ts - timedelta(minutes=60)
    cooldown_minutes = 60
    if target_station_id:
        recent_cancellations = db.query(Reservation).join(ChargingPort).filter(
            Reservation.user_id == current_user.user_id,
            ChargingPort.station_id == target_station_id,
            Reservation.status == "Cancelled",
            Reservation.status_updated_at >= _60m_ago
        ).all()
        if recent_cancellations:
            cancellation_res_ids = [c.reservation_id for c in recent_cancellations]
            waived_count = db.query(_CW).filter(
                _CW.user_id == current_user.user_id,
                _CW.reservation_id.in_(cancellation_res_ids)
            ).count()
            if waived_count == len(recent_cancellations):
                cooldown_minutes = 0
        else:
            cooldown_minutes = 60


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
                ChargingPort.has_blocked_warning == False,
                ChargingPort.is_pending_maintenance == False
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
                "p_cooldown_minutes": cooldown_minutes,
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
            
        log_audit_event(
            db,
            user_id=current_user.user_id,
            action="Reservation Created",
            entity_type="RESERVATIONS",
            entity_id=new_res.reservation_id,
            details={"port_id": str(target_port_id), "vehicle_id": str(request.vehicle_id)},
            ip_address=str(ip_address),
        )
        create_notification(
            db,
            current_user.user_id,
            "Reservation confirmed",
            "Your reservation is confirmed. Check in within 15 minutes to start charging.",
        )

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
        elif "pending maintenance" in error_msg:
            raise HTTPException(status_code=409, detail="This port is pending maintenance and cannot be reserved")
        elif "scheduled maintenance" in error_msg:
            raise HTTPException(status_code=409, detail="This port has scheduled maintenance beginning too soon to complete check-in")
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
    cancel_req: Optional[CancelReservationRequest] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    DD-24: Cancellation Penalty Logic
    Escrow is FORFEITED unless ALL of the following are true:
      (A) Trusted driver cancelling for 'Faulty Charger' or 'Blocked Bay' within 5 min (up to 2 waivers/24h), OR
      (B) Reservation was held for < FREE_CANCEL_HOLD_MINUTES (5 min), AND
          it is the user's 1st free cancellation in the last 24 hours, OR
      (C) A valid 'Faulty Charger' exemption claim exists for this reservation's port.
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
        station = db.query(Station).join(ChargingPort).with_for_update(read=True, of=Station).filter(
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

        # Tier 3.5: WAITLIST
        waitlist_candidate = None
        if port:
            waitlist_candidate = WaitlistService.find_candidate_waitlist_entry(db, port.station_id, port.connector_type, port.port_id)

        reservation = db.query(Reservation).with_for_update().filter(
            Reservation.reservation_id == reservation_id,
            Reservation.user_id == current_user.user_id
        ).first()

        # Re-check status after acquiring lock (guard against race conditions)
        if reservation.status != "Confirmed":
            raise HTTPException(status_code=400, detail="Only confirmed reservations can be cancelled")

        # --- DD-24 / TASK-6: Determine if escrow should be refunded or forfeited ---
        from app.models.session import ChargingSession
        from app.models.transient import CooldownWaiver, FaultExemptionClaim

        successful_sessions = db.query(ChargingSession).join(Reservation).filter(
            Reservation.user_id == current_user.user_id,
            ChargingSession.end_time.isnot(None),
            ChargingSession.is_aborted.is_(False)
        ).count()
        account_age_days = (now - current_user.created_at).days if current_user.created_at else 0
        is_trusted_account = successful_sessions >= 3 and account_age_days >= 7

        hold_duration_minutes = (now - reservation.created_at).total_seconds() / 60
        twenty_four_hours_ago = now - timedelta(hours=24)

        reason_str = cancel_req.reason.strip() if (cancel_req and cancel_req.reason) else None
        is_fault_or_blocked = reason_str in ["Faulty Charger", "Blocked Bay"] if reason_str else False

        # TASK-6: Cooldown Waiver for Trusted Drivers
        waiver_applied = False
        if is_trusted_account and hold_duration_minutes <= 5.0 and is_fault_or_blocked:
            waiver_count = db.query(CooldownWaiver).filter(
                CooldownWaiver.user_id == current_user.user_id,
                CooldownWaiver.created_at >= twenty_four_hours_ago
            ).count()
            if waiver_count < 2:
                waiver_applied = True
                new_waiver = CooldownWaiver(
                    user_id=current_user.user_id,
                    reservation_id=reservation.reservation_id,
                    station_id=port.station_id if port else station.station_id,
                    reason=reason_str
                )
                db.add(new_waiver)

        cancel_window_minutes = 10 if is_trusted_account else FREE_CANCEL_HOLD_MINUTES
        is_short_hold = hold_duration_minutes < cancel_window_minutes

        prior_free_cancels = db.query(Reservation).filter(
            Reservation.user_id == current_user.user_id,
            Reservation.status == "Cancelled",
            Reservation.cancellation_reason.like("User cancelled%Free%"),
            Reservation.status_updated_at >= twenty_four_hours_ago
        ).count()
        is_first_free_cancel = prior_free_cancels == 0

        faulty_charger_claim = db.query(FaultExemptionClaim).filter(
            FaultExemptionClaim.user_id == current_user.user_id,
            FaultExemptionClaim.port_id == reservation.port_id
        ).first()
        is_faulty_charger = faulty_charger_claim is not None

        # Apply refund or penalty
        if waiver_applied:
            cancel_reason = f"User cancelled ({reason_str}) (Waiver)"
            wallet_tx = WalletTransaction(
                user_id=current_user.user_id,
                amount=ESCROW_AMOUNT,
                transaction_type="Escrow Release",
                reference_id=reservation.reservation_id
            )
            response_message = f"Reservation cancelled and escrow refunded. Cooldown waiver recorded for {reason_str}. (Trusted: {is_trusted_account})"
        elif (is_short_hold and is_first_free_cancel) or is_faulty_charger:
            cancel_reason = f"User cancelled ({reason_str}) (Free)" if reason_str else "User cancelled (Free)"
            wallet_tx = WalletTransaction(
                user_id=current_user.user_id,
                amount=ESCROW_AMOUNT,
                transaction_type="Escrow Release",
                reference_id=reservation.reservation_id
            )
            response_message = f"Reservation cancelled and escrow refunded. (Trusted: {is_trusted_account})"
        else:
            cancel_reason = f"User cancelled ({reason_str}) (Penalty)" if reason_str else "User cancelled (Penalty)"
            wallet_tx = WalletTransaction(
                user_id=current_user.user_id,
                amount=Decimal("0.00"),  # Escrow already deducted; no release
                transaction_type="Escrow Forfeited (Cancellation Penalty)",
                reference_id=reservation.reservation_id
            )
            response_message = f"Reservation cancelled. Escrow of ₹1000 has been forfeited as a cancellation penalty per DD-24. (Trusted: {is_trusted_account})"

        db.add(wallet_tx)

        # Free port and synchronously trigger waitlist promotion (DD-24)
        if port:
            WaitlistService.apply_promotion_or_release(db, port, waitlist_candidate)

        # Cancel reservation
        reservation.status = "Cancelled"
        reservation.cancellation_reason = cancel_reason
        reservation.status_updated_at = now

        log_audit_event(
            db,
            user_id=current_user.user_id,
            action="Reservation Cancelled",
            entity_type="RESERVATIONS",
            entity_id=reservation.reservation_id,
            details={"reason": cancel_reason},
            ip_address=fastapi_req.client.host if fastapi_req.client else "unknown",
            commit=False,
        )

        db.commit()
        return {"success": True, "message": response_message}


    except HTTPException as e:
        db.rollback()
        raise e
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
