import secrets
import string
from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from typing import List, Optional
from datetime import datetime

from core.receipts.model.Receipt import Receipt
from core.receipts.dto.response.receiptresponse import ReceiptResponse
from core.receipts.service.image_gen import ReceiptGenerator

class ReceiptService:
    def __init__(self, db: Session):
        self.db = db
        self.receipt_generator = ReceiptGenerator()
    
    def create_receipt(
        self,
        user_id: str,
        amount: str,
        transaction_id: str,
        sender_name: str,
        sender_account: str,
        sender_provider: str,
        status: str,
        receiver_name: str,
        receiver_account: str,
        receiver_provider: str,
        timestamp: datetime,
        # Optional loan fields
        interest_rate: Optional[str] = None,
        loan_period: Optional[str] = None,
        expected_pay_date: Optional[str] = None,
        penalty_rate: Optional[str] = None
    ) -> str:
        """Create a receipt image from transaction data and return image URL only"""
        
        # Prepare receipt data with all fields
        receipt_data = {
            'amount': amount,
            'transaction_id': transaction_id,
            'sender_name': sender_name,
            'sender_account': sender_account,
            'sender_provider': sender_provider,
            'status': status,
            'receiver_name': receiver_name,
            'receiver_account': receiver_account,
            'receiver_provider': receiver_provider,
            'timestamp': timestamp,
            # Include loan fields if provided
            'interest_rate': interest_rate,
            'loan_period': loan_period,
            'expected_pay_date': expected_pay_date,
            'penalty_rate': penalty_rate
        }
        
        # Generate receipt image URL
        image_url = self.receipt_generator.generate_receipt_image(receipt_data)
        
        # Create receipt record
        receipt = Receipt(
            id=self._generate_receipt_id(),
            transaction_id=transaction_id,
            user_id=user_id,
            image_url=image_url
        )
        
        self.db.add(receipt)
        self.db.commit()
        self.db.refresh(receipt)
        
        # Return only the image URL as requested
        return image_url
    
    def get_receipt_image_url(self, receipt_id: str) -> str:
        """Get receipt image URL by receipt ID"""
        receipt = self.db.query(Receipt).filter(Receipt.id == receipt_id).first()
        if not receipt:
            raise HTTPException(status_code=404, detail="Receipt not found")
        
        return receipt.image_url
    
    def get_receipt_image_url_by_transaction(self, transaction_id: str) -> str:
        """Get receipt image URL by transaction ID"""
        receipt = self.db.query(Receipt).filter(Receipt.transaction_id == transaction_id).first()
        if not receipt:
            raise HTTPException(status_code=404, detail="Receipt not found for this transaction")
        
        return receipt.image_url
    
    def get_user_receipts(self, user_id: str, limit: int = 10) -> List[ReceiptResponse]:
        """Get recent receipts for a user"""
        receipts = self.db.query(Receipt)\
            .filter(Receipt.user_id == user_id)\
            .order_by(Receipt.created_at.desc())\
            .limit(limit)\
            .all()
        
        return [ReceiptResponse.from_orm(receipt) for receipt in receipts]
    
    def _generate_receipt_id(self) -> str:
        """Generate unique receipt ID"""
        alphabet = string.ascii_letters + string.digits
        return "RCP" + "".join(secrets.choice(alphabet) for i in range(12))