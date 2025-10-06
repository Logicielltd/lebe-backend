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

    def hash_password(self, password: str) -> str:
        """Hash a plain-text password."""
        return pwd_context.hash(password)

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verify a plain-text password against a hashed one."""
        return pwd_context.verify(plain_password, hashed_password)

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
            profile_picture=request.profile_picture,
            bio=request.bio,
            email=request.email,
            hashed_password=self.hash_password(request.pin),
            created_at=datetime.now(timezone.utc),
        )

        self.db.add(db_user)
        self.db.commit()
        self.db.refresh(db_user)

        return {
            "message": "User account created successfully",
            "user_id": db_user.id,
        }

    def validate_user(self, phone: str):
        
        db_user = self.db.query(User).filter(User.phone == phone).first()

        # return True if user exists, else False
        return db_user is not None
