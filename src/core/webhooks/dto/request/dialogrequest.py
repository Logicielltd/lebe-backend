from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel

class DialogRequest(BaseModel):
    phone: str
    message: str
    data: Optional[dict] = None
