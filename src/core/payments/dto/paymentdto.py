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
    phoneNumber: Optional[str] = None  # Legacy field for backwards compatibility
    senderPhone: Optional[str] = None  # Customer initiating payment
    receiverPhone: Optional[str] = None  # Recipient of payment
    bankCode: Optional[str] = None
    network: Optional[Network] = None
    amountPaid: Optional[Decimal] = None
    datePaid: Optional[datetime] = None
    updatedOn: Optional[datetime] = None
    # External biller information (for non-telco/ABS bill payments)
    extBillerRefId: Optional[str] = None  # Biller ID for ABS bill payments
    # Sender and receiver information
    senderName: Optional[str] = None  # Name of user initiating transaction
    receiverName: Optional[str] = None  # Verified account holder name
    senderProvider: Optional[str] = None  # Provider based on sender network
    receiverProvider: Optional[str] = None  # Provider based on receiver network