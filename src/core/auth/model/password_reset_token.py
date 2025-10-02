from datetime import datetime, timedelta
from sqlalchemy import Column, String, DateTime, Boolean, ForeignKey
from datetime import datetime
from typing import List, Optional
from sqlalchemy import Column, String, DateTime
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import relationship, Mapped, mapped_column
from utilities.dbconfig import Base
from sqlalchemy.sql import func

class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    token: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    user: Mapped["User"] = relationship("User", back_populates="password_reset_tokens")
    
    expiry_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    used: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if self.created_at is None:
            self.created_at = datetime.utcnow()
        if self.expiry_date is None:
            self.expiry_date = datetime.utcnow() + timedelta(hours=24)  # Default 24 hour expiry

    def is_expired(self) -> bool:
        return datetime.utcnow() > self.expiry_date or self.used

    def __repr__(self):
        return f"<PasswordResetToken(id={self.id}, user_id={self.user_id})>"