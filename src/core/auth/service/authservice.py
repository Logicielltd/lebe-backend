from typing import Optional
from fastapi.responses import JSONResponse
import jwt
from passlib.context import CryptContext
from fastapi_jwt_auth import AuthJWT
from sqlalchemy.orm import Session
from pydantic import BaseModel
from fastapi import HTTPException
from fastapi import status
from datetime import datetime, timedelta, timezone
from core.auth.service.sessiondriver import SessionDriver
from core.exceptions.AuthException import InvalidCredentialsError
from core.exceptions.UserException import UserAlreadyExistsError
from core.user.model.User import User
from core.otp.service.otpservice import OTPService
import secrets
import string
import logging

logger = logging.getLogger(__name__)

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
class AuthService:
    def __init__(self, db: Session):
        self.db = db
        self.session_driver = SessionDriver()
        self.otp_service = OTPService(db)

    def hash_password(self, password: str) -> str:
        """Hash a plain-text password."""
        return pwd_context.hash(password)

    def verify_password(self, plain_password: str, hashed_pin: str) -> bool:
        """Verify a plain-text password against a hashed one."""
        return pwd_context.verify(plain_password, hashed_pin)

    def generate_user_id(self):
        """Generate a random user ID with alphanumeric characters."""
        alphabet = string.ascii_letters + string.digits
        return "".join(secrets.choice(alphabet) for i in range(20))

    def create_user(self, request: BaseModel):
        """Create a new user in the database."""
        existing_user = (
            self.db.query(User)
            .filter(
                (User.email == request.email) | (User.username == request.username)
            )
            .first()
        )

        if existing_user:
            if existing_user.email == request.email:
                raise UserAlreadyExistsError(field="email")
            else:
                raise UserAlreadyExistsError(field="username")
            
        user_id = self.generate_user_id()

        db_user = User(
            id=user_id,
            username=request.username,
            first_name=request.first_name,
            last_name=request.last_name,
            phone=request.phone,
            email=request.email,
            hashed_pin=self.hash_password(request.pin),
            created_at=datetime.now(timezone.utc),
        )

        self.db.add(db_user)
        self.db.commit()
        self.db.refresh(db_user)

        # Send OTP to phone for verification
        otp_result = self.otp_service.send_otp_phone(request.phone)
        
        return {
            "message": "User account created successfully. Please verify your phone number with the OTP sent to you.",
            "user_id": db_user.id,
            "verification_required": True,
            "otp_sent": otp_result.success
        }

    def validate_user(self, phone: str):
        
        db_user = self.db.query(User).filter(User.phone == phone).first()

        # return True if user exists, else False
        return db_user is not None

    def verify_and_enable_user(self, phone: str, otp: str):
        """Verify OTP and enable user account"""
        # Validate OTP
        is_valid = self.otp_service.validate_otp(phone=phone, otp=otp)
        
        if not is_valid:
            return {
                "success": False,
                "message": "Invalid or expired OTP"
            }
        
        # Find user by phone
        user = self.db.query(User).filter(User.phone == phone).first()
        
        if not user:
            return {
                "success": False,
                "message": "User not found"
            }
        
        # Enable user account
        user.enabled = True
        user.updated_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(user)
        
        return {
            "success": True,
            "message": "Phone number verified successfully. Your account is now active.",
            "user_id": user.id
        }
