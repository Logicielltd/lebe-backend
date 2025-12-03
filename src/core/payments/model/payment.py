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

    # Transaction IDs - tracks both CTM and second stage (MTC or ATP)
    transaction_id: Mapped[str] = mapped_column(String, nullable=False, unique=True)  # Original CTM transaction
    ctm_transaction_id: Mapped[Optional[str]] = mapped_column(String)  # CTM (Customer to Merchant) transaction ID
    mtc_transaction_id: Mapped[Optional[str]] = mapped_column(String)  # MTC (Merchant to Customer) transaction ID for send_money
    atp_transaction_id: Mapped[Optional[str]] = mapped_column(String)  # ATP (Airtime Top-Up) transaction ID for buy_airtime
    blp_transaction_id: Mapped[Optional[str]] = mapped_column(String)  # BLP (Bill Payment) transaction ID for pay_bill

    # Reversal tracking - for reversal payments, links back to the original failed payment
    original_payment_id: Mapped[Optional[int]] = mapped_column(Integer)  # Links reversal payment to original payment

    service_name: Mapped[Optional[str]] = mapped_column(String)
    intent: Mapped[Optional[str]] = mapped_column(String)
    customer_email: Mapped[Optional[str]] = mapped_column(String)
    customer_name: Mapped[Optional[str]] = mapped_column(String)

    # Phone numbers - sender is the customer paying (CTM), receiver is who gets the money (MTC)
    sender_phone: Mapped[Optional[str]] = mapped_column(String)  # Customer initiating payment (in 0xxx format)
    receiver_phone: Mapped[Optional[str]] = mapped_column(String)  # Recipient of payment (in 0xxx format)

    bank_code: Mapped[Optional[str]] = mapped_column(String)
    network: Mapped[Optional[Network]] = mapped_column(Enum(Network))

    # External biller information (for non-telco/ABS bill payments)
    ext_biller_ref_id: Mapped[Optional[str]] = mapped_column(String)  # Biller ID for ABS bill payments

    # Sender and receiver information
    sender_name: Mapped[Optional[str]] = mapped_column(String)  # Name of user initiating transaction
    receiver_name: Mapped[Optional[str]] = mapped_column(String)  # Verified account holder name
    sender_provider: Mapped[Optional[str]] = mapped_column(String)  # Provider based on sender network
    receiver_provider: Mapped[Optional[str]] = mapped_column(String)  # Provider based on receiver network

    date_paid: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_on: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    def __repr__(self):
        return f"<Payment(id={self.id}, transaction_id={self.transaction_id}, amount={self.amount_paid}, status={self.status})>"