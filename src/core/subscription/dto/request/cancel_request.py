from pydantic import BaseModel, Field
from typing import Optional


class CancelRequest(BaseModel):
    phone: str = Field(..., description="User's phone number")
    reason: Optional[str] = Field(None, max_length=500, description="Reason for cancellation")