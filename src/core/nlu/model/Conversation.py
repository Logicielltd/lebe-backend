
from sqlalchemy import Column, String, Text, DateTime, JSON, Integer, Date, UniqueConstraint
from sqlalchemy import JSON, Column, Integer, String, DateTime
from utilities.dbconfig import Base
from datetime import datetime

class DailyConversation(Base):
    """PostgreSQL model for daily conversation batches"""
    __tablename__ = "daily_conversations"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String, nullable=False, index=True)
    conversation_date = Column(Date, nullable=False, index=True)
    conversation_state = Column(JSON, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # CORRECTED: Proper UniqueConstraint syntax
    __table_args__ = (
        UniqueConstraint('user_id', 'conversation_date', name='unique_user_date'),
    )