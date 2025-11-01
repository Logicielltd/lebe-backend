from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel

class DialogResponse(BaseModel):
    response: str
    timestamp: datetime
