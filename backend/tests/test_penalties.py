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


def test_assign_penalty_point_accumulates_across_calls():
    """Point accumulation across 1, 2, and then 3 points: the 3rd call is the
    one that must cross BAN_THRESHOLD_POINTS and ban the user, not the 1st or 2nd."""
    from app.models.user import User
    from app.services.penalty_service import PenaltyService, BAN_THRESHOLD_POINTS

    assert BAN_THRESHOLD_POINTS == 3

    db = MagicMock()
    user = User()
    user.user_id = uuid.uuid4()
    user.banned_until = None

    db.query.return_value.filter.return_value.scalar.return_value = 1
    PenaltyService.assign_penalty_point(db, user, "Ignored Waitlist Offer")
    assert user.banned_until is None

    db.query.return_value.filter.return_value.scalar.return_value = 2
    PenaltyService.assign_penalty_point(db, user, "Ignored Waitlist Offer")
    assert user.banned_until is None

    db.query.return_value.filter.return_value.scalar.return_value = 3
    PenaltyService.assign_penalty_point(db, user, "Overstay After Charging Complete")
    assert user.banned_until is not None


def test_assign_penalty_point_marks_previously_unserved_points_served_on_ban():
    from app.models.user import User
    from app.services.penalty_service import PenaltyService, BAN_THRESHOLD_POINTS

    db = MagicMock()
    db.query.return_value.filter.return_value.scalar.return_value = BAN_THRESHOLD_POINTS

    user = User()
    user.user_id = uuid.uuid4()
    user.banned_until = None

    PenaltyService.assign_penalty_point(db, user, "Overstay After Charging Complete")

    # The bulk UPDATE ... SET is_served = TRUE is issued against the DB...
    update_call = db.query.return_value.filter.return_value.update
    update_call.assert_called_once_with({"is_served": True}, synchronize_session=False)


def test_assign_penalty_point_returned_object_reflects_served_state():
    """Regression test: assign_penalty_point uses synchronize_session=False for
    its bulk UPDATE, which bypasses the ORM session and leaves any in-memory
    instance created earlier in the same call stale unless corrected
    explicitly. The Penalty object returned to the caller must reflect the
    ban it just caused, not the pre-ban is_served=False it was constructed
    with."""
    from app.models.user import User
    from app.services.penalty_service import PenaltyService, BAN_THRESHOLD_POINTS

    db = MagicMock()
    db.query.return_value.filter.return_value.scalar.return_value = BAN_THRESHOLD_POINTS

    user = User()
    user.user_id = uuid.uuid4()
    user.banned_until = None

    penalty = PenaltyService.assign_penalty_point(db, user, "Overstay After Charging Complete")

    assert penalty.is_served is True


def test_assign_penalty_point_below_threshold_leaves_returned_object_unserved():
    from app.models.user import User
    from app.services.penalty_service import PenaltyService

    db = MagicMock()
    db.query.return_value.filter.return_value.scalar.return_value = 1

    user = User()
    user.user_id = uuid.uuid4()
    user.banned_until = None

    penalty = PenaltyService.assign_penalty_point(db, user, "Ignored Waitlist Offer")

    assert penalty.is_served is False


def test_log_audit_event_persists_expected_fields_and_commits_by_default():
    from app.services.audit_service import log_audit_event

    db = MagicMock()
    user_id = uuid.uuid4()
    entity_id = uuid.uuid4()

    entry = log_audit_event(
        db,
        user_id=user_id,
        action="User Banned",
        entity_type="USERS",
        entity_id=entity_id,
        details={"reason": "Overstay After Charging Complete"},
        ip_address="127.0.0.1",
    )

    db.add.assert_called_once_with(entry)
    assert entry.user_id == user_id
    assert entry.action == "User Banned"
    assert entry.entity_type == "USERS"
    assert entry.entity_id == entity_id
    assert entry.details == {"reason": "Overstay After Charging Complete"}
    assert entry.ip_address == "127.0.0.1"
    db.commit.assert_called_once()
    db.refresh.assert_called_once_with(entry)


def test_log_audit_event_commit_false_does_not_commit_or_refresh():
    """commit=False lets a caller fold the audit row into a still-open
    transaction (e.g. alongside a wallet ledger update) instead of it being
    its own separately-committed follow-up transaction."""
    from app.services.audit_service import log_audit_event

    db = MagicMock()
    log_audit_event(db, user_id=uuid.uuid4(), action="Waitlist Left", commit=False)

    db.add.assert_called_once()
    db.commit.assert_not_called()
    db.refresh.assert_not_called()


def test_log_audit_event_defaults_missing_ip_address_to_unknown():
    from app.services.audit_service import log_audit_event

    db = MagicMock()
    entry = log_audit_event(db, user_id=None, action="System Sweep", ip_address=None, commit=False)

    assert entry.ip_address == "unknown"
