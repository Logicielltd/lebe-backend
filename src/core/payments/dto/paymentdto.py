from enum import Enum
from pydantic import BaseModel, Field
from typing import Optional
from decimal import Decimal
from datetime import datetime

from core.payments.model.paymentmethod import PaymentMethod
from core.payments.model.paymentstatus import PaymentStatus
from core.payments.model.paynetwork import Network

class PaymentDto(BaseModel):
    id: Optional[int] = None
    billId: Optional[int] = None
    responseId: Optional[int] = None
    paymentMethod: Optional[PaymentMethod] = None
    status: Optional[PaymentStatus] = None
    transactionId: Optional[str] = None
    serviceName: Optional[str] = None
    customerEmail: Optional[str] = None
    customerName: Optional[str] = None
    phoneNumber: Optional[str] = None
    bankCode: Optional[str] = None
    network: Optional[Network] = None
    datePaid: Optional[datetime] = None
    updatedOn: Optional[datetime] = None