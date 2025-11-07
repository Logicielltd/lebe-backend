from datetime import datetime
from pydantic import BaseModel


class UserResponse(BaseModel):
    id: str
    username: str
    email: str
    phone: str
    hashed_pin: str
    first_name: str
    last_name: str
    is_active: bool
    created_at: datetime