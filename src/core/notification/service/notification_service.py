from datetime import datetime
import secrets
import string
from typing import List, Optional
from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from core.notification.model.Notification import Notification, NotificationStatus, NotificationType
from core.user.model.User import User

# DTO Models
from core.notification.dto.response.notification_response import NotificationResponse
from core.notification.dto.response.paged_notifications import PagedNotificationResponse
from core.notification.dto.response.message_response import MessageResponse

class NotificationService:
    def __init__(self, db: Session):
        self.db = db

    def create_notification(
        self,
        user_id: str,
        notification_type: NotificationType,
        data: dict
    ) -> NotificationResponse:
        """Create a new notification for a user"""
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        notification = Notification(
            id=self._generate_notification_id(),
            user_id=user_id,
            type=notification_type,
            data=data,
            status=NotificationStatus.UNREAD
        )

        self.db.add(notification)
        self.db.commit()
        self.db.refresh(notification)

        return NotificationResponse.from_orm(notification)

    def get_notification(self, notification_id: str) -> NotificationResponse:
        """Get a specific notification by ID"""
        notification = self.db.query(Notification).filter(Notification.id == notification_id).first()
        if not notification:
            raise HTTPException(status_code=404, detail="Notification not found")
        
        return NotificationResponse.from_orm(notification)

    def get_user_notifications_paged(
        self,
        user_id: str,
        page: int,
        size: int,
        status: Optional[NotificationStatus] = None,
        notification_type: Optional[NotificationType] = None
    ) -> PagedNotificationResponse:
        """Get paginated notifications for a user with optional filters"""
        query = self.db.query(Notification).filter(Notification.user_id == user_id)

        if status:
            query = query.filter(Notification.status == status)
        if notification_type:
            query = query.filter(Notification.type == notification_type)

        total = query.count()
        notifications = query.order_by(Notification.created_at.desc()) \
                           .offset((page - 1) * size) \
                           .limit(size) \
                           .all()

        return PagedNotificationResponse(
            items=[NotificationResponse.from_orm(n) for n in notifications],
            total=total,
            page=page,
            size=size,
            pages=(total + size - 1) // size  # Calculate total pages
        )

    def update_notification(
        self,
        notification_id: str,
        status: Optional[NotificationStatus] = None,
        data: Optional[dict] = None
    ) -> NotificationResponse:
        """Update a notification's status and/or data"""
        notification = self.db.query(Notification).filter(Notification.id == notification_id).first()
        if not notification:
            raise HTTPException(status_code=404, detail="Notification not found")

        if status is not None:
            notification.status = status
            if status == NotificationStatus.READ and notification.read_at is None:
                notification.read_at = datetime.now()

        if data is not None:
            notification.data = data

        self.db.commit()
        self.db.refresh(notification)

        return NotificationResponse.from_orm(notification)

    def mark_notification_as_read(self, notification_id: str) -> NotificationResponse:
        """Mark a specific notification as read"""
        return self.update_notification(
            notification_id=notification_id,
            status=NotificationStatus.READ
        )

    def mark_all_notifications_as_read(self, user_id: str) -> MessageResponse:
        """Mark all unread notifications for a user as read"""
        self.db.query(Notification) \
             .filter(Notification.user_id == user_id) \
             .filter(Notification.status == NotificationStatus.UNREAD) \
             .update({
                 Notification.status: NotificationStatus.READ,
                 Notification.read_at: datetime.now()
             }, synchronize_session=False)
        
        self.db.commit()
        return MessageResponse(message="All notifications marked as read")

    def delete_notification(self, notification_id: str) -> None:
        """Delete a notification"""
        notification = self.db.query(Notification).filter(Notification.id == notification_id).first()
        if not notification:
            raise HTTPException(status_code=404, detail="Notification not found")

        self.db.delete(notification)
        self.db.commit()
    
    def _generate_notification_id(self) -> str:
        """Generate a unique notification ID"""
        alphabet = string.ascii_letters + string.digits
        return "".join(secrets.choice(alphabet) for i in range(16))