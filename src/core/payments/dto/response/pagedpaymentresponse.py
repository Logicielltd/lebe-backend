from typing import List
from pydantic import BaseModel

from src.core.payments.dto.response.paymentresponse import PaymentResponse



class PagedPaymentResponse(BaseModel):
    total: int
    page: int
    size: int
    users: List[PaymentResponse]