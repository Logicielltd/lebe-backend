from pydantic import BaseModel
from typing import Optional, List, Any, Dict
from datetime import datetime


class PlanResponse(BaseModel):
    id: int
    name: str
    price: float
    features: str
    description: Optional[str]
    is_active: bool


class SubscriptionResponse(BaseModel):
    success: bool
    message: str
    subscription_id: Optional[int] = None
    plan_name: Optional[str] = None
    expires_at: Optional[str] = None
    amount_paid: Optional[float] = None
    days_extended: Optional[int] = None


class SubscriptionStatusResponse(BaseModel):
    has_active_subscription: bool
    subscription_id: Optional[int] = None
    plan_name: Optional[str] = None
    features: Optional[str] = None
    amount_paid: Optional[float] = None
    expires_at: Optional[str] = None
    days_remaining: int
    status: str


class PlansListResponse(BaseModel):
    success: bool
    plans: List[PlanResponse]
    total_count: int