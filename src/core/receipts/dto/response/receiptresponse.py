from pydantic import BaseModel
from datetime import datetime

class ReceiptResponse(BaseModel):
    id: str
    transaction_id: str
    user_id: str
    image_url: str
    created_at: datetime
    
    class Config:
        from_attributes = True