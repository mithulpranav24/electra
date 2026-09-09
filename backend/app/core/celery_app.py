from celery import Celery
from app.core.config import settings

# A standalone worker process only imports what its task modules import
# directly, unlike the FastAPI app (which pulls in every model transitively
# via app.main's controller imports). Import the full model graph up front
# so SQLAlchemy relationship strings (e.g. Station -> "Company") always
# resolve, regardless of which task runs first.
import app.models  # noqa: E402,F401

celery_app = Celery(
    "electra",
    broker=settings.redis_url or "redis://localhost:6379/0",
    backend=settings.redis_url or "redis://localhost:6379/0",
)

celery_app.conf.timezone = "UTC"
celery_app.conf.beat_schedule = {
    # DD-03: offers are exclusively expired 90 seconds after being made.
    "expire-waitlist-offers": {
        "task": "app.workers.waitlist_tasks.expire_waitlist_offers",
        "schedule": 15.0,
    },
    # Frees ports abandoned by a No-Show and promotes the next queued driver.
    "expire-reservations": {
        "task": "app.workers.waitlist_tasks.expire_reservations",
        "schedule": 60.0,
    },
}

# celery_app.autodiscover_tasks() only imports a module literally named
# "tasks.py" inside each listed package by convention; it would silently
# skip waitlist_tasks.py, leaving the worker with zero registered tasks
# (beat would then dispatch to task names the worker never learned about).
# Import task modules explicitly instead, after celery_app exists, since
# their @celery_app.task decorators need it at import time.
import app.workers.waitlist_tasks  # noqa: E402,F401
