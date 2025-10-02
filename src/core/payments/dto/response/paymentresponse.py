from enum import Enum
from pydantic import BaseModel, Field
from typing import Optional
from decimal import Decimal
from datetime import datetime

class PaymentResponse(BaseModel):
    resp_code: Optional[str] = Field(default=None, alias="resp_code")
    resp_desc: Optional[str] = Field(default=None, alias="resp_desc")

    class Config:
        populate_by_name = True  # allows using field names or aliases