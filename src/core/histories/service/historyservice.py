from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import desc, func
from core.histories.model.history import History
from core.histories.dto.response.historyresponse import HistoryResponseDTO, HistorySummaryDTO
import uuid
from datetime import datetime, timedelta

class HistoryService:
    def __init__(self, db: Session):
        self.db = db
    
    def create_history(self, 
                     user_id: str,
                     intent: str,
                     transaction_type: str,
                     amount: Optional[float] = None,
                     recipient: Optional[str] = None,
                     phone_number: Optional[str] = None,
                     data_plan: Optional[str] = None,
                     category: Optional[str] = None,
                     status: str = "completed",
                     description: Optional[str] = None,
                     metadata: Optional[Dict[str, Any]] = None) -> HistoryResponseDTO:
        """Create a new transaction history record"""
        
        history = History(
            id=uuid.uuid4(),
            user_id=user_id,
            intent=intent,
            transaction_type=transaction_type,
            amount=amount,
            recipient=recipient,
            phone_number=phone_number,
            data_plan=data_plan,
            category=category,
            status=status,
            description=description,
            transaction_metadata=metadata or {}
        )
        
        self.db.add(history)
        self.db.commit()
        self.db.refresh(history)

        return HistoryResponseDTO.model_validate(history)
    
    def get_user_histories(self, 
                          user_id: str,
                          page: int = 1,
                          page_size: int = 20,
                          intent: Optional[str] = None,
                          transaction_type: Optional[str] = None,
                          start_date: Optional[datetime] = None,
                          end_date: Optional[datetime] = None) -> List[HistoryResponseDTO]:
        """Get paginated transaction histories for a user"""
        
        query = self.db.query(History).filter(History.user_id == user_id)
        
        # Apply filters
        if intent:
            query = query.filter(History.intent == intent)
        if transaction_type:
            query = query.filter(History.transaction_type == transaction_type)
        if start_date:
            query = query.filter(History.created_at >= start_date)
        if end_date:
            query = query.filter(History.created_at <= end_date)
        
        # Pagination
        offset = (page - 1) * page_size
        histories = query.order_by(desc(History.created_at)).offset(offset).limit(page_size).all()
        
        return [HistoryResponseDTO.model_validate(history) for history in histories]
    
    def get_history_by_id(self, history_id: str, user_id: str) -> Optional[HistoryResponseDTO]:
        """Get a specific transaction history by ID"""
        history = self.db.query(History).filter(
            History.id == uuid.UUID(history_id),
            History.user_id == user_id
        ).first()
        
        return HistoryResponseDTO.model_validate(history) if history else None
    
    def get_transaction_summary(self, user_id: str, days: int = 30) -> HistorySummaryDTO:
        """Get transaction summary for a user"""
        
        start_date = datetime.utcnow() - timedelta(days=days)
        
        # Total transactions and amount
        total_query = self.db.query(
            func.count(History.id).label('total_count'),
            func.coalesce(func.sum(History.amount), 0).label('total_amount')
        ).filter(
            History.user_id == user_id,
            History.created_at >= start_date
        ).first()
        
        # Transaction type counts
        type_counts_query = self.db.query(
            History.transaction_type,
            func.count(History.id).label('count')
        ).filter(
            History.user_id == user_id,
            History.created_at >= start_date
        ).group_by(History.transaction_type).all()
        
        # Recent transactions
        recent_transactions = self.db.query(History).filter(
            History.user_id == user_id,
            History.created_at >= start_date
        ).order_by(desc(History.created_at)).limit(5).all()
        
        return HistorySummaryDTO(
            total_transactions=total_query.total_count,
            total_amount=float(total_query.total_amount),
            transaction_types={item.transaction_type: item.count for item in type_counts_query},
            recent_transactions=[HistoryResponseDTO.model_validate(tx) for tx in recent_transactions]
        )
    
    def get_spending_by_category(self, user_id: str, days: int = 30) -> Dict[str, float]:
        """Get spending breakdown by category"""
        
        start_date = datetime.utcnow() - timedelta(days=days)
        
        category_spending = self.db.query(
            History.category,
            func.sum(History.amount).label('total_amount')
        ).filter(
            History.user_id == user_id,
            History.transaction_type == 'debit',
            History.created_at >= start_date,
            History.category.isnot(None)
        ).group_by(History.category).all()
        
        return {item.category: float(item.total_amount) for item in category_spending}