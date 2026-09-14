from pydantic import BaseModel, ConfigDict
from datetime import datetime
from uuid import UUID


class NotificationResponse(BaseModel):
    notification_id: UUID
    title: str
    message: str
    is_read: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UnreadCountResponse(BaseModel):
    unread_count: int
