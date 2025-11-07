from pydantic import BaseModel
from typing import Optional, Dict, Any

class NLUResponse(BaseModel):
    user_id: str
    message: str
    response: str
    success: bool
    metadata: Optional[Dict[str, Any]] = None
    
    class Config:
        schema_extra = {
            "example": {
                "user_id": "user123",
                "message": "I want to send money",
                "response": "Sure! How much would you like to send and to which phone number?",
                "success": True,
                "metadata": {"intent": "send_money", "missing_slots": ["amount", "recipient"]}
            }
        }