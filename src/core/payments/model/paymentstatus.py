from enum import Enum
from pydantic import BaseModel
from typing import Optional


class PaymentStatus(str, Enum):
    # Initial state
    PENDING = "PENDING"

    # CTM (Customer to Merchant) - Money coming in
    CTM_PROCESSING = "CTM_PROCESSING"
    CTM_SUCCESS = "CTM_SUCCESS"
    CTM_FAILED = "CTM_FAILED"

    # MTC (Merchant to Customer) - Money going out to receiver
    MTC_PROCESSING = "MTC_PROCESSING"
    MTC_SUCCESS = "MTC_SUCCESS"
    MTC_FAILED = "MTC_FAILED"

    # ATP (Airtime Top-Up) - Airtime going to receiver after CTM succeeds
    ATP_PROCESSING = "ATP_PROCESSING"
    ATP_SUCCESS = "ATP_SUCCESS"
    ATP_FAILED = "ATP_FAILED"

    # BLP (Bill Payment) - Bill payment after CTM succeeds
    BLP_PROCESSING = "BLP_PROCESSING"
    BLP_SUCCESS = "BLP_SUCCESS"
    BLP_FAILED = "BLP_FAILED"

    # Reversal (when MTC, ATP, or BLP fails, refund money back to sender)
    REVERSAL_PROCESSING = "REVERSAL_PROCESSING"
    REVERSAL_SUCCESS = "REVERSAL_SUCCESS"
    REVERSAL_FAILED = "REVERSAL_FAILED"

    # Final states
    SUCCESS = "SUCCESS"  # Both CTM and MTC succeeded
    FAILED = "FAILED"    # Either CTM or MTC failed