from enum import Enum
from pydantic import BaseModel, Field
from typing import Optional
from decimal import Decimal
from datetime import datetime

class PaymentCallbackResponse(BaseModel):
    trans_id: str
    trans_ref: int
    trans_status: str
    message: Optional[str] = None