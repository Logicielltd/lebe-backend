from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel

class DialogRequest(BaseModel):
    user_id: int
    data: str
