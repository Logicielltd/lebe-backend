from typing import Dict, List, Any, Tuple
from src.core.nlu.config import INTENTS, SYSTEM_PROMPTS
from src.core.nlu.service.llmclient import LLMClient  # Add this import

class IntentDetector:
    def __init__(self):
        self.intents = INTENTS
        self.llm_client = LLMClient()  # Replace direct openai client with LLMClient
    
    def detect_intent_and_slots(self, user_message: str, conversation_history: List[Dict]) -> Tuple[str, Dict, List[str]]:
        """
        Detect user intent and extract slots from message
        Returns: (intent, extracted_slots, missing_slots)
        """
        
        # Prepare conversation context
        context = self._prepare_context(conversation_history)
        
        # Use transactional system prompt for intent detection
        system_prompt = SYSTEM_PROMPTS["transactional"].format(
            context=context, 
            missing_slots="",
            topic="intent detection"
        )
        
        # Create prompt for intent detection
        prompt = f"""
        Analyze the user's message and extract:
        1. The main intent from this list: {list(self.intents.keys())}
        2. Any relevant information (slots) for that intent
        
        User message: "{user_message}"
        
        Available intents and their slots:
        {self._format_intents_for_prompt()}
        
        Respond in this exact format:
        INTENT: [detected_intent]
        SLOTS: [json_object_with_slots]
        MISSING: [comma_separated_missing_slots]
        
        Example:
        INTENT: send_money
        SLOTS: {{"amount": "50", "recipient": "0234567890"}}
        MISSING: network,reason
        """
        
        try:
            # Use LLMClient instead of direct openai call
            response_text = self.llm_client.chat_completion(
                system_prompt=system_prompt,
                user_message=prompt,
                temperature=0.1,
                max_tokens=500
            )
            
            return self._parse_response(response_text)
            
        except Exception as e:
            print(f"Error in intent detection: {e}")
            return "unknown", {}, []
    
    def _prepare_context(self, conversation_history: List[Dict]) -> str:
        """Prepare conversation context for the AI"""
        if not conversation_history:
            return "New conversation"
        
        context = "Recent conversation:\n"
        for msg in conversation_history[-5:]:  # Last 5 messages
            context += f"{msg['role']}: {msg['content']}\n"
        return context
    
    def _format_intents_for_prompt(self) -> str:
        """Format intents for the prompt"""
        formatted = ""
        for intent, details in self.intents.items():
            formatted += f"- {intent}: {details['description']} (slots: {', '.join(details['slots'])})\n"
        return formatted
    
    def _parse_response(self, response_text: str) -> Tuple[str, Dict, List[str]]:
        """Parse the AI response into structured data"""
        intent = "unknown"
        slots = {}
        missing_slots = []
        
        if not response_text:
            return intent, slots, missing_slots
            
        lines = response_text.strip().split('\n')
        for line in lines:
            if line.startswith('INTENT:'):
                intent = line.replace('INTENT:', '').strip()
            elif line.startswith('SLOTS:'):
                import json
                try:
                    slots_str = line.replace('SLOTS:', '').strip()
                    slots = json.loads(slots_str) if slots_str else {}
                except:
                    slots = {}
            elif line.startswith('MISSING:'):
                missing_str = line.replace('MISSING:', '').strip()
                missing_slots = [s.strip() for s in missing_str.split(',')] if missing_str else []
        
        return intent, slots, missing_slots