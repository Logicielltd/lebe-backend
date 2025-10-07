from pydantic import BaseModel


class OTPVerifyResponse(BaseModel):
    success: bool
    message: str