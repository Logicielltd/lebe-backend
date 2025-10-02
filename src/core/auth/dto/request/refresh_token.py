from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr, Field, validator

class RefreshTokenRequest(BaseModel):
    refresh_token: str
    # Include any user identifiers you need (email or user_id)
    email: Optional[str] = None