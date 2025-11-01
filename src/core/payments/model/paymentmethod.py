from enum import Enum
from pydantic import BaseModel
from typing import Optional

class PaymentMethod(str, Enum):
    CARD = "CARD"
    MOBILE_MONEY = "MOBILE_MONEY"
    BANK_TRANSFER = "BANK_TRANSFER"
    CASH = "CASH"