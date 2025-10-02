from enum import Enum
from pydantic import BaseModel
from typing import Optional


class PaymentStatus(str, Enum):
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    PENDING = "PENDING"