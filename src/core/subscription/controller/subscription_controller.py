from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from utilities.dbconfig import get_db
from src.core.subscription.service.subscription_service import SubscriptionService
from src.core.subscription.dto.request.subscribe_request import SubscribeRequest
from src.core.subscription.dto.request.upgrade_request import UpgradeRequest
from src.core.subscription.dto.request.cancel_request import CancelRequest
from src.core.subscription.dto.request.create_plan_request import CreatePlanRequest
from src.core.subscription.dto.request.update_plan_request import UpdatePlanRequest
from src.core.subscription.dto.response.subscription_response import (
    SubscriptionResponse, 
    SubscriptionStatusResponse, 
    PlansListResponse,
    PlanResponse,
    PlanCreateResponse
)

subscription_routes = APIRouter()


# Helper function to get current user ID (you'll need to implement this based on your auth system)
def get_current_user_id() -> str:
    # TODO: Replace with actual user authentication
    # This should extract user_id from JWT token or session
    return "sample_user_id"


@subscription_routes.get("/plans", response_model=PlansListResponse)
def get_subscription_plans(db: Session = Depends(get_db)):
    """Get all available subscription plans"""
    subscription_service = SubscriptionService(db)
    plans = subscription_service.get_all_plans()
    
    plan_responses = [
        PlanResponse(
            id=plan.id,
            name=plan.name,
            price=plan.price,
            features=plan.features,
            description=plan.description,
            is_active=plan.is_active
        )
        for plan in plans
    ]
    
    return PlansListResponse(
        success=True,
        plans=plan_responses,
        total_count=len(plan_responses)
    )


@subscription_routes.post("/subscribe", response_model=SubscriptionResponse)
def subscribe_to_plan(
    request: SubscribeRequest,
    db: Session = Depends(get_db)
):
    """Subscribe user to a subscription plan using phone number"""
    subscription_service = SubscriptionService(db)
    result = subscription_service.subscribe_user_by_phone(
        phone=request.phone,
        plan_id=request.plan_id,
        payment_reference=request.payment_reference
    )
    
    if not result["success"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result["message"]
        )
    
    return SubscriptionResponse(**result)


@subscription_routes.post("/upgrade", response_model=SubscriptionResponse)
def upgrade_subscription(
    request: UpgradeRequest,
    db: Session = Depends(get_db)
):
    """Upgrade user's current subscription to a higher plan using phone number"""
    subscription_service = SubscriptionService(db)
    result = subscription_service.upgrade_subscription_by_phone(
        phone=request.phone,
        new_plan_id=request.new_plan_id,
        payment_reference=request.payment_reference
    )
    
    if not result["success"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result["message"]
        )
    
    return SubscriptionResponse(**result)


@subscription_routes.post("/cancel", response_model=SubscriptionResponse)
def cancel_subscription(
    request: CancelRequest,
    db: Session = Depends(get_db)
):
    """Cancel user's current subscription using phone number"""
    subscription_service = SubscriptionService(db)
    result = subscription_service.cancel_subscription_by_phone(
        phone=request.phone,
        reason=request.reason
    )
    
    if not result["success"]:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=result["message"]
        )
    
    return SubscriptionResponse(**result)


@subscription_routes.get("/status/{phone}", response_model=SubscriptionStatusResponse)
def get_subscription_status(
    phone: str,
    db: Session = Depends(get_db)
):
    """Get user's current subscription status using phone number"""
    subscription_service = SubscriptionService(db)
    result = subscription_service.get_user_subscription_status_by_phone(phone)
    
    return SubscriptionStatusResponse(**result)


@subscription_routes.get("/check-feature/{feature}/{phone}")
def check_user_feature(
    feature: str,
    phone: str,
    db: Session = Depends(get_db)
):
    """Check if user has access to a specific feature using phone number"""
    subscription_service = SubscriptionService(db)
    return subscription_service.check_user_has_feature_by_phone(phone, feature)


# ADMIN ENDPOINTS
@subscription_routes.post("/admin/plans", response_model=PlanCreateResponse)
def create_subscription_plan(
    request: CreatePlanRequest,
    db: Session = Depends(get_db)
    # TODO: Add admin authentication middleware here
):
    """Create a new subscription plan (Admin only)"""
    subscription_service = SubscriptionService(db)
    result = subscription_service.create_subscription_plan(
        name=request.name,
        price=request.price,
        billing_period=request.billing_period,
        billing_period_count=request.billing_period_count,
        features=request.features,
        description=request.description,
        is_active=request.is_active
    )
    
    if not result["success"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result["message"]
        )
    
    plan = result["plan"]
    return PlanCreateResponse(
        success=True,
        message=result["message"],
        plan=PlanResponse(
            id=plan.id,
            name=plan.name,
            price=plan.price,
            features=plan.features,
            description=plan.description,
            is_active=plan.is_active
        )
    )



@subscription_routes.put("/admin/plans/{plan_id}", response_model=SubscriptionResponse)
def update_subscription_plan(
    plan_id: int,
    request: UpdatePlanRequest,
    db: Session = Depends(get_db)
    # TODO: Add admin authentication middleware here
):
    """Update a subscription plan (Admin only)"""
    subscription_service = SubscriptionService(db)
    
    # Filter out None values
    updates = {k: v for k, v in request.dict().items() if v is not None}
    
    result = subscription_service.update_subscription_plan(plan_id, **updates)
    
    if not result["success"]:
        status_code = status.HTTP_404_NOT_FOUND if "not found" in result["message"].lower() else status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=status_code, detail=result["message"])
    
    return SubscriptionResponse(**result)


@subscription_routes.delete("/admin/plans/{plan_id}", response_model=SubscriptionResponse)
def delete_subscription_plan(
    plan_id: int,
    db: Session = Depends(get_db)
    # TODO: Add admin authentication middleware here
):
    """Delete a subscription plan (Admin only)"""
    subscription_service = SubscriptionService(db)
    result = subscription_service.delete_subscription_plan(plan_id)
    
    if not result["success"]:
        status_code = status.HTTP_404_NOT_FOUND if "not found" in result["message"].lower() else status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=status_code, detail=result["message"])
    
    return SubscriptionResponse(**result)