from fastapi import APIRouter, Depends, HTTPException, status, Query
from datetime import datetime
from typing import List, Optional
import jwt
from pydantic import BaseModel
from core.auth.service.sessiondriver import SessionDriver, TokenData
from fastapi_jwt_auth import AuthJWT
from core.profile.dto.request.profileupdate import ProfileUpdateRequest
from core.exceptions import *
from utilities.dbconfig import SessionLocal
from sqlalchemy.orm import Session
from core.user.model.User import User
from core.profile.model.Profile import Profile
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# DTO Models
from core.user.dto.response.message_response import MessageResponse
from core.profile.dto.response.profile_response import ProfileResponse

from core.profile.service.profile_service import ProfileService
from fastapi_jwt_auth.exceptions import MissingTokenError

# Reuse the same token validation from user controller
from core.user.controller.usercontroller import validate_token

# Controller (Router)
profile_routes = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@profile_routes.get("/me", response_model=ProfileResponse)
def get_current_user_profile(
    authjwt: AuthJWT = Depends(validate_token), 
    db: Session = Depends(get_db)
):
    current_user_email = authjwt.get_jwt_subject()
    profile_service = ProfileService(db)
    return profile_service.get_user_profile(current_user_email)

@profile_routes.put("/me", response_model=ProfileResponse)
def update_current_user_profile(
    profile_data: ProfileUpdateRequest,
    authjwt: AuthJWT = Depends(validate_token),
    db: Session = Depends(get_db)
):
    current_user_email = authjwt.get_jwt_subject()
    profile_service = ProfileService(db)
    return profile_service.update_user_profile(current_user_email, profile_data)

@profile_routes.get("/user/{user_id}", response_model=ProfileResponse)
def get_profile_by_user_id(
    user_id: str,
    authjwt: AuthJWT = Depends(validate_token),
    db: Session = Depends(get_db)
):
    # Add admin check here if needed
    profile_service = ProfileService(db)
    return profile_service.get_profile_by_user_id(user_id)

@profile_routes.put("/user/{user_id}", response_model=ProfileResponse)
def update_profile_by_user_id(
    user_id: str,
    profile_data: ProfileUpdateRequest,
    authjwt: AuthJWT = Depends(validate_token),
    db: Session = Depends(get_db)
):
    # Add admin check here if needed
    profile_service = ProfileService(db)
    return profile_service.update_profile_by_user_id(user_id, profile_data)