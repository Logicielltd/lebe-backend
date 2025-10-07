from pydantic import BaseModel, Field
from typing import Optional


class SubscribeRequest(BaseModel):
    plan_id: int = Field(..., gt=0, description="ID of the subscription plan")
    payment_reference: Optional[str] = Field(None, max_length=255, description="Payment transaction reference")