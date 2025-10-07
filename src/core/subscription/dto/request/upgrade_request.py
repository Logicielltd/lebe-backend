from pydantic import BaseModel, Field
from typing import Optional


class UpgradeRequest(BaseModel):
    new_plan_id: int = Field(..., gt=0, description="ID of the new subscription plan to upgrade to")
    phone: str = Field(..., description="User's phone number")
    payment_reference: Optional[str] = Field(None, max_length=255, description="Payment transaction reference")