from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime

class HistoryResponseDTO(BaseModel):
    id: str
    user_id: str
    intent: str
    transaction_type: str
    amount: Optional[float] = None
    currency: str = "GHS"
    recipient: Optional[str] = None
    phone_number: Optional[str] = None
    data_plan: Optional[str] = None
    category: Optional[str] = None
    status: str = "completed"
    description: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

class HistoryListResponseDTO(BaseModel):
    histories: list[HistoryResponseDTO]
    total: int
    page: int
    page_size: int
    total_pages: int

class HistorySummaryDTO(BaseModel):
    total_transactions: int
    total_amount: float
    transaction_types: Dict[str, int]
    recent_transactions: list[HistoryResponseDTO]