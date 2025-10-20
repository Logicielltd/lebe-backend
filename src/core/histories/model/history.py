from sqlalchemy import Column, String, DateTime, Text, Float, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.declarative import declarative_base
import uuid
from datetime import datetime

Base = declarative_base()

class History(Base):
    __tablename__ = "histories"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(String, nullable=False, index=True)
    intent = Column(String, nullable=False)  # e.g., "send_money", "buy_airtime"
    transaction_type = Column(String, nullable=False)  # "debit", "credit"
    amount = Column(Float, nullable=True)
    currency = Column(String, default="GHS")
    recipient = Column(String, nullable=True)
    phone_number = Column(String, nullable=True)
    data_plan = Column(String, nullable=True)
    category = Column(String, nullable=True)  # For budgets, expenses
    status = Column(String, default="completed")  # "completed", "failed", "pending"
    description = Column(Text, nullable=True)
    transaction_metadata = Column(JSON, nullable=True)  # Additional transaction data
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        return {
            "id": str(self.id),
            "user_id": self.user_id,
            "intent": self.intent,
            "transaction_type": self.transaction_type,
            "amount": self.amount,
            "currency": self.currency,
            "recipient": self.recipient,
            "phone_number": self.phone_number,
            "data_plan": self.data_plan,
            "category": self.category,
            "status": self.status,
            "description": self.description,
            "metadata": self.transaction_metadata,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }