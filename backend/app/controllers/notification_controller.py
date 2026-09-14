from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.schemas.notification_schema import NotificationResponse, UnreadCountResponse
from app.services.notification_service import NotificationService

router = APIRouter(prefix="/notifications", tags=["Notifications"])


@router.get("", response_model=List[NotificationResponse])
def list_notifications(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return NotificationService.list_notifications(db, current_user)


@router.get("/unread-count", response_model=UnreadCountResponse)
def get_unread_count(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return {"unread_count": NotificationService.count_unread(db, current_user)}


@router.post("/{notification_id}/read", response_model=NotificationResponse)
def mark_notification_read(notification_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return NotificationService.mark_read(db, current_user, notification_id)


@router.post("/read-all")
def mark_all_notifications_read(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    updated = NotificationService.mark_all_read(db, current_user)
    return {"updated": updated}
