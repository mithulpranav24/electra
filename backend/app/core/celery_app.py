from celery import Celery
from app.core.config import settings

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

celery_app.autodiscover_tasks(["app.workers"])
