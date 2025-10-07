from sqlalchemy import String, DateTime, Integer, Float, Boolean, Text, Enum
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime, timezone
from utilities.dbconfig import Base
from typing import Optional
import enum


class BillingPeriod(str, enum.Enum):
    MONTHLY = "monthly"
    ANNUALLY = "annually"


class SubscriptionPlan(Base):
    __tablename__ = "subscription_plans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)  # e.g., "Basic", "Premium", "Pro"
    price: Mapped[float] = mapped_column(Float, nullable=False)  # Price per billing period
    billing_period: Mapped[BillingPeriod] = mapped_column(Enum(BillingPeriod), nullable=False, default=BillingPeriod.MONTHLY)
    billing_period_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)  # e.g., 3 months, 6 months
    features: Mapped[str] = mapped_column(Text, nullable=False)  # JSON string of features
    description: Mapped[Optional[str]] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    def __repr__(self):
        return f"<SubscriptionPlan(id={self.id}, name={self.name}, price={self.price}, period={self.billing_period})>"
    
    def get_period_description(self) -> str:
        """Get a human-readable description of the billing period"""
        if self.billing_period_count == 1:
            return self.billing_period.value
        else:
            period_map = {
                BillingPeriod.MONTHLY: "month",
                BillingPeriod.ANNUALLY: "year"
            }
            base_period = period_map.get(self.billing_period, self.billing_period.value)
            return f"{self.billing_period_count} {base_period}s"