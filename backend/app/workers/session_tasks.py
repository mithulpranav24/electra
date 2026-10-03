from app.core.celery_app import celery_app
from app.core.database import SessionLocal
from app.services.session_service import SessionService


@celery_app.task(name="app.workers.session_tasks.auto_terminate_stale_sessions")
def auto_terminate_stale_sessions() -> int:
    """FR-16: force-terminates any session idle for 24 accumulated hours,
    billing an abandonment penalty and taking the port Offline for operator
    intervention (no waitlist promotion)."""
    db = SessionLocal()
    try:
        return SessionService.auto_terminate_stale_sessions(db)
    finally:
        db.close()


@celery_app.task(name="app.workers.session_tasks.enforce_overstay_penalties")
def enforce_overstay_penalties() -> int:
    """FR-21 'Overstay Penalty Enforcer': runs every 15 seconds, assigning 1
    penalty point the first time a session's idle time crosses the 30-minute
    grace period after target_reached."""
    db = SessionLocal()
    try:
        return SessionService.enforce_overstay_penalties(db)
    finally:
        db.close()


@celery_app.task(name="app.workers.session_tasks.abort_timed_out_handshakes")
def abort_timed_out_handshakes() -> int:
    """FR-15: finds sessions where hardware_ack_deadline has passed without an ack,
    aborts them, refunds escrow, frees the port, and tracks health warnings."""
    from datetime import datetime, timezone
    from decimal import Decimal
    from app.models.session import ChargingSession
    from app.models.reservation import Reservation
    from app.models.station import ChargingPort
    from app.models.wallet import WalletTransaction
    from app.services.notification_service import create_notification

    db = SessionLocal()
    aborted = 0
    try:
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        timed_out = db.query(ChargingSession).filter(
            ChargingSession.hardware_acked.is_(False),
            ChargingSession.hardware_ack_deadline.isnot(None),
            ChargingSession.hardware_ack_deadline < now,
            ChargingSession.end_time.is_(None),
        ).all()

        for session in timed_out:
            try:
                reservation = db.query(Reservation).filter(
                    Reservation.reservation_id == session.reservation_id
                ).first()
                if not reservation:
                    continue

                port = db.query(ChargingPort).with_for_update().filter(
                    ChargingPort.port_id == reservation.port_id
                ).first()

                # Abort: end session immediately with no cost
                session.end_time = now

                # Refund escrow
                refund_tx = WalletTransaction(
                    user_id=reservation.user_id,
                    amount=Decimal("1000.00"),
                    transaction_type="Escrow Release",
                    reference_id=reservation.reservation_id,
                )
                db.add(refund_tx)

                # Free port and track handshake failures
                if port:
                    port.consecutive_handshake_failures = (port.consecutive_handshake_failures or 0) + 1
                    if port.consecutive_handshake_failures >= 2:
                        port.has_health_warning = True
                        port.consecutive_handshake_failures = 0
                    port.status = "Available"

                reservation.status = "Cancelled"
                reservation.cancellation_reason = "Hardware handshake timeout"

                create_notification(
                    db,
                    reservation.user_id,
                    "Session aborted — charger did not respond",
                    "The charger failed to confirm the connection within 60 seconds. Your escrow has been refunded. "
                    "Please try a different port or contact the operator.",
                    commit=False,
                )
                db.commit()
                aborted += 1
            except Exception:
                db.rollback()
    finally:
        db.close()

    return aborted

