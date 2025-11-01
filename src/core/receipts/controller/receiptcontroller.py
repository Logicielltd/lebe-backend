from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Optional
from datetime import datetime

from core.auth.service.sessiondriver import SessionDriver, TokenData
from fastapi_jwt_auth import AuthJWT
from utilities.dbconfig import SessionLocal
from sqlalchemy.orm import Session

# DTO Models
from core.receipts.dto.request.receiptcreate import ReceiptCreateRequest
from core.receipts.dto.response.receiptresponse import ReceiptResponse

from core.receipts.service.receipt_service import ReceiptService

# Reuse existing dependencies
from core.user.controller.usercontroller import validate_token, get_db

# Controller (Router)
receipt_routes = APIRouter()

@receipt_routes.post("/", response_model=ReceiptResponse)
def create_receipt(
    receipt_data: ReceiptCreateRequest,
    authjwt: AuthJWT = Depends(validate_token),
    db: Session = Depends(get_db)
):
    """Create a receipt image from transaction data"""
    current_user_email = authjwt.get_jwt_subject()
    
    receipt_service = ReceiptService(db)
    
    return receipt_service.create_receipt(
        transaction_id=receipt_data.transaction_id,
        user_id=receipt_data.user_id,
        receipt_data=receipt_data.receipt_data,
        template_type=receipt_data.template_type
    )

@receipt_routes.get("/{receipt_id}", response_model=ReceiptResponse)
def get_receipt(
    receipt_id: str,
    authjwt: AuthJWT = Depends(validate_token),
    db: Session = Depends(get_db)
):
    """Get a specific receipt by ID"""
    receipt_service = ReceiptService(db)
    return receipt_service.get_receipt(receipt_id)

@receipt_routes.get("/transaction/{transaction_id}", response_model=ReceiptResponse)
def get_receipt_by_transaction(
    transaction_id: str,
    authjwt: AuthJWT = Depends(validate_token),
    db: Session = Depends(get_db)
):
    """Get receipt by transaction ID"""
    receipt_service = ReceiptService(db)
    return receipt_service.get_receipt_by_transaction(transaction_id)

@receipt_routes.get("/user/recent", response_model=List[ReceiptResponse])
def get_user_receipts(
    limit: int = Query(10, ge=1, le=50),
    authjwt: AuthJWT = Depends(validate_token),
    db: Session = Depends(get_db)
):
    """Get recent receipts for the current user"""
    current_user_email = authjwt.get_jwt_subject()
    
    # You might need to get user_id from email
    from core.user.model.User import User
    user = db.query(User).filter(User.email == current_user_email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    receipt_service = ReceiptService(db)
    return receipt_service.get_user_receipts(user.id, limit)