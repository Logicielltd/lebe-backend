from enum import Enum
from pydantic import BaseModel, Field
from typing import Optional
from decimal import Decimal
from datetime import datetime

class Network(str, Enum):
    # Mobile Networks
    MTN = "MTN"           # MTN network
    VOD = "VOD"           # Vodafone network
    AIR = "AIR"           # AirtelTigo network

    # Payment Networks
    MAS = "MAS"           # MasterCard
    VIS = "VIS"           # VISA
    BNK = "BNK"           # Bank

    # Bill Payment Providers
    GOT = "GOT"           # GoTV
    DST = "DST"           # DStv
    ECG = "ECG"           # Electricity Company of Ghana
    GHW = "GHW"           # Ghana Water Company
    SFL = "SFL"           # Surfline
    TLS = "TLS"           # Telesol
    STT = "STT"           # StartTimes
    BXO = "BXO"           # Box Office