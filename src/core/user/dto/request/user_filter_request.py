from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel


class UserFilterRequest(BaseModel):
    roles: Optional[List[str]] = None
    location_ids: Optional[List[str]] = None
    created_after: Optional[datetime] = None
    created_before: Optional[datetime] = None
    is_active: Optional[bool] = None