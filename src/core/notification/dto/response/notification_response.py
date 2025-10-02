from datetime import datetime
from enum import Enum
from pydantic import BaseModel
from typing import Any, Dict, Optional

from core.notification.model.Notification import NotificationStatus, NotificationType

class NotificationResponse(BaseModel):
    id: str
    user_id: str
    type: NotificationType
    status: NotificationStatus
    data: Dict[str, Any]
    created_at: datetime
    read_at: Optional[datetime] = None

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
        use_enum_values = True  # This will use the enum values instead of enum objects
        orm_mode = True  # Allows conversion from ORM model

    @classmethod
    def from_orm(cls, notification):
        return cls(
            id=notification.id,
            user_id=notification.user_id,
            type=notification.type,
            status=notification.status,
            data=notification.data,
            created_at=notification.created_at,
            read_at=notification.read_at
        )