from pydantic import BaseModel, Field, validator
from typing import Optional, List
from core.subscription.model.subscription_plan import BillingPeriod
import json


class CreatePlanRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="Name of the subscription plan")
    price: float = Field(..., gt=0, description="Price per billing period")
    billing_period: BillingPeriod = Field(BillingPeriod.MONTHLY, description="Billing period (monthly or annually)")
    billing_period_count: int = Field(1, gt=0, description="Number of billing periods (e.g., 3 for 3 months)")
    features: List[str] = Field(..., description="List of features")
    description: Optional[str] = Field(None, max_length=500, description="Description of the plan")
    is_active: bool = Field(True, description="Whether the plan is active")
    
    @validator('features')
    def convert_features_to_string(cls, v):
        return json.dumps(v)