from sqlalchemy import Column, String, DateTime, Integer, Float, Boolean, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime, timezone
from utilities.dbconfig import Base
from typing import Optional
from enum import Enum


class SubscriptionStatus(str, Enum):
    ACTIVE = "ACTIVE"
    EXPIRED = "EXPIRED"
    CANCELLED = "CANCELLED"
    SUSPENDED = "SUSPENDED"


class UserSubscription(Base):
    __tablename__ = "user_subscriptions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(20), ForeignKey('users.id'), nullable=False)
    plan_id: Mapped[int] = mapped_column(Integer, ForeignKey('subscription_plans.id'), nullable=False)
    
    # Subscription details
    status: Mapped[SubscriptionStatus] = mapped_column(String, nullable=False, default=SubscriptionStatus.ACTIVE)
    amount_paid: Mapped[float] = mapped_column(Float, nullable=False)
    
    # Dates
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    cancelled_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    
    # Metadata
    payment_reference: Mapped[Optional[str]] = mapped_column(String(255))  # For tracking payments
    notes: Mapped[Optional[str]] = mapped_column(Text)  # Any additional notes
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # Relationships
    plan: Mapped["SubscriptionPlan"] = relationship("SubscriptionPlan")

    @property
    def is_active(self) -> bool:
        """Check if subscription is currently active"""
        return (
            self.status == SubscriptionStatus.ACTIVE and 
            self.expires_at > datetime.now(timezone.utc)
        )

    @property
    def days_remaining(self) -> int:
        """Get days remaining on subscription"""
        if not self.is_active:
            return 0
        return (self.expires_at - datetime.now(timezone.utc)).days

    def __repr__(self):
        return f"<UserSubscription(id={self.id}, user_id={self.user_id}, plan_id={self.plan_id}, status={self.status})>"