from pydantic import BaseModel, Field
from typing import Optional


class UpdatePlanRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100, description="Name of the subscription plan")
    price: Optional[float] = Field(None, gt=0, description="Monthly price of the plan")
    features: Optional[str] = Field(None, description="Comma-separated list of features or JSON string")
    description: Optional[str] = Field(None, max_length=500, description="Description of the plan")
    is_active: Optional[bool] = Field(None, description="Whether the plan is active")