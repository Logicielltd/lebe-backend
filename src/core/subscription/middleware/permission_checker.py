from functools import wraps
from fastapi import HTTPException, status, Depends
from sqlalchemy.orm import Session
from utilities.dbconfig import get_db
from core.subscription.service.subscription_service import SubscriptionService
from typing import List, Optional, Callable, Any


class SubscriptionPermissionChecker:
    """Middleware for checking subscription-based permissions"""
    
    def __init__(self, db: Session):
        self.subscription_service = SubscriptionService(db)
    
    def check_subscription_required(self, user_id: str) -> bool:
        """Check if user has any active subscription"""
        subscription = self.subscription_service.get_user_active_subscription(user_id)
        return subscription is not None and subscription.is_active
    
    def check_feature_access(self, user_id: str, required_feature: str) -> bool:
        """Check if user has access to specific feature"""
        return self.subscription_service.check_user_has_feature(user_id, required_feature)
    
    def check_plan_access(self, user_id: str, required_plans: List[str]) -> bool:
        """Check if user has access to specific plan tiers"""
        subscription = self.subscription_service.get_user_active_subscription(user_id)
        if not subscription or not subscription.is_active:
            return False
        
        return subscription.plan.name.lower() in [plan.lower() for plan in required_plans]


# Dependency to get permission checker
def get_permission_checker(db: Session = Depends(get_db)) -> SubscriptionPermissionChecker:
    return SubscriptionPermissionChecker(db)


# Decorator for requiring active subscription
def require_active_subscription(get_current_user_id: Callable[[], str]):
    """
    Decorator to require user to have an active subscription
    
    Usage:
    @require_active_subscription(get_current_user_id)
    def protected_endpoint():
        pass
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Extract user_id and db from kwargs
            current_user_id = kwargs.get('current_user_id') or get_current_user_id()
            db = kwargs.get('db')
            
            if not db:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Database session not available"
                )
            
            checker = SubscriptionPermissionChecker(db)
            
            if not checker.check_subscription_required(current_user_id):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Active subscription required to access this feature"
                )
            
            return await func(*args, **kwargs) if asyncio.iscoroutinefunction(func) else func(*args, **kwargs)
        return wrapper
    return decorator


# Decorator for requiring specific feature access
def require_feature(feature: str, get_current_user_id: Callable[[], str]):
    """
    Decorator to require user to have access to specific feature
    
    Usage:
    @require_feature("premium_analytics", get_current_user_id)
    def analytics_endpoint():
        pass
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            current_user_id = kwargs.get('current_user_id') or get_current_user_id()
            db = kwargs.get('db')
            
            if not db:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Database session not available"
                )
            
            checker = SubscriptionPermissionChecker(db)
            
            if not checker.check_feature_access(current_user_id, feature):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Your subscription plan does not include access to '{feature}'"
                )
            
            return await func(*args, **kwargs) if asyncio.iscoroutinefunction(func) else func(*args, **kwargs)
        return wrapper
    return decorator


# Decorator for requiring specific plan tiers
def require_plan_tier(required_plans: List[str], get_current_user_id: Callable[[], str]):
    """
    Decorator to require user to have specific plan tier
    
    Usage:
    @require_plan_tier(["Premium", "Pro"], get_current_user_id)
    def premium_endpoint():
        pass
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            current_user_id = kwargs.get('current_user_id') or get_current_user_id()
            db = kwargs.get('db')
            
            if not db:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Database session not available"
                )
            
            checker = SubscriptionPermissionChecker(db)
            
            if not checker.check_plan_access(current_user_id, required_plans):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"This feature requires one of these subscription plans: {', '.join(required_plans)}"
                )
            
            return await func(*args, **kwargs) if asyncio.iscoroutinefunction(func) else func(*args, **kwargs)
        return wrapper
    return decorator


# FastAPI dependency for checking permissions
def check_subscription_permission(
    required_feature: Optional[str] = None,
    required_plans: Optional[List[str]] = None,
    require_subscription: bool = True
):
    """
    FastAPI dependency for checking subscription permissions
    
    Usage:
    @app.get("/premium-feature")
    def premium_feature(
        permission_check = Depends(check_subscription_permission(required_feature="premium_analytics"))
    ):
        pass
    """
    def permission_dependency(
        current_user_id: str = Depends(get_current_user_id),  # You'll need to implement this
        db: Session = Depends(get_db)
    ):
        checker = SubscriptionPermissionChecker(db)
        
        # Check if subscription is required
        if require_subscription and not checker.check_subscription_required(current_user_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Active subscription required to access this feature"
            )
        
        # Check feature access
        if required_feature and not checker.check_feature_access(current_user_id, required_feature):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Your subscription plan does not include access to '{required_feature}'"
            )
        
        # Check plan tier access
        if required_plans and not checker.check_plan_access(current_user_id, required_plans):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"This feature requires one of these subscription plans: {', '.join(required_plans)}"
            )
        
        return {"access_granted": True}
    
    return permission_dependency