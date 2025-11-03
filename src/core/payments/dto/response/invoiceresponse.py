from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
from core.payments.model.invoice import Invoice

class InvoiceResponse(BaseModel):
    id: int
    bill_id: Optional[int] = None
    invoice_number: str
    customer_name: str
    customer_email: str
    service_name: str
    amount: float
    created_on: datetime
    updated_on: datetime

    class Config:
        from_attributes = True  # Allows ORM mode for SQLAlchemy objects