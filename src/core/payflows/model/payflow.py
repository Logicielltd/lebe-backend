from datetime import datetime
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, JSON
from sqlalchemy.orm import relationship, Mapped, mapped_column

from utilities.dbconfig import Base


class Payflow(Base):
    """
    Payflow model for storing saved payment sessions/templates.
    A payflow is a snapshot of a successful payment transaction that can be repeated.
    Users can save payflows similar to beneficiaries and reuse them for quick payments.
    
    A payflow can only be created after a successful transaction where all intent slots are available.
    """
    __tablename__ = "payflows"

    id = Column(Integer, primary_key=True, index=True)
    user_id: Mapped[str] = mapped_column(String(20), ForeignKey("users.id"), nullable=False)

    # Payflow identification
    name = Column(String(100), nullable=False)  # User-friendly name (e.g., "Mom Payment", "Electricity Bill")
    description = Column(String(255), nullable=True)  # Optional description

    # Intent and slot information
    intent_name = Column(String(50), nullable=False)  # The intent (send_money, buy_airtime, pay_bill, etc.)
    slot_values = Column(JSON, nullable=False)  # Stored slots with their values
    
    # Payment details extracted from the successful transaction
    payment_method = Column(String(3), nullable=True)  # MTN, VOD, AIR, BNK, MAS, VIS, etc.
    recipient_phone = Column(String(20), nullable=True)  # For send_money, buy_airtime
    recipient_name = Column(String(100), nullable=True)  # Display name for recipient
    account_number = Column(String(50), nullable=True)  # For bill payments
    bill_provider = Column(String(100), nullable=True)  # For bill payments
    
    # Transaction details
    last_amount = Column(String(20), nullable=True)  # Last amount used in this payflow
    requires_confirmation = Column(Boolean, default=True, nullable=False)  # User must confirm before execution
    is_active = Column(Boolean, default=True, nullable=False)  # Whether this payflow can be used

    # Metadata
    last_used_at = Column(DateTime, nullable=True)  # Last execution timestamp
    created_at = Column(DateTime, default=datetime.now, nullable=False)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, nullable=False)

    def __repr__(self):
        return f"<Payflow(id={self.id}, user_id={self.user_id}, name={self.name}, intent={self.intent_name})>"
