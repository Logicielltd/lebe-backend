from fastapi import APIRouter, Depends, HTTPException, status, Query
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel
from core.auth.service.sessiondriver import SessionDriver, TokenData
from fastapi_jwt_auth import AuthJWT
from core.exceptions import *
from core.webhooks.dto.request.dialogrequest import DialogRequest
from utilities.dbconfig import SessionLocal
from sqlalchemy.orm import Session
import logging
from core.user.model.User import User
from core.nlu.main import LebeNLUSystem
from core.subscription.service.subscription_service import SubscriptionService

# DTO Models
from core.notification.dto.response.message_response import MessageResponse
from core.webhooks.dto.response.message_response import LebeResponse

from fastapi_jwt_auth.exceptions import MissingTokenError
from core.auth.service.authservice import AuthService

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Reuse your existing token validation and DB dependencies
from core.user.controller.usercontroller import validate_token, get_db

# Controller (Router)
webhooks_routes = APIRouter()

@webhooks_routes.post("/start-dialog", response_model=LebeResponse)
def start_dialog(
    dialog_payload: DialogRequest,
    db: Session = Depends(get_db)
):

    nlu_system = LebeNLUSystem()

    subscription_service = SubscriptionService(db)

    result = subscription_service.get_user_subscription_status_by_phone(dialog_payload.phone)

    
    nlu_system.initialize_user(dialog_payload.phone, "00000")
    
    response_message = nlu_system.process_message(dialog_payload.phone, dialog_payload.message , result["has_active_subscription"])
    
    return LebeResponse(message=response_message)