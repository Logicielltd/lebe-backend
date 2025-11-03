# profile_response.py
from pydantic import BaseModel
from datetime import datetime
from typing import Optional
from core.profile.model.Profile import ProfileType

class ProfileResponse(BaseModel):
    id: str
    user_id: str
    name: str
    description: Optional[str] = None
    category: ProfileType
    website: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None
    postal_code: Optional[str] = None
    tax_id: Optional[str] = None
    registration_number: Optional[str] = None
    established_date: Optional[datetime] = None
    created_at: datetime
    updated_at: Optional[datetime] = None