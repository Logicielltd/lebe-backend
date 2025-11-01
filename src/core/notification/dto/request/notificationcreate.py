from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel

from core.notification.model.Notification import NotificationType


class NotificationCreateRequest(BaseModel):
    type: NotificationType
    data: dict
    user_id: Optional[str] = None  # If not provided, will use current user
