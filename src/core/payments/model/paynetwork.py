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

    # Telco Billers (telecommunications services)
    GOT = "GOT"           # GoTV
    DST = "DST"           # DStv
    MPP = "MPP"           # MTN Prepaid Data
    VPP = "VPP"           # Vodafone Prepaid Data
    STT = "STT"           # Startimes
    VBB = "VBB"           # Vodafone Broadband (ADSL)

    # External Biller System (non-telco bills requiring ext_biller_ref_id)
    ABS = "ABS"           # Abstract Biller System (ECG, schools, institutions, etc.)