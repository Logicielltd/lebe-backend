from pydantic import BaseModel, Field
from datetime import datetime
from decimal import Decimal
from typing import Optional
from core.payments.model.bill import BillFrequency, BillStatus, BillingType
from core.payments.model.paymentmethod import PaymentMethod

class BillCreate(BaseModel):
    form_id: Optional[int] = Field(None, description="ID of the associated form")
    discount_id: Optional[int] = Field(None, description="ID of the applied discount")
    service_name: str = Field(..., description="Name of the service being billed")
    billing_type: BillingType = Field(..., description="Type of billing")
    currency: str = Field(..., description="Currency code")
    amount: Decimal = Field(..., ge=0, description="Bill amount", max_digits=10, decimal_places=2)
    frequency: Optional[BillFrequency] = Field(None, description="Billing frequency")
    payment_method: PaymentMethod = Field(..., description="Payment method")
    status: BillStatus = Field(default=BillStatus.PENDING, description="Bill status")

    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "form_id": 123,
                "discount_id": 1,
                "service_name": "Premium Subscription",
                "billing_type": "RECURRING",
                "currency": "USD",
                "amount": "99.99",
                "frequency": "MONTHLY",
                "payment_method": "CREDIT_CARD",
                "status": "PENDING"
            }
        }