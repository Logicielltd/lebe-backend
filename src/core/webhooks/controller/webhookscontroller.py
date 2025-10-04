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
    auth_service = AuthService(db)

    user_in_db_status = auth_service.validate_user(dialog_payload.phone)

    return nlp_engine.respond(
        user_in_db_status= user_in_db_status,
        data=dialog_payload.data
    )
