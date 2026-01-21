# core/rag/user_data_manager.py
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import json
from collections import defaultdict
from sqlalchemy.orm import Session
from core.histories.model.history import History
from utilities.dbconfig import SessionLocal

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
        transaction_data = self._get_transaction_history(user_id, intent, current_slots)
        
        rag_context = {
            "user_bio": core_bio,
            "transactions": transaction_data
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
    
    def _get_transaction_history(self, user_id: str, intent: str, slots: Dict) -> List[Dict]:
        """Fetch transaction history from database"""
        try:
            db = SessionLocal()
            
            #Log user id and intent
            print(f"[USER_RAG] Fetching transactions for user_id: {user_id}, intent: {intent}")
            
            # Base query for user's transactions
            query = db.query(History).filter(History.user_id == user_id)
            
            # Apply time filters based on intent
            days_to_look_back = self._get_lookback_period(intent)
            start_date = datetime.utcnow() - timedelta(days=days_to_look_back)
            query = query.filter(History.created_at >= start_date)
         
            # Order by most recent and limit
            transactions = query.order_by(History.created_at.desc()).limit(100).all()
            
            # Convert to dictionary format
            transaction_list = []
            for tx in transactions:
                transaction_list.append({
                    "id": str(tx.id),
                    "intent": tx.intent,
                    "transaction_type": tx.transaction_type,
                    "amount": float(tx.amount) if tx.amount else 0.0,
                    "recipient": tx.recipient,
                    "phone_number": tx.phone_number,
                    "category": tx.category,
                    "status": tx.status,
                    "description": tx.description,
                    "created_at": tx.created_at.isoformat() if tx.created_at else None,
                    "metadata": tx.transaction_metadata or {}
                })
            
            return transaction_list
            
        except Exception as e:
            print(f"Error fetching transaction history: {e}")
            return []
        finally:
            db.close()
    
    def _get_lookback_period(self, intent: str) -> int:
        """Determine how far back to look in transaction history based on intent"""
        lookback_map = {
            "budgeting_advice": 90,  # 3 months for budgeting patterns
            "savings_tips": 180,     # 6 months for savings trends
            "investment_advice": 365, # 1 year for investment history
            "debt_management": 180,   # 6 months for debt patterns
            "send_money": 60,         # 2 months for transfer patterns
            "buy_airtime": 30,        # 1 month for airtime usage
            "pay_bill": 90,           # 3 months for bill payments
            "financial_tips": 60,     # 2 months for general tips
            "expense_report": 30,     # 1 month for current expenses
            "default": 30             # 1 month default
        }
        return lookback_map.get(intent, lookback_map["default"])
    