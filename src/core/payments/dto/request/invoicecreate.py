from pydantic import BaseModel, EmailStr, Field
from datetime import datetime
from decimal import Decimal
from typing import Optional

class InvoiceCreate(BaseModel):
    bill_id: Optional[int] = Field(None, description="ID of the associated bill")
    invoice_number: str = Field(..., description="Unique invoice number")
    customer_name: str = Field(..., description="Name of the customer")
    customer_email: EmailStr = Field(..., description="Email address of the customer")
    service_name: str = Field(..., description="Name of the service being billed")
    amount: Decimal = Field(..., ge=0, description="Invoice amount", max_digits=10, decimal_places=2)

    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "bill_id": 123,
                "invoice_number": "INV-2023-001",
                "customer_name": "John Doe",
                "customer_email": "john.doe@example.com",
                "service_name": "Premium Subscription",
                "amount": "99.99"
            }
        }