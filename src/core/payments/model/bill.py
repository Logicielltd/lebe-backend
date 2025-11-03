from sqlalchemy import Column, Integer, String, DateTime, Enum, Numeric
from sqlalchemy.sql import func
from core.payments.model.paymentmethod import PaymentMethod
from utilities.dbconfig import Base
from datetime import datetime
from typing import Optional
import enum

from sqlalchemy import Integer, String, DateTime, Enum
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from utilities.dbconfig import Base
from datetime import datetime
from typing import Optional

from sqlalchemy import String, DateTime, Integer
from sqlalchemy.orm import relationship, Mapped, mapped_column

class BillingType(str, enum.Enum):
    RECURRING = "RECURRING"
    ONE_TIME = "ONE_TIME"

class BillFrequency(str, enum.Enum):
    DAILY = "DAILY"
    WEEKLY = "WEEKLY"
    MONTHLY = "MONTHLY"
    YEARLY = "YEARLY"

class BillStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    PENDING = "PENDING"
    COMPLETED = "COMPLETED"

class Bill(Base):
    __tablename__ = "billing"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    form_id: Mapped[Optional[int]] = mapped_column(Integer)
    discount_id: Mapped[Optional[int]] = mapped_column(Integer)
    service_name: Mapped[Optional[str]] = mapped_column(String)
    
    billing_type: Mapped[Optional[BillingType]] = mapped_column(Enum(BillingType))
    currency: Mapped[Optional[str]] = mapped_column(String)
    amount: Mapped[Optional[float]] = mapped_column(Numeric(10, 2))
    
    frequency: Mapped[Optional[BillFrequency]] = mapped_column(Enum(BillFrequency))
    payment_method: Mapped[Optional[PaymentMethod]] = mapped_column(Enum(PaymentMethod))
    status: Mapped[Optional[BillStatus]] = mapped_column(Enum(BillStatus))
    
    created_on: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_on: Mapped[datetime] = mapped_column(DateTime(timezone=True), onupdate=func.now())

    def __repr__(self):
        return f"<Bill(id={self.id}, service_name={self.service_name}, amount={self.amount})>"