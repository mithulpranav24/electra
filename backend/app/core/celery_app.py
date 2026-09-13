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
    # FR-16: force-terminate sessions idle for 24 accumulated hours.
    "auto-terminate-stale-sessions": {
        "task": "app.workers.session_tasks.auto_terminate_stale_sessions",
        "schedule": 60.0,
    },
    # FR-21 "Overstay Penalty Enforcer": 1 point once idle time crosses the
    # 30-minute grace period after target_reached.
    "enforce-overstay-penalties": {
        "task": "app.workers.session_tasks.enforce_overstay_penalties",
        "schedule": 15.0,
    },
    # FR-21: asynchronously clear a newly-banned user's own WAITLIST entry.
    "clear-waitlist-for-banned-users": {
        "task": "app.workers.waitlist_tasks.clear_waitlist_for_banned_users",
        "schedule": 15.0,
    },
}

# celery_app.autodiscover_tasks() only imports a module literally named
# "tasks.py" inside each listed package by convention; it would silently
# skip waitlist_tasks.py, leaving the worker with zero registered tasks
# (beat would then dispatch to task names the worker never learned about).
# Import task modules explicitly instead, after celery_app exists, since
# their @celery_app.task decorators need it at import time.
import app.workers.waitlist_tasks  # noqa: E402,F401
import app.workers.session_tasks  # noqa: E402,F401
