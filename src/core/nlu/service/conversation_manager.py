from datetime import datetime, date, timedelta
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
import json
from sqlalchemy import Column, String, Text, DateTime, JSON, Integer, Date
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from utilities.dbconfig import SessionLocal

from core.nlu.model.Conversation import DailyConversation


@dataclass
class ConversationState:
    user_id: str
    current_intent: str = ""
    collected_slots: Dict = None
    waiting_for_pin: bool = False
    pending_action: Dict = None
    conversation_history: List[Dict] = None
    conversation_date: date = None
    waiting_for_payment_confirmation: bool = False
    pending_payment_dto: Dict = None

    def __post_init__(self):
        if self.collected_slots is None:
            self.collected_slots = {}
        if self.conversation_history is None:
            self.conversation_history = []
        if self.conversation_date is None:
            self.conversation_date = date.today()
        if self.pending_payment_dto is None:
            self.pending_payment_dto = {}
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization"""
        return {
            'user_id': self.user_id,
            'current_intent': self.current_intent,
            'collected_slots': self.collected_slots,
            'waiting_for_pin': self.waiting_for_pin,
            'pending_action': self.pending_action,
            'conversation_history': self.conversation_history,
            'conversation_date': self.conversation_date.isoformat(),
            'waiting_for_payment_confirmation': self.waiting_for_payment_confirmation,
            'pending_payment_dto': self.pending_payment_dto
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'ConversationState':
        """Create ConversationState from dictionary"""
        if 'conversation_date' in data and isinstance(data['conversation_date'], str):
            data['conversation_date'] = date.fromisoformat(data['conversation_date'])
        return cls(**data)

class ConversationManager:
    def __init__(self):
        self.db = SessionLocal()
        self.memory_cache: Dict[str, ConversationState] = {}  # In-memory cache for performance
    
    def _get_today_key(self, user_id: str) -> str:
        """Generate cache key for user's today's conversation"""
        return f"{user_id}_{date.today().isoformat()}"
    
    def get_conversation_state(self, user_id: str) -> ConversationState:
        """Get or create conversation state for user for today"""
        today_key = self._get_today_key(user_id)
        
        # Check memory cache first
        if today_key in self.memory_cache:
            return self.memory_cache[today_key]
        
        # Try to load from database
        today = date.today()
        db_conversation = self.db.query(DailyConversation).filter(
            DailyConversation.user_id == user_id,
            DailyConversation.conversation_date == today
        ).first()
        
        if db_conversation:
            # Load from database
            state = ConversationState.from_dict(db_conversation.conversation_state)
        else:
            # Create new conversation state for today
            state = ConversationState(user_id=user_id, conversation_date=today)
        
        # Cache in memory
        self.memory_cache[today_key] = state
        return state
    
    def update_conversation_history(self, user_id: str, role: str, content: str):
        """Update conversation history and persist to database"""
        state = self.get_conversation_state(user_id)
        state.conversation_history.append({
            "role": role, 
            "content": content,
            "timestamp": datetime.utcnow().isoformat()
        })
        
        # Keep only last 20 messages to manage context length
        if len(state.conversation_history) > 20:
            state.conversation_history = state.conversation_history[-20:]
        
        # Persist to database
        self._save_conversation_state(state)
    
    def _save_conversation_state(self, state: ConversationState):
        """Save conversation state to database"""
        today = date.today()
        
        # Check if record exists for today
        db_conversation = self.db.query(DailyConversation).filter(
            DailyConversation.user_id == state.user_id,
            DailyConversation.conversation_date == today
        ).first()
        
        if db_conversation:
            # Update existing record
            db_conversation.conversation_state = state.to_dict()
            db_conversation.updated_at = datetime.utcnow()
        else:
            # Create new record
            db_conversation = DailyConversation(
                user_id=state.user_id,
                conversation_date=today,
                conversation_state=state.to_dict()
            )
            self.db.add(db_conversation)
        
        try:
            self.db.commit()
        except Exception as e:
            self.db.rollback()
            raise e
        
        # Update cache
        today_key = self._get_today_key(state.user_id)
        self.memory_cache[today_key] = state
    
    def reset_conversation_state(self, user_id: str):
        """Reset conversation state for today (after action completion)"""
        today_key = self._get_today_key(user_id)
        
        # Clear from memory cache
        if today_key in self.memory_cache:
            del self.memory_cache[today_key]
        
        # Delete from database for today
        today = date.today()
        self.db.query(DailyConversation).filter(
            DailyConversation.user_id == user_id,
            DailyConversation.conversation_date == today
        ).delete()
        
        try:
            self.db.commit()
        except Exception as e:
            self.db.rollback()
            raise e
        
    # Method to clear collected slots after action execution
    def clear_collected_slots(self, user_id: str):
        """Clear collected slots after action execution"""
        state = self.get_conversation_state(user_id)
        state.collected_slots = {}
        
        # Persist changes
        self._save_conversation_state(state)

    def set_pending_action(self, user_id: str, intent: str, slots: Dict):
        """Set pending action waiting for PIN and persist to database"""
        state = self.get_conversation_state(user_id)
        state.waiting_for_pin = True
        state.pending_action = {
            "intent": intent,
            "slots": slots,
            "timestamp": datetime.now().isoformat()
        }
        
        # Persist changes
        self._save_conversation_state(state)
    
    def get_previous_conversations(self, user_id: str, days_back: int = 7) -> List[ConversationState]:
        """Get conversation states from previous days (useful for analytics or context)"""
        start_date = date.today() - timedelta(days=days_back)
        
        previous_conversations = self.db.query(DailyConversation).filter(
            DailyConversation.user_id == user_id,
            DailyConversation.conversation_date >= start_date,
            DailyConversation.conversation_date < date.today()  # Exclude today
        ).order_by(DailyConversation.conversation_date.desc()).all()
        
        return [ConversationState.from_dict(conv.conversation_state) for conv in previous_conversations]
    
    def cleanup_old_conversations(self, days_to_keep: int = 30):
        """Clean up conversations older than specified days (for maintenance)"""
        cutoff_date = date.today() - timedelta(days=days_to_keep)
        
        self.db.query(DailyConversation).filter(
            DailyConversation.conversation_date < cutoff_date
        ).delete()
        
        try:
            self.db.commit()
        except Exception as e:
            self.db.rollback()
            raise e

