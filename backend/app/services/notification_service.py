from typing import Optional
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.notification import Notification

NOTIFICATION_LIST_LIMIT = 50


def create_notification(db: Session, user_id, title: str, message: str, commit: bool = True) -> Notification:
    """FR-19 Notification Center: the single place every controller/service/
    worker routes an in-app notification through, mirroring log_audit_event's
    role for audit rows. Pass commit=False to fold the notification into a
    still-open transaction the caller is about to commit alongside other
    state (e.g. a waitlist promotion offering a port)."""
    entry = Notification(user_id=user_id, title=title, message=message)
    db.add(entry)
    if commit:
        db.commit()
        db.refresh(entry)
    return entry


class NotificationService:
    @staticmethod
    def list_notifications(db: Session, current_user, limit: int = NOTIFICATION_LIST_LIMIT):
        return (
            db.query(Notification)
            .filter(Notification.user_id == current_user.user_id)
            .order_by(Notification.created_at.desc())
            .limit(limit)
            .all()
        )

    @staticmethod
    def count_unread(db: Session, current_user) -> int:
        return (
            db.query(func.count(Notification.notification_id))
            .filter(Notification.user_id == current_user.user_id, Notification.is_read.is_(False))
            .scalar()
            or 0
        )

    @staticmethod
    def mark_read(db: Session, current_user, notification_id: UUID) -> Notification:
        notification = (
            db.query(Notification)
            .filter(Notification.notification_id == notification_id, Notification.user_id == current_user.user_id)
            .first()
        )
        if not notification:
            raise HTTPException(status_code=404, detail="Notification not found")
        notification.is_read = True
        db.commit()
        db.refresh(notification)
        return notification

    @staticmethod
    def mark_all_read(db: Session, current_user) -> int:
        updated = (
            db.query(Notification)
            .filter(Notification.user_id == current_user.user_id, Notification.is_read.is_(False))
            .update({"is_read": True}, synchronize_session=False)
        )
        db.commit()
        return updated
