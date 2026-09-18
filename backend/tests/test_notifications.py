import uuid
from unittest.mock import MagicMock

import pytest


def test_create_notification_commits_and_refreshes_by_default():
    from app.services.notification_service import create_notification

    db = MagicMock()
    user_id = uuid.uuid4()

    entry = create_notification(db, user_id, "Reservation confirmed", "Check in within 15 minutes.")

    db.add.assert_called_once_with(entry)
    assert entry.user_id == user_id
    assert entry.title == "Reservation confirmed"
    assert entry.message == "Check in within 15 minutes."
    db.commit.assert_called_once()
    db.refresh.assert_called_once_with(entry)


def test_create_notification_commit_false_skips_commit_and_refresh():
    from app.services.notification_service import create_notification

    db = MagicMock()
    create_notification(db, uuid.uuid4(), "Waitlist offer", "A port is available.", commit=False)

    db.add.assert_called_once()
    db.commit.assert_not_called()
    db.refresh.assert_not_called()


def test_list_notifications_scopes_to_current_user_and_orders_recent_first():
    from app.services.notification_service import NotificationService

    current_user = MagicMock(user_id=uuid.uuid4())
    db = MagicMock()
    expected = [MagicMock(), MagicMock()]
    db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = expected

    result = NotificationService.list_notifications(db, current_user)

    assert result == expected


def test_count_unread_defaults_to_zero_when_scalar_is_none():
    from app.services.notification_service import NotificationService

    db = MagicMock()
    db.query.return_value.filter.return_value.scalar.return_value = None

    assert NotificationService.count_unread(db, MagicMock(user_id=uuid.uuid4())) == 0


def test_mark_read_raises_404_for_someone_elses_notification():
    from fastapi import HTTPException
    from app.services.notification_service import NotificationService

    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None

    with pytest.raises(HTTPException) as exc_info:
        NotificationService.mark_read(db, MagicMock(user_id=uuid.uuid4()), uuid.uuid4())
    assert exc_info.value.status_code == 404


def test_mark_read_sets_is_read_true_and_commits():
    from app.services.notification_service import NotificationService

    db = MagicMock()
    notification = MagicMock(is_read=False)
    db.query.return_value.filter.return_value.first.return_value = notification

    result = NotificationService.mark_read(db, MagicMock(user_id=uuid.uuid4()), uuid.uuid4())

    assert notification.is_read is True
    assert result is notification
    db.commit.assert_called_once()


def test_mark_all_read_bulk_updates_and_returns_count():
    from app.services.notification_service import NotificationService

    db = MagicMock()
    db.query.return_value.filter.return_value.update.return_value = 3

    updated = NotificationService.mark_all_read(db, MagicMock(user_id=uuid.uuid4()))

    assert updated == 3
    db.query.return_value.filter.return_value.update.assert_called_once_with({"is_read": True}, synchronize_session=False)
    db.commit.assert_called_once()
