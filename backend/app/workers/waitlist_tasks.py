from app.core.celery_app import celery_app
from app.core.database import SessionLocal
from app.services.waitlist_service import WaitlistService


@celery_app.task(name="app.workers.waitlist_tasks.expire_waitlist_offers")
def expire_waitlist_offers() -> int:
    """DD-03: runs every 15 seconds. Drops any waitlist offer whose 90-second
    confirmation window has elapsed and promotes the next eligible driver."""
    db = SessionLocal()
    try:
        return WaitlistService.expire_stale_offers(db)
    finally:
        db.close()


@celery_app.task(name="app.workers.waitlist_tasks.expire_reservations")
def expire_reservations() -> None:
    """Background counterpart to the opportunistic cleanup already run inline
    on reservation endpoints, so ports free up (and the waitlist advances)
    even when nobody happens to call the API in the meantime."""
    from app.controllers.reservation_controller import clean_expired_reservations

    db = SessionLocal()
    try:
        clean_expired_reservations(db)
    finally:
        db.close()


@celery_app.task(name="app.workers.waitlist_tasks.clear_waitlist_for_banned_users")
def clear_waitlist_for_banned_users() -> int:
    """FR-21: asynchronously clears a banned user's own WAITLIST entry
    (promoting the next candidate if the entry held an active offer), since
    applying the ban itself cannot safely do this without inverting the
    global lock hierarchy."""
    db = SessionLocal()
    try:
        return WaitlistService.clear_waitlist_for_banned_users(db)
    finally:
        db.close()
