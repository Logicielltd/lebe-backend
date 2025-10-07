from pydantic import BaseModel
from typing import Optional, Dict, Any


class OTPSendResponse(BaseModel):
    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None