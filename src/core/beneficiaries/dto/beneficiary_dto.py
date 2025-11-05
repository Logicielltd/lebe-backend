from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class BeneficiaryCreateRequest(BaseModel):
    """Request model for creating/updating a beneficiary."""
    name: str
    customer_number: str
    network: Optional[str] = None  # Auto-detected if not provided
    bank_code: Optional[str] = None

    class Config:
        json_schema_extra = {
            "example": {
                "name": "John Agyeman",
                "customer_number": "0550748724",
                "network": "MTN",
                "bank_code": None
            }
        }


class BeneficiaryResponse(BaseModel):
    """Response model for beneficiary."""
    id: int
    name: str
    customer_number: str
    network: str
    bank_code: Optional[str]
    account_type: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

    @classmethod
    def from_beneficiary(cls, beneficiary):
        """Convert Beneficiary model to response DTO."""
        return cls(
            id=beneficiary.id,
            name=beneficiary.name,
            customer_number=beneficiary.customer_number,
            network=beneficiary.network,
            bank_code=beneficiary.bank_code,
            account_type=beneficiary.account_type.value,
            is_active=beneficiary.is_active,
            created_at=beneficiary.created_at,
            updated_at=beneficiary.updated_at
        )
