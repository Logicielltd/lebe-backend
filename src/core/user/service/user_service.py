
from fastapi import APIRouter, Depends, HTTPException, status, Query
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel
from core.auth.service.sessiondriver import SessionDriver, TokenData
from fastapi_jwt_auth import AuthJWT
from core.exceptions import *
from utilities.dbconfig import SessionLocal
from sqlalchemy.orm import Session
from core.user.model.User import User
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# DTO Models
from core.user.dto.request.user_filter_request import UserFilterRequest
from core.user.dto.response.message_response import MessageResponse
from core.user.dto.response.user_response import UserResponse

# Service Class
class UserService:
    def __init__(self, db: Session):
        self.db = db

    def get_current_user(self, email: str) -> UserResponse:
        user = self.db.query(User).filter(User.email == email).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        return UserResponse(
            id=user.id,
            username=user.username,
            email=user.email,
            first_name=user.first_name,
            last_name=user.last_name,
            is_active=user.is_active,
            created_at=user.created_at
        )

    def get_user_by_id(self, user_id: str) -> UserResponse:
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        return UserResponse(
            id=user.id,
            username=user.username,
            email=user.email,
            first_name=user.first_name,
            last_name=user.last_name,
            is_active=user.is_active,
            created_at=user.created_at
        )

    def set_user_enabled_status(self, user_id: str, enabled: bool) -> MessageResponse:
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        user.is_active = enabled
        self.db.commit()
        status_msg = "enabled" if enabled else "disabled"
        return MessageResponse(message=f"User {status_msg} successfully")

    def delete_user(self, user_id: str) -> MessageResponse:
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        self.db.delete(user)
        self.db.commit()
        return MessageResponse(message="User deleted successfully")

    def get_all_users_paged(self, page: int, size: int):
        query = self.db.query(User)
        total = query.count()
        users = query.offset((page - 1) * size).limit(size).all()
        
        return {
            "total": total,
            "page": page,
            "size": size,
            "users": [
                UserResponse(
                    id=user.id,
                    username=user.username,
                    email=user.email,
                    first_name=user.first_name,
                    last_name=user.last_name,
                    is_active=user.is_active,
                    created_at=user.created_at
                ) for user in users
            ]
        }

    def update_user_role(self, user_id: str, role_id: str) -> MessageResponse:
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        # Assuming you have role update logic here
        user.role_id = role_id
        self.db.commit()
        return MessageResponse(message="User role updated successfully")