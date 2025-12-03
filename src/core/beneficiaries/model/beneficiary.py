from datetime import datetime
from enum import Enum

from sqlalchemy import Boolean, Column, DateTime, Enum as SQLEnum, ForeignKey, Integer, String
from sqlalchemy.orm import relationship, Mapped, mapped_column

from utilities.dbconfig import Base


class AccountType(str, Enum):
    """Account type enumeration"""
    MOBILE_MONEY = "mobile_money"
    BANK_ACCOUNT = "bank_account"
    CARD = "card"


class Beneficiary(Base):
    """
    Beneficiary model for storing saved payment recipients.
    Users can save beneficiaries and send money to them quickly.
    """
    __tablename__ = "beneficiaries"

    id = Column(Integer, primary_key=True, index=True)
    user_id: Mapped[str] = mapped_column(String(20), ForeignKey("users.id"), nullable=False)

    # Beneficiary information
    name = Column(String(100), nullable=False)  # e.g., "John Agyeman"
    customer_number = Column(String(20), nullable=False)  # Mobile money wallet, bank account, or card number
    network = Column(String(3), nullable=False)  # MTN, VOD, AIR, BNK, MAS, VIS
    bank_code = Column(String(4), nullable=True)  # Bank code if network is BNK (e.g., "GCB", "ECO")
    account_type = Column(SQLEnum(AccountType), nullable=False)  # Type of account

    # Status and metadata
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.now, nullable=False)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, nullable=False)

    def __repr__(self):
        return f"<Beneficiary(id={self.id}, user_id={self.user_id}, name={self.name}, network={self.network})>"
