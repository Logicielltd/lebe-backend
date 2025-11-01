from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel

from core.notification.model.Notification import NotificationStatus


class NotificationUpdateRequest(BaseModel):
    status: Optional[NotificationStatus] = None
    data: Optional[dict] = None