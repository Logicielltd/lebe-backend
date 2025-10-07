from pydantic import BaseModel, EmailStr, Field
from typing import Optional


class OTPSendRequest(BaseModel):
    phone: Optional[str] = Field(None, min_length=10, max_length=15)
    email: Optional[EmailStr] = None