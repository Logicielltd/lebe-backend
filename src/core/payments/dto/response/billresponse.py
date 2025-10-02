from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
from core.payments.model.bill import BillingType, BillFrequency, BillStatus, PaymentMethod

class BillResponse(BaseModel):
    id: int
    form_id: Optional[int] = None
    discount_id: Optional[int] = None
    service_name: Optional[str] = None
    billing_type: Optional[BillingType] = None
    currency: Optional[str] = None
    amount: Optional[float] = None
    frequency: Optional[BillFrequency] = None
    payment_method: Optional[PaymentMethod] = None
    status: Optional[BillStatus] = None
    created_on: datetime
    updated_on: datetime

    class Config:
        from_attributes = True