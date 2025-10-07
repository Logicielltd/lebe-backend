from pydantic import BaseModel, EmailStr, Field
from typing import Optional


class OTPVerifyRequest(BaseModel):
    phone: Optional[str] = Field(None, min_length=10, max_length=15)
    email: Optional[EmailStr] = None
    otp: str = Field(..., min_length=5, max_length=5)