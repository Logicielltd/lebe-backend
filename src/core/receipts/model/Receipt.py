from sqlalchemy import Column, String, DateTime, Text
from sqlalchemy.sql import func
from sqlalchemy.orm import Mapped, mapped_column
from utilities.dbconfig import Base
from datetime import datetime

class Receipt(Base):
    __tablename__ = "receipts"
    
    id: Mapped[str] = mapped_column(String(20), primary_key=True, nullable=False, unique=True)
    transaction_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    image_url: Mapped[str] = mapped_column(Text, nullable=False)
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    
    def __repr__(self):
        return f"<Receipt(id={self.id}, transaction_id={self.transaction_id})>"