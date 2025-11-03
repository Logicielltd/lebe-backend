from typing import List
from pydantic import BaseModel

from src.core.notification.dto.response.notification_response import NotificationResponse


class PagedNotificationResponse(BaseModel):
    total: int
    page: int
    size: int
    items: List[NotificationResponse]