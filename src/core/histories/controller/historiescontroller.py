from core.auth.service.authservice import AuthService
from core.histories.dto.response.historyresponse import HistoryListResponseDTO, HistoryResponseDTO, HistorySummaryDTO
from core.histories.service.historyservice import HistoryService
from fastapi import APIRouter, Depends, HTTPException, status, Query
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel
from core.auth.service.sessiondriver import SessionDriver, TokenData
from fastapi_jwt_auth import AuthJWT
from core.exceptions import *
from core.notification.dto.request.notificationcreate import NotificationCreateRequest
from core.notification.dto.request.notificationupdate import NotificationUpdateRequest
from utilities.dbconfig import SessionLocal
from sqlalchemy.orm import Session
import logging
from core.notification.model.Notification import Notification, NotificationStatus, NotificationType
from core.user.model.User import User

# DTO Models
from core.notification.dto.response.notification_response import NotificationResponse
from core.notification.dto.response.paged_notifications import PagedNotificationResponse
from core.notification.dto.response.message_response import MessageResponse

from core.notification.service.notification_service import NotificationService
from fastapi_jwt_auth.exceptions import MissingTokenError

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Reuse your existing token validation and DB dependencies
from core.user.controller.usercontroller import validate_token, get_db

# Controller (Router)
histories_routes = APIRouter()

def get_history_service(db: Session = Depends(get_db)) -> HistoryService:
    return HistoryService(db)

def get_current_user(token: str = Depends(AuthService.oauth2_scheme)):
    return AuthService.verify_token(token)

@histories_routes.get("/", response_model=HistoryListResponseDTO)
async def get_user_histories(
    current_user: dict = Depends(get_current_user),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    intent: Optional[str] = None,
    transaction_type: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    history_service: HistoryService = Depends(get_history_service)
):
    """Get paginated transaction histories for the current user"""
    
    user_id = current_user["sub"]
    histories = history_service.get_user_histories(
        user_id=user_id,
        page=page,
        page_size=page_size,
        intent=intent,
        transaction_type=transaction_type,
        start_date=start_date,
        end_date=end_date
    )
    
    # For simplicity, returning all histories. In production, you'd want proper pagination counts
    return HistoryListResponseDTO(
        histories=histories,
        total=len(histories),
        page=page,
        page_size=page_size,
        total_pages=(len(histories) + page_size - 1) // page_size
    )

@histories_routes.get("/{history_id}", response_model=HistoryResponseDTO)
async def get_history(
    history_id: str,
    current_user: dict = Depends(get_current_user),
    history_service: HistoryService = Depends(get_history_service)
):
    """Get a specific transaction history by ID"""
    
    user_id = current_user["sub"]
    history = history_service.get_history_by_id(history_id, user_id)
    
    if not history:
        raise HTTPException(status_code=404, detail="Transaction history not found")
    
    return history

@histories_routes.get("/summary/overview", response_model=HistorySummaryDTO)
async def get_transaction_summary(
    days: int = Query(30, ge=1, le=365),
    current_user: dict = Depends(get_current_user),
    history_service: HistoryService = Depends(get_history_service)
):
    """Get transaction summary for the current user"""
    
    user_id = current_user["sub"]
    return history_service.get_transaction_summary(user_id, days)

@histories_routes.get("/analytics/spending-by-category")
async def get_spending_by_category(
    days: int = Query(30, ge=1, le=365),
    current_user: dict = Depends(get_current_user),
    history_service: HistoryService = Depends(get_history_service)
):
    """Get spending breakdown by category"""
    
    user_id = current_user["sub"]
    spending = history_service.get_spending_by_category(user_id, days)
    return {"spending_by_category": spending}