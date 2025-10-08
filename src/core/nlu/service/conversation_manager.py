from datetime import datetime
from typing import Dict, List, Any, Optional
from dataclasses import dataclass

@dataclass
class ConversationState:
    user_id: str
    current_intent: str = ""
    collected_slots: Dict = None
    waiting_for_pin: bool = False
    pending_action: Dict = None
    conversation_history: List[Dict] = None
    
    def __post_init__(self):
        if self.collected_slots is None:
            self.collected_slots = {}
        if self.conversation_history is None:
            self.conversation_history = []

class ConversationManager:
    def __init__(self):
        self.conversations: Dict[str, ConversationState] = {}
    
    def get_conversation_state(self, user_id: str) -> ConversationState:
        """Get or create conversation state for user"""
        if user_id not in self.conversations:
            self.conversations[user_id] = ConversationState(user_id=user_id)
        return self.conversations[user_id]
    
    def update_conversation_history(self, user_id: str, role: str, content: str):
        """Update conversation history"""
        state = self.get_conversation_state(user_id)
        state.conversation_history.append({"role": role, "content": content})
        
        # Keep only last 20 messages to manage context length
        if len(state.conversation_history) > 20:
            state.conversation_history = state.conversation_history[-20:]
    
    def reset_conversation_state(self, user_id: str):
        """Reset conversation state (after action completion)"""
        if user_id in self.conversations:
            self.conversations[user_id] = ConversationState(user_id=user_id)
    
    def set_pending_action(self, user_id: str, intent: str, slots: Dict):
        """Set pending action waiting for PIN"""
        state = self.get_conversation_state(user_id)
        state.waiting_for_pin = True
        state.pending_action = {
            "intent": intent,
            "slots": slots,
            "timestamp": datetime.now().isoformat()
        }