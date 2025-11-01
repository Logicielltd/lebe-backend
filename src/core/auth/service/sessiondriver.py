from datetime import datetime, timedelta
import os
from typing import Dict, Optional
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel
import logging
import redis
import json
# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TokenData(BaseModel):
    email: Optional[str] = None

class SessionDriver:
    def __init__(self):
        # Get Redis host from environment variables (default to 'redis' if not set)
        redis_host = os.getenv("REDIS_HOST", "redis-1")
        redis_port = int(os.getenv("REDIS_PORT", 6379))
        
        self.redis_client = redis.Redis(
            host='localhost',
            port=6379,
            db=0,
            decode_responses=True
        )
        
        # Token configuration
        self.SECRET_KEY = "09d25e094faa6ca2556c818166b7a9563b93f7099f6f0f4caa6cf63b88e8d3e7"
        self.ALGORITHM = "HS256"
        self.ACCESS_TOKEN_EXPIRE_MINUTES = 35
        self.REFRESH_TOKEN_EXPIRE_DAYS = 3
        
        self.oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

    def create_access_token(self, data: dict, expires_delta: Optional[timedelta] = None):
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=15)
        to_encode.update({"exp": expire, "type": "access"})
        encoded_jwt = jwt.encode(to_encode, self.SECRET_KEY, algorithm=self.ALGORITHM)
        return encoded_jwt if isinstance(encoded_jwt, str) else encoded_jwt.decode("utf-8")

    def create_refresh_token(self, data: dict):
        to_encode = data.copy()
        expire = datetime.utcnow() + timedelta(days=self.REFRESH_TOKEN_EXPIRE_DAYS)
        to_encode.update({"exp": expire, "type": "refresh"})
        encoded_jwt = jwt.encode(to_encode, self.SECRET_KEY, algorithm=self.ALGORITHM)
        return encoded_jwt if isinstance(encoded_jwt, str) else encoded_jwt.decode("utf-8")

    def store_tokens(self, access_token: str, refresh_token: str):
        """Store both access and refresh tokens in Redis"""
        try:
            # Decode tokens to get expiration and user info
            access_payload = jwt.decode(access_token, self.SECRET_KEY, algorithms=[self.ALGORITHM])
            refresh_payload = jwt.decode(refresh_token, self.SECRET_KEY, algorithms=[self.ALGORITHM])
            
            email = access_payload.get("sub")
            
            # Prepare token data for storage
            token_data = {
                "access_token": access_token,
                "access_exp": access_payload.get("exp"),
                "refresh_token": refresh_token,
                "refresh_exp": refresh_payload.get("exp")
            }
            
            # Store in Redis with expiration set to refresh token's expiration
            self.redis_client.set(
                f"user:{email}:tokens",
                json.dumps(token_data),
                ex=int((datetime.fromtimestamp(refresh_payload["exp"]) - datetime.now()).total_seconds())
            )
            
        except jwt.PyJWTError as e:
            logger.error(f"Error storing tokens: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Could not store tokens"
            )

    def remove_tokens(self, email: str):
        """Remove tokens for a user from Redis"""
        try:
            self.redis_client.delete(f"user:{email}:tokens")
        except Exception as e:
            logger.error(f"Error removing token: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Could not remove token"
            )

    def validate_token(self, token: str):
        """Validate JWT token and return user email"""
        credentials_exception = HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
        try:
            # First check if token is blacklisted
            if self.redis_client.sismember("blacklisted_tokens", token):
                raise credentials_exception

            # Then verify the token
            payload = jwt.decode(token, self.SECRET_KEY, algorithms=[self.ALGORITHM])
            email: str = payload.get("sub")
            if email is None:
                raise credentials_exception

            # After validating the token, check token version
            user_version = self.redis_client.get(f"user:{email}:token_version")
            token_version = payload.get("version", "0")
            if user_version and user_version > token_version:
                raise credentials_exception
            
            return TokenData(email=email)
        except jwt.ExpiredSignatureError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token expired",
                headers={"WWW-Authenticate": "Bearer"},
            )
        except jwt.PyJWTError:
            raise credentials_exception

    def refresh_access_token(self, refresh_token: str):
        """Generate new access token using refresh token"""
        try:
            payload = jwt.decode(refresh_token, self.SECRET_KEY, algorithms=[self.ALGORITHM])
            email = payload.get("sub")
            if email is None:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid refresh token"
                )
            
            # Get stored tokens from Redis
            token_data = self.redis_client.get(f"user:{email}:tokens")
            if not token_data:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="No tokens found for user"
                )
            
            token_data = json.loads(token_data)
            
            # Verify refresh token matches stored one
            if token_data["refresh_token"] != refresh_token:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Refresh token mismatch"
                )
            
            # Create new access token
            new_access_token = self.create_access_token(
                data={"sub": email},
                expires_delta=timedelta(minutes=self.ACCESS_TOKEN_EXPIRE_MINUTES)
            )
            
            # Update stored access token in Redis
            token_data["access_token"] = new_access_token
            token_data["access_exp"] = (datetime.now() + timedelta(minutes=self.ACCESS_TOKEN_EXPIRE_MINUTES)).timestamp()
            
            # Update Redis with new token data
            self.redis_client.set(
                f"user:{email}:tokens",
                json.dumps(token_data),
                ex=int((datetime.fromtimestamp(token_data["refresh_exp"]) - datetime.now()).total_seconds())
            )
            
            return new_access_token
            
        except jwt.PyJWTError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token"
            )

    def blacklist_token(self, token: str):
        """Add token to blacklist set in Redis"""
        try:
            # Set expiration for blacklisted token (same as token's expiration)
            payload = jwt.decode(token, self.SECRET_KEY, algorithms=[self.ALGORITHM], options={"verify_exp": False})
            exp_time = payload.get("exp")
            if exp_time:
                ttl = exp_time - int(datetime.now().timestamp())
                if ttl > 0:
                    self.redis_client.sadd("blacklisted_tokens", token)
                    self.redis_client.expire("blacklisted_tokens", ttl)
        except Exception as e:
            logger.error(f"Error blacklisting token: {str(e)}")