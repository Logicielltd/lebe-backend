from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr, Field, validator

class UserCreateRequest(BaseModel):
    email: EmailStr
    pin: str = Field(..., min_length=1, max_length=5)
    first_name: str = Field(..., min_length=1, max_length=50)
    last_name: str = Field(..., min_length=1, max_length=50)
    username: str = Field(..., min_length=1, max_length=50)
    phone: Optional[str] = Field(None, min_length=10, max_length=15)