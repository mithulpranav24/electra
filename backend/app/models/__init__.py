"""
Importing this package registers every SQLAlchemy model against the shared
declarative Base, so relationship strings like Station.company (relationship
"Company") resolve regardless of which model a caller imported directly.

FastAPI gets this for free today because app.main imports every controller,
which transitively imports every model. A standalone process that only
imports a narrow slice (e.g. a Celery worker importing just the waitlist
task chain) does not get that side effect, so it must import this package
explicitly before running any query. See app/core/celery_app.py.
"""

from app.models import (  # noqa: F401
    audit,
    company,
    invoice,
    penalty,
    reservation,
    session,
    station,
    transient,
    user,
    vehicle,
    wallet,
)
