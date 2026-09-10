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
