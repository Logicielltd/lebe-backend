# core/rag/user_data_manager.py
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import json
from collections import defaultdict
from sqlalchemy.orm import Session
from core.payments.model.payment import Payment
from core.payments.model.paymentstatus import PaymentStatus
from utilities.dbconfig import SessionLocal
from core.nlu.service.datapipe.time_period_parser import TimePeriodParser, get_lookback_days
import logging

logger = logging.getLogger(__name__)

class UserRAGManager:
    """Manages user data for RAG augmentation using transaction history"""
    
    def __init__(self, max_context_tokens: int = 4000):
        self.max_context_tokens = max_context_tokens
        self.estimated_token_ratio = 4  # chars per token estimate
    
    def get_extracted_user_context(
        self, 
        user_id: str, 
        intent: str,
        current_slots: Dict,
        full_user_data: Dict
    ) -> Dict[str, Any]:
        """
        Get optimized user context based on intent and transaction history
        """
        # Extract core user bio (always included)
        core_bio = self._extract_core_bio(full_user_data)
        
        # Get transaction history from database
        transaction_data = self.get_transaction_history(user_id, intent, current_slots)
        
        rag_context = {
            "User Transaction History": transaction_data
        }
        
        return rag_context
    
    def _extract_core_bio(self, user_data: Dict) -> Dict:
        """Extract essential user bio information"""
        return {
            "user_id": user_data.get("user_id"),
            "username": user_data.get("username"),
            "email": user_data.get("email"),
            "first_name": user_data.get("first_name"),
            "last_name": user_data.get("last_name"),
            "is_active": user_data.get("is_active"),
            "member_since": user_data.get("created_at"),
            "location": "Ghana"  # Default location
        }
    
    def get_transaction_history(self, user_id: str, intent: str, slots: Dict) -> List[Dict]:
        """Fetch transaction history from database"""
        try:
            db = SessionLocal()
            
            #Log user id and intent
            print(f"[USER_RAG] Fetching transactions for user_id: {user_id}, intent: {intent}")
            
            # Base query: use Payment table (only SUCCESS) and filter by sender phone
            query = db.query(Payment).filter(
                Payment.sender_phone == user_id,
            )

            # Parse time period intelligently - supports natural language, codes, and numeric formats
            time_period = slots.get("time_period")
            date_range = TimePeriodParser.parse(time_period)
            
            if date_range:
                start_date = date_range.start_date
                logger.info(
                    f"[USER_RAG] Parsed time_period '{time_period}' -> lookback {date_range.days_back} days "
                    f"(code: {date_range.period_code}, confidence: {date_range.confidence})"
                )
            else:
                # Fallback: default to 30 days
                start_date = datetime.utcnow() - timedelta(days=30)
                logger.warning(f"[USER_RAG] Failed to parse time_period '{time_period}', defaulting to 30 days")
            
            query = query.filter(Payment.date_paid >= start_date)

            # Order by most recent and limit
            transactions = query.order_by(Payment.date_paid.desc()).limit(100).all()

            # Convert to dictionary format (map Payment fields)
            transaction_list = []
            for tx in transactions:
                transaction_list.append({
                    "id": str(tx.id),
                    "bill_id": tx.bill_id,
                    "response_id": tx.response_id,
                    "amount_paid": float(tx.amount_paid) if tx.amount_paid else 0.0,
                    "payment_method": tx.payment_method,
                    "status": tx.status.value if hasattr(tx.status, 'value') else str(tx.status),
                    "transaction_id": tx.transaction_id,
                    "service_name": tx.service_name,
                    "intent": tx.intent,
                    "sender_phone": tx.sender_phone,
                    "receiver_phone": tx.receiver_phone,
                    "network": tx.network,
                    "reference": tx.reference or None,
                    "receiver_name": " ".join(filter(None, [tx.beneficiary_name, tx.receiver_name])),          
                    "date_paid": tx.date_paid.isoformat() if tx.date_paid else None,
                })
            
            return transaction_list
            
        except Exception as e:
            logger.error(f"Error fetching transaction history: {e}")
            return []
        finally:
            db.close()
    
    def _get_lookback_period(self, time_period: str) -> int:
        """
        Get number of days to look back based on time period.
        Now uses smart TimePeriodParser for better natural language support.
        
        Supports:
        - Natural language: "last month", "3 weeks ago", "30 days", etc.
        - Period codes: "TODAY", "MONTH_1", "YEAR_1", etc.
        - Numeric: "30", "7 days", "3 months", etc.
        """
        return get_lookback_days(time_period)

    
