from pydantic import BaseModel
from datetime import datetime
from typing import Dict, Any, Optional, List


class PayflowCreateRequest(BaseModel):
    """Request model to save a payflow after successful transaction"""
    name: str  # User-friendly name (e.g., "Mom Payment")
    description: Optional[str] = None  # Optional description
    intent_name: str  # Which intent this payflow is for (send_money, buy_airtime, pay_bill, etc.)
    slot_values: Dict[str, Any]  # Raw slot values from the intent
    payment_method: Optional[str] = None
    recipient_phone: Optional[str] = None
    recipient_name: Optional[str] = None
    account_number: Optional[str] = None
    bill_provider: Optional[str] = None
    last_amount: Optional[str] = None
    requires_confirmation: bool = True  # Whether user confirmation is needed before using payflow


class PayflowUpdateRequest(BaseModel):
    """Request model to update an existing payflow"""
    name: Optional[str] = None
    description: Optional[str] = None
    recipient_phone: Optional[str] = None
    recipient_name: Optional[str] = None
    last_amount: Optional[str] = None
    requires_confirmation: Optional[bool] = None
    is_active: Optional[bool] = None


class PayflowExecuteRequest(BaseModel):
    """Request model to execute a saved payflow"""
    payflow_id: int  # ID of the payflow to execute
    amount: Optional[str] = None  # Optional override amount
    skip_confirmation: bool = False  # Skip confirmation if payflow allows it


class PayflowResponse(BaseModel):
    """Response model for payflow data"""
    id: int
    user_id: str
    name: str
    description: Optional[str]
    intent_name: str
    slot_values: Dict[str, Any]
    payment_method: Optional[str]
    recipient_phone: Optional[str]
    recipient_name: Optional[str]
    account_number: Optional[str]
    bill_provider: Optional[str]
    last_amount: Optional[str]
    requires_confirmation: bool
    is_active: bool
    last_used_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

    @staticmethod
    def from_payflow(payflow):
        """Convert Payflow model to response DTO"""
        return PayflowResponse(
            id=payflow.id,
            user_id=payflow.user_id,
            name=payflow.name,
            description=payflow.description,
            intent_name=payflow.intent_name,
            slot_values=payflow.slot_values,
            payment_method=payflow.payment_method,
            recipient_phone=payflow.recipient_phone,
            recipient_name=payflow.recipient_name,
            account_number=payflow.account_number,
            bill_provider=payflow.bill_provider,
            last_amount=payflow.last_amount,
            requires_confirmation=payflow.requires_confirmation,
            is_active=payflow.is_active,
            last_used_at=payflow.last_used_at,
            created_at=payflow.created_at,
            updated_at=payflow.updated_at
        )


class PayflowListResponse(BaseModel):
    """Response model for listing payflows"""
    total: int
    payflows: List[PayflowResponse]
