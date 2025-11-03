from typing import List, Optional
from pydantic import BaseModel

from src.core.payments.model.paymentmethod import PaymentMethod
from src.core.payments.model.paymentstatus import PaymentStatus

class PaymentResultResponse(BaseModel):
    paymentId: Optional[int] = None
    status: PaymentStatus
    responseCode: Optional[str] = None
    responseDescription: Optional[str] = None
    transactionId: Optional[str] = None
    paymentMethod: Optional[PaymentMethod] = None