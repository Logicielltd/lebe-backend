from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr


class UserResponse(BaseModel):
    id: int
    email: EmailStr
    first_name: str
    last_name: str
    phone: Optional[str]
    profile_picture: Optional[str]
    bio: Optional[str]
    created_at: datetime
    status: str
    
    class Config:
        from_attributes = True  # For ORM compatibility