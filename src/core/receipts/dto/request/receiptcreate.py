from pydantic import BaseModel
from typing import Dict, Any, Optional
from datetime import datetime

class ReceiptCreateRequest(BaseModel):
    transaction_id: str
    user_id: str
    transaction_type: str
    amount: str
    status: str
    sender: str
    receiver: str
    payment_method: str
    timestamp: datetime
    # Optional loan-specific fields
    interest_rate: Optional[str] = None
    loan_period: Optional[str] = None
    expected_pay_date: Optional[str] = None
    penalty_rate: Optional[str] = None