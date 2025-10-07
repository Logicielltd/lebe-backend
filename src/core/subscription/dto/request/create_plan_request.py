from pydantic import BaseModel, Field
from typing import Optional


class CreatePlanRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="Name of the subscription plan")
    price: float = Field(..., gt=0, description="Monthly price of the plan")
    features: str = Field(..., description="Comma-separated list of features or JSON string")
    description: Optional[str] = Field(None, max_length=500, description="Description of the plan")
    is_active: bool = Field(True, description="Whether the plan is active")