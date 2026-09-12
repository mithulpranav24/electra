from datetime import datetime, timedelta, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.penalty import Penalty
from app.models.user import User
from app.services.audit_service import log_audit_event

# FR-21: 3 accumulated (unserved) points triggers an automatic 24-hour ban.
BAN_THRESHOLD_POINTS = 3
BAN_DURATION_HOURS = 24


class PenaltyService:
    @staticmethod
    def assign_penalty_point(db: Session, user: User, reason: str, points: int = 1) -> Penalty:
        """FR-21 Penalty System: records a penalty and, once the user's unserved
        point total reaches BAN_THRESHOLD_POINTS, applies a 24-hour ban.

        Callers must already hold `user` FOR UPDATE under the global lock
        hierarchy (Tier 3, USERS) before calling this - the ban write below
        mutates that same row, and per Architecture.md 3.5 no lock below Tier 3
        (WAITLIST, RESERVATIONS, CHARGING_SESSIONS) may be acquired after it.
        This is why clearing the newly-banned user's own WAITLIST entry happens
        in a separate, later async sweep (clear_waitlist_for_banned_users)
        rather than here: locking that entry's STATIONS/CHARGING_PORTS (Tiers
        1-2) while a Tier 3 USERS lock is already held would invert the
        hierarchy.
        """
        penalty = Penalty(user_id=user.user_id, reason=reason, points=points, is_served=False)
        db.add(penalty)
        db.flush()

        unserved_points = (
            db.query(func.coalesce(func.sum(Penalty.points), 0))
            .filter(Penalty.user_id == user.user_id, Penalty.is_served.is_(False))
            .scalar()
        )

        if unserved_points >= BAN_THRESHOLD_POINTS:
            now = datetime.now(timezone.utc).replace(tzinfo=None)
            user.banned_until = now + timedelta(hours=BAN_DURATION_HOURS)
            # Points DO NOT reset - they're marked served exactly at ban time so
            # points earned during the ban stay active (unserved) once it lifts.
            db.query(Penalty).filter(Penalty.user_id == user.user_id, Penalty.is_served.is_(False)).update(
                {"is_served": True}, synchronize_session=False
            )
            log_audit_event(
                db,
                user_id=user.user_id,
                action="User Banned",
                entity_type="USERS",
                entity_id=user.user_id,
                details={"reason": reason, "unserved_points": unserved_points, "banned_until": user.banned_until.isoformat()},
                ip_address="system",
                commit=False,
            )

        return penalty
