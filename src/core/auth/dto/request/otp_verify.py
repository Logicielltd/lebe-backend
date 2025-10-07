from pydantic import BaseModel, Field


class OTPVerifyRequest(BaseModel):
    phone: str = Field(..., min_length=10, max_length=15)
    otp: str = Field(..., min_length=5, max_length=5)