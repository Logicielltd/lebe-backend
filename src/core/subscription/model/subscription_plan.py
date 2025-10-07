from sqlalchemy import Column, String, DateTime, Integer, Float, Boolean, Text
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime, timezone
from utilities.dbconfig import Base
from typing import Optional


class SubscriptionPlan(Base):
    __tablename__ = "subscription_plans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)  # e.g., "Basic", "Premium", "Pro"
    price: Mapped[float] = mapped_column(Float, nullable=False)  # Monthly price
    features: Mapped[str] = mapped_column(Text, nullable=False)  # JSON string or comma-separated features
    description: Mapped[Optional[str]] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    def __repr__(self):
        return f"<SubscriptionPlan(id={self.id}, name={self.name}, price={self.price})>"