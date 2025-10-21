from pydantic import BaseModel, Field, validator
from typing import Optional, Dict, Any
from datetime import datetime
from uuid import UUID

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
    metadata: Optional[Dict[str, Any]] = Field(None, alias="transaction_metadata")
    created_at: datetime
    updated_at: datetime

    @validator('id', pre=True)
    def convert_id_to_str(cls, v):
        if isinstance(v, UUID):
            return str(v)
        return v

    class Config:
        orm_mode = True
        allow_population_by_field_name = True

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