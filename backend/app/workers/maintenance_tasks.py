from app.core.celery_app import celery_app
from app.core.database import SessionLocal
from app.services.maintenance_service import MaintenanceService


@celery_app.task(name="app.workers.maintenance_tasks.check_scheduled_maintenance")
def check_scheduled_maintenance() -> int:
    """FR-27 'Scheduled Maintenance Trigger': runs every minute, transitioning
    ports whose scheduled maintenance start_time has arrived into Maintenance,
    cancelling any unstarted reservation/waitlist offer without penalty."""
    db = SessionLocal()
    try:
        return MaintenanceService.check_scheduled_maintenance(db)
    finally:
        db.close()
