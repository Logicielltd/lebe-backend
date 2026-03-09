
from fastapi import APIRouter, Depends, HTTPException, status, Query
from datetime import datetime
from typing import Dict, List, Optional
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
            age=user.age,
            income_level=user.income_level,
            occupation=user.occupation,
            financial_goals=user.financial_goals,
            risk_tolerance=user.risk_tolerance,
            location=user.location,

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

    # get user by phone number
    def get_user_by_phone(self, phone_number: str) -> UserResponse:
        user = self.db.query(User).filter(User.phone == phone_number).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        return UserResponse(
            id=user.id,
            username=user.username,
            email=user.email,
            phone=user.phone,
            hashed_pin=user.hashed_pin,
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

    def update_user_details(self, user_id: str, update_data: Dict) -> UserResponse:
        """
        Update user profile details
        
        Args:
            user_id: User identifier
            update_data: Dictionary containing fields to update (first_name, last_name, phone, location, occupation, income_level, financial_goals, risk_tolerance)
            
        Returns:
            Updated UserResponse
        """
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Define allowed fields to update
        allowed_fields = [
            "first_name", "last_name", "phone", "location", 
            "occupation", "income_level", "financial_goals", "risk_tolerance"
        ]
        
        # Update only provided and allowed fields
        for field, value in update_data.items():
            if field in allowed_fields and value is not None:
                setattr(user, field, value)
                logger.info(f"Updated user {user_id} field '{field}' to '{value}'")
        
        self.db.commit()
        logger.info(f"User profile updated successfully for user {user_id}")
        
        return UserResponse(
            id=user.id,
            username=user.username,
            email=user.email,
            first_name=user.first_name,
            last_name=user.last_name,
            is_active=user.is_active,
            created_at=user.created_at
        )

    def get_user_profile(self, user_id: str) -> Dict:
        """
        Get complete user profile details
        
        Args:
            user_id: User identifier
            
        Returns:
            Dictionary with user profile details
        """
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        return {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "phone": user.phone,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "is_active": user.is_active,
            "location": getattr(user, "location", None),
            "occupation": getattr(user, "occupation", None),
            "income_level": getattr(user, "income_level", None),
            "financial_goals": getattr(user, "financial_goals", None),
            "risk_tolerance": getattr(user, "risk_tolerance", None),
            "created_at": user.created_at
        }