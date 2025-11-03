# profile_request.py
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from src.core.profile.model.Profile import ProfileType

class ProfileUpdateRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    category: Optional[ProfileType] = None
    website: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None
    postal_code: Optional[str] = None
    tax_id: Optional[str] = None
    registration_number: Optional[str] = None
    established_date: Optional[datetime] = None