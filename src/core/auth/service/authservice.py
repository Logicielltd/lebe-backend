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
            hashed_password=self.hash_password(request.password),
            created_at=datetime.now(timezone.utc),
        )

        self.db.add(db_user)
        self.db.commit()
        self.db.refresh(db_user)

        return {
            "message": "User account created successfully",
            "user_id": db_user.id,
        }

    def authenticate_user(self, email: str, password: str):
        db_user = self.db.query(User).filter(User.email == email).first()

        if not db_user:
            raise InvalidCredentialsError()

        if not self.verify_password(password, db_user.hashed_password):
            raise InvalidCredentialsError()

        return db_user

    def signin(self, user: BaseModel):
        """Login the user by generating a JWT token and returning tokens."""
        db_user = self.authenticate_user(user.email, user.password)

        access_token = self.session_driver.create_access_token(
            data={"sub": db_user.email},
            expires_delta=timedelta(minutes=self.session_driver.ACCESS_TOKEN_EXPIRE_MINUTES)
        )
        
        refresh_token = self.session_driver.create_refresh_token(
            data={"sub": db_user.email}
        )

        self.session_driver.store_tokens(access_token, refresh_token)

        return JSONResponse(
            status_code=200,
            content={
                "status": "Login successful",
                "access_token": access_token,
                "refresh_token": refresh_token,
                "token_type": "bearer",
                "expires_in": self.session_driver.ACCESS_TOKEN_EXPIRE_MINUTES * 60
            },
        )

    def signout(self, token: str):
        try:
            # Decode without expiration check
            payload = jwt.decode(
                token, 
                self.session_driver.SECRET_KEY, 
                algorithms=[self.session_driver.ALGORITHM],
                options={"verify_exp": False}
            )
            email = payload.get("sub")
            
            if not email:
                raise HTTPException(status_code=401, detail="Invalid token")
            
            # Triple protection:
            # 1. Blacklist this specific token
            self.session_driver.blacklist_token(token)
            
            # 2. Remove token storage
            self.session_driver.remove_tokens(email)
            
            return JSONResponse(
                status_code=200,
                content={"message": "Logout successful"}
            )
        except Exception as e:
            logger.error(f"Logout error: {str(e)}")
            # Still attempt to blacklist
            self.session_driver.blacklist_token(token)
            raise HTTPException(status_code=500, detail="Logout processing error")

    def refresh_tokens(self, refresh_token: str):
        """Refresh access token using refresh token"""
        try:
            new_access_token = self.session_driver.refresh_access_token(refresh_token)
            
            return JSONResponse(
                status_code=200,
                content={
                    "access_token": new_access_token,
                    "token_type": "bearer",
                    "expires_in": self.session_driver.ACCESS_TOKEN_EXPIRE_MINUTES * 60
                }
            )
        except HTTPException as e:
            raise e
        except Exception as e:
            logger.error(f"Error refreshing token: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))
        
    def signout_all(self, token: str):
        """Logout the user from all devices by invalidating all their tokens"""
        try:
            payload = jwt.decode(
                token, 
                self.session_driver.SECRET_KEY, 
                algorithms=[self.session_driver.ALGORITHM],
                options={"verify_exp": False}
            )
            email = payload.get("sub")
            
            if not email:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid token"
                )
            
            # Triple protection:
            # 1. Blacklist this specific token
            self.session_driver.blacklist_token(token)
            
            # 2. Remove token storage
            self.session_driver.remove_tokens(email)
            
            return JSONResponse(
                status_code=200,
                content={"message": "Logged out from all devices"}
            )
        except jwt.PyJWTError as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token"
            )
    
    def verify_account(self, email: str):
        """Verify user account using email or username"""
        try:
            db_user = self.db.query(User).filter(User.email == email).first()

            if not db_user:
                raise InvalidCredentialsError()
            
            return JSONResponse(
                status_code=200,
                content={"message": "Account verified successfully"}
            )
            
        except jwt.ExpiredSignatureError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email not valid or expired"
            )
            
    def reset_password(self, request: BaseModel):
        """Reset password using a valid reset token (authenticated version)"""
        try:
            # Verify the reset token
            payload = jwt.decode(
                request.reset_token,
                self.session_driver.SECRET_KEY,
                algorithms=[self.session_driver.ALGORITHM]
            )
            
            if payload.get("type") != "reset":
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid token type"
                )
                
            email = payload.get("sub")
            if not email:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid token payload"
                )
            
            # Find user and update password
            db_user = self.db.query(User).filter(User.email == email).first()
            if not db_user:
                raise InvalidCredentialsError()
                
            db_user.hashed_password = self.hash_password(request.new_password)
            self.db.commit()
            
            # Invalidate all existing tokens
            self.session_driver.remove_tokens(email)
            
            return JSONResponse(
                status_code=200,
                content={"message": "Password reset successfully"}
            )
            
        except jwt.ExpiredSignatureError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Reset token has expired"
            )
        except jwt.PyJWTError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid reset token"
            )

    def reset_password_no_auth(self, request: BaseModel):
        """Reset password without authentication (for forgotten password flow)"""
        try:
            # Find user by email
            db_user = self.db.query(User).filter(User.email == request.email).first()
            if not db_user:
                # Don't reveal whether email exists for security
                return JSONResponse(
                    status_code=200,
                    content={"message": "If the email exists, password has been reset"}
                )
                
            # Update password
            db_user.hashed_password = self.hash_password(request.new_password)
            self.db.commit()
            
            # Invalidate all existing tokens
            self.session_driver.remove_tokens(request.email)
            
            return JSONResponse(
                status_code=200,
                content={"message": "If the email exists, password has been reset"}
            )
            
        except Exception as e:
            logger.error(f"Password reset error: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error resetting password"
            )

    def generate_password_reset_token(self, email: str) -> str:
        """Generate a password reset token for the user"""
        try:
            # Verify user exists
            db_user = self.db.query(User).filter(User.email == email).first()
            if not db_user:
                # Don't reveal whether email exists
                return None
                
            # Create reset token that expires in 1 hour
            reset_data = {
                "sub": email,
                "type": "reset",
                "exp": datetime.now(timezone.utc) + timedelta(hours=1)
            }
            
            return jwt.encode(
                reset_data,
                self.session_driver.SECRET_KEY,
                algorithm=self.session_driver.ALGORITHM
            )
            
        except Exception as e:
            logger.error(f"Error generating reset token: {str(e)}")
            return None