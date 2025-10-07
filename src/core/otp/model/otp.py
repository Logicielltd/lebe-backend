from sqlalchemy import Column, String, DateTime, Integer
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime, timedelta, timezone
from utilities.dbconfig import Base
from config import settings


class OTP(Base):
    __tablename__ = "otps"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    phone: Mapped[str] = mapped_column(String, nullable=True)
    email: Mapped[str] = mapped_column(String, nullable=True)
    otp: Mapped[str] = mapped_column(String(6), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc) + timedelta(minutes=settings.OTP_EXPIRE_MINUTES))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    def is_expired(self) -> bool:
        """Check if the OTP has expired"""
        return datetime.now(timezone.utc) > self.expires_at

    def __repr__(self):
        return f"<OTP(phone={self.phone}, email={self.email}, expires_at={self.expires_at})>"