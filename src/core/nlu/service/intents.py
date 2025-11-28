from typing import Dict, List, Any, Tuple
from core.nlu.config import INTENTS, SYSTEM_PROMPTS
from core.nlu.service.llmclient import LLMClient  # Add this import

class IntentDetector:
    def __init__(self):
        self.intents = INTENTS
        self.llm_client = LLMClient()  # Replace direct openai client with LLMClient

    def detect_intent_and_slots(self, user_message: str, conversation_history: List[Dict], current_intent: str = None) -> Tuple[str, Dict, List[str]]:
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
            category="intent detection"
        )

        # Enhanced prompt with context awareness and precision
        prompt = self._create_enhanced_prompt(user_message, current_intent)
        
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
    
    def _create_enhanced_prompt(self, user_message: str, current_intent: str = None) -> str:
        """Create enhanced prompt with context awareness and precision"""
        
        intent_guidelines = """
        INTENT DETECTION GUIDELINES:
        1. Be precise - analyze the exact words and phrasing in the user message
        2. If the message continues the current conversation flow, maintain the same intent
        3. Only change intent if the user clearly introduces a new topic or request
        4. For ambiguous messages, prefer the current intent if it makes contextual sense
        5. Consider conversation history when determining if this is a continuation
        
        CRITICAL RULES:
        - If user provides additional information for current intent: KEEP SAME INTENT
        - If user corrects or modifies previous information: KEEP SAME INTENT  
        - If user asks clarifying questions about current task: KEEP SAME INTENT
        - Only switch intent for completely new, unrelated requests
        """
        
        current_intent_context = f"CURRENT_INTENT: {current_intent if current_intent else 'None (new conversation)'}"
        
        return f"""
        {intent_guidelines}
        
        {current_intent_context}
        You are an expert conversational AI that identifies user intents and extracts relevant slot information.
        A slot is a specific piece of information needed to fulfill an intent (e.g., amount, recipient).

        Your goals:
        1. Identify the user's **main intent** from the list below:
        List of defined intents: {list(self.intents.keys())}
        2. Extract slot values relevant to that intent.
        3. If the message is a continuation of an existing intent (current_intent = "{current_intent}"), 
        maintain that same intent **unless** the user clearly starts a new topic.
        4. Accurately identify missing required slots for that intent.
        
        User message to analyze: "{user_message}"
        
        Available intents and their slots:
        {self._format_intents_for_prompt()}
        
        DECISION PROCESS:
        - Is this message clearly about a NEW intent? → Use new intent
        - Is this message continuing/refining the CURRENT intent? → Keep current intent
        - Is this message ambiguous but contextually related? → Prefer current intent
        
        Respond in this EXACT format:
        INTENT: [detected_intent]
        SLOTS: [json_object_with_slots]
        MISSING: [comma_separated_missing_slots]
        
        Examples:
        User starts send_money: "Send 50 cedis to 0234567890"
        INTENT: send_money
        SLOTS: {{"amount": "50", "recipient": "0234567890"}}
        MISSING: network,reason

        User starts bill payment: "Make bill payment of 1 cedi to 95200204493"
        INTENT: pay_bill
        SLOTS: {{"amount": "1", "account_number": "95200204493"}}
        MISSING: bill_type

        User starts bill payment: "Pay my DStv bill, account 1234567890, amount is 50 cedis"
        INTENT: pay_bill
        SLOTS: {{"bill_type": "DStv", "account_number": "1234567890", "amount": "50"}}
        MISSING:

        User starts buy_airtime: "Buy me 5 cedis airtime to 0550748724"
        INTENT: buy_airtime
        SLOTS: {{"amount": "5", "phone_number": "0550748724"}}
        MISSING: network

        User continues current intent: "Actually, make it 100 cedis instead"
        INTENT: send_money
        SLOTS: {{"amount": "100"}}
        MISSING: recipient,network,reason

        User starts new intent: "I want to check my balance"
        INTENT: check_balance
        SLOTS: {{}}
        MISSING:
        Examples end.

        Notes for accuracy:
        - If the user's message clarifies or adds to the **current intent**, do not change it.
        - Only switch intent if the message explicitly refers to a different goal or action.
        - Always ensure `SLOTS` is valid JSON.
        """
    
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