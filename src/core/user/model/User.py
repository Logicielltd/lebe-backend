from sqlalchemy import JSON, Column, Integer, String, DateTime, ForeignKey, Boolean, Enum
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from core.notification.model import Notification
from utilities.dbconfig import Base
from datetime import datetime
from typing import List, Optional

from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Integer
from sqlalchemy.orm import relationship, Mapped, mapped_column

from core.auth.model.password_reset_token import PasswordResetToken
from core.auth.model.refreshtoken import RefreshToken


class UserStatus(str, Enum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    DELETED = "DELETED"
    
class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(20), nullable=False, unique=True, primary_key=True)
    username: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    email: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    hashed_password: Mapped[str] = mapped_column(String, nullable=False)
    first_name: Mapped[str] = mapped_column(String, nullable=False)
    last_name: Mapped[str] = mapped_column(String, nullable=False)
    phone: Mapped[Optional[str]] = mapped_column(String)
    
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    profile_picture: Mapped[Optional[str]] = mapped_column(String)
    bio: Mapped[Optional[str]] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    
    status: Mapped[UserStatus] = mapped_column(String, nullable=False, default=UserStatus.ACTIVE)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    
    # Relationships
    password_reset_tokens: Mapped[List["PasswordResetToken"]] = relationship(
        "PasswordResetToken", 
        back_populates="user",
        cascade="all, delete-orphan"
    )
    
    refresh_tokens: Mapped[List["RefreshToken"]] = relationship(
        "RefreshToken", 
        back_populates="user",
        cascade="all, delete-orphan"
    )

    # Removed custom __init__; SQLAlchemy handles defaults and values automatically

    def __repr__(self):
        return f"<User(id={self.id}, email={self.email})>"
    
    # Profile relationship (one-to-one)
    profile: Mapped[Optional["Profile"]] = relationship(
        "Profile", 
        back_populates="user",
        cascade="all, delete-orphan",
        uselist=False
    )
    
    # Notifications relationship (one-to-many)
    notifications: Mapped[List["Notification"]] = relationship(
        "Notification", 
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="dynamic"  # Using dynamic loading for potentially large collections
    )

    # For security/authentication purposes
    @property
    def password(self):
        return self.hashed_password

    @property
    def is_active(self):
        return self.enabled

    @property
    def is_authenticated(self):
        return True

    @property
    def is_anonymous(self):
        return False

    def get_id(self):
        return str(self.id)