from enum import Enum
from pydantic import BaseModel, Field
from typing import Optional
from decimal import Decimal
from datetime import datetime

class Network(str, Enum):
    MTN = "MTN"
    VODAFONE = "VODAFONE"
    AIRTELTIGO = "AIRTELTIGO"
    OTHER = "OTHER"