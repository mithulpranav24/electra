import uuid
from unittest.mock import MagicMock


class _AlwaysEmptyQuery:
    """Mirrors the _AlwaysNoneQuery pattern in test_sessions.py: any chain of
    .filter()/.join()/.order_by() collapses to an empty result, regardless of
    call order, so the "no candidates" branch of a background sweep can be
    exercised without a live database."""

    def __getattr__(self, name):
        if name == "first":
            return lambda: None
        if name == "all":
            return lambda: []
        if name == "scalar":
            return lambda: 0
        return lambda *a, **k: self


def _empty_db():
    db = MagicMock()
    db.query.side_effect = lambda *a, **k: _AlwaysEmptyQuery()
    return db


def test_enforce_overstay_penalties_no_candidates():
    from app.services.session_service import SessionService

    assert SessionService.enforce_overstay_penalties(_empty_db()) == 0


def test_clear_waitlist_for_banned_users_no_candidates():
    from app.services.waitlist_service import WaitlistService

    assert WaitlistService.clear_waitlist_for_banned_users(_empty_db()) == 0


def test_assign_penalty_point_below_threshold_does_not_ban():
    from app.models.user import User
    from app.services.penalty_service import PenaltyService

    db = MagicMock()
    db.query.return_value.filter.return_value.scalar.return_value = 1

    user = User()
    user.user_id = uuid.uuid4()
    user.banned_until = None

    PenaltyService.assign_penalty_point(db, user, "Ignored Waitlist Offer")

    assert user.banned_until is None


def test_assign_penalty_point_at_threshold_bans_user():
    from app.models.user import User
    from app.services.penalty_service import PenaltyService, BAN_THRESHOLD_POINTS

    db = MagicMock()
    db.query.return_value.filter.return_value.scalar.return_value = BAN_THRESHOLD_POINTS

    user = User()
    user.user_id = uuid.uuid4()
    user.banned_until = None

    PenaltyService.assign_penalty_point(db, user, "Overstay After Charging Complete")

    assert user.banned_until is not None
