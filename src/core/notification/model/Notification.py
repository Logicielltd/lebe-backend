from sqlalchemy import JSON, Column, Integer, String, DateTime, ForeignKey, Boolean, Enum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from sqlalchemy.orm import Mapped, mapped_column
from utilities.dbconfig import Base
from datetime import datetime
from typing import List, Optional, Dict, Any
from enum import Enum as PythonEnum

class NotificationStatus(str, PythonEnum):
    UNREAD = "UNREAD"
    READ = "READ"
    ARCHIVED = "ARCHIVED"

class NotificationType(str, PythonEnum):
    SYSTEM = "SYSTEM"
    BUSINESS = "BUSINESS"
    TRANSACTION = "TRANSACTION"
    SECURITY = "SECURITY"
    OTHER = "OTHER"

class Notification(Base):
    __tablename__ = "notifications"
    
    id: Mapped[str] = mapped_column(String(20), primary_key=True, nullable=False, unique=True)
    user_id: Mapped[str] = mapped_column(String(20), ForeignKey("users.id"), nullable=False)
    
    # Notification content stored as JSONB for flexibility
    data: Mapped[Dict[str, Any]] = mapped_column(JSONB, nullable=False)
    
    type: Mapped[NotificationType] = mapped_column(String, nullable=False, default=NotificationType.SYSTEM)
    status: Mapped[NotificationStatus] = mapped_column(String, nullable=False, default=NotificationStatus.UNREAD)
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    read_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    
    # Relationship to user
    user: Mapped["User"] = relationship("User", back_populates="notifications")
    
    def __repr__(self):
        return f"<Notification(id={self.id}, type={self.type}, status={self.status})>"