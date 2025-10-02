from pydantic import BaseModel, Field
from datetime import datetime
from decimal import Decimal
from typing import Optional

from core.payments.model.bill import BillFrequency, BillStatus, BillingType
from core.payments.model.paymentmethod import PaymentMethod

class BillUpdate(BaseModel):
    form_id: Optional[int] = Field(None, description="ID of the associated form")
    discount_id: Optional[int] = Field(None, description="ID of the applied discount")
    service_name: Optional[str] = Field(None, description="Name of the service being billed")
    billing_type: Optional[BillingType] = Field(None, description="Type of billing")
    currency: Optional[str] = Field(None, description="Currency code")
    amount: Optional[Decimal] = Field(None, ge=0, description="Bill amount", max_digits=10, decimal_places=2)
    frequency: Optional[BillFrequency] = Field(None, description="Billing frequency")
    payment_method: Optional[PaymentMethod] = Field(None, description="Payment method")
    status: Optional[BillStatus] = Field(None, description="Bill status")

    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "service_name": "Updated Premium Subscription",
                "amount": "89.99",
                "status": "ACTIVE"
            }
        }