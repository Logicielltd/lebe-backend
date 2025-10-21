from sqlalchemy import Column, Integer, String, DateTime, Enum, Numeric, ForeignKey, JSON, Text
from sqlalchemy.sql import func
from core.payments.model.paymentmethod import PaymentMethod
from core.payments.model.paymentstatus import PaymentStatus
from core.payments.model.paynetwork import Network
from utilities.dbconfig import Base
from datetime import datetime
from typing import Optional

from sqlalchemy import String, DateTime, Integer
from sqlalchemy.orm import Mapped, mapped_column

class Payment(Base):
    __tablename__ = "payment"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    bill_id: Mapped[int] = mapped_column(Integer, nullable=False)
    response_id: Mapped[Optional[int]] = mapped_column(Integer)
    amount_paid: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)

    payment_method: Mapped[PaymentMethod] = mapped_column(Enum(PaymentMethod), nullable=False)
    status: Mapped[PaymentStatus] = mapped_column(Enum(PaymentStatus), nullable=False)

    transaction_id: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    service_name: Mapped[Optional[str]] = mapped_column(String)
    customer_email: Mapped[Optional[str]] = mapped_column(String)
    customer_name: Mapped[Optional[str]] = mapped_column(String)
    phone_number: Mapped[Optional[str]] = mapped_column(String)

    bank_code: Mapped[Optional[str]] = mapped_column(String)
    network: Mapped[Optional[Network]] = mapped_column(Enum(Network))

    # New fields for enhanced tracking and callback matching
    checkout_id: Mapped[Optional[str]] = mapped_column(String, index=True, nullable=True)
    external_transaction_id: Mapped[Optional[str]] = mapped_column(String, unique=True, nullable=True)
    orchard_reference: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    # Response tracking for audit trail
    initiation_response: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    callback_response: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    verification_response: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # Timestamps for tracking
    callback_received_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_status_check: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    date_paid: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_on: Mapped[datetime] = mapped_column(DateTime(timezone=True), onupdate=func.now())

    def __repr__(self):
        return f"<Payment(id={self.id}, transaction_id={self.transaction_id}, amount={self.amount_paid}, status={self.status})>"