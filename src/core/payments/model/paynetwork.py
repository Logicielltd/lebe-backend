from enum import Enum
from pydantic import BaseModel, Field
from typing import Optional
from decimal import Decimal
from datetime import datetime

class Network(str, Enum):
    MTN = "MTN"           # MTN network
    VOD = "VOD"           # Vodafone network
    AIR = "AIR"           # AirtelTigo network
    MAS = "MAS"           # MasterCard
    VIS = "VIS"           # VISA
    BNK = "BNK"           # Bank