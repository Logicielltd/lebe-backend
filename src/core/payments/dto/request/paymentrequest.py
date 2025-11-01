from enum import Enum
from pydantic import BaseModel, Field
from typing import Optional
from decimal import Decimal
from datetime import datetime

class PaymentRequest(BaseModel):
    customer_number: str
    amount: Decimal
    exttrid: Optional[int] = None
    reference: Optional[str] = None
    nw: Optional[str] = None
    bank_code: Optional[str] = None
    recipient_name: Optional[str] = None
    trans_type: Optional[str] = None
    callback_url: Optional[str] = None
    service_id: Optional[str] = None
    ts: Optional[str] = None
    nickname: Optional[str] = None