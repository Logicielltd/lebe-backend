from typing import List
from pydantic import BaseModel

from core.user.dto.response.user_response import UserResponse


class PagedUserResponse(BaseModel):
    total: int
    page: int
    size: int
    users: List[UserResponse]