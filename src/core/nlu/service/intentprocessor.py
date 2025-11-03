# core/nlu/service/intent_processor.py
from typing import Dict, List, Any, Optional
from core.nlu.service.llmclient import LLMClient
from core.nlu.config import SYSTEM_PROMPTS, RESPONSE_TEMPLATES, INTENT_CATEGORIES
from core.nlu.service.user_rag import UserRAGManager

class IntentProcessor:
    """Processes conversational and financial tips intents using LLM with User RAG"""
    
    def __init__(self):
        self.llm_client = LLMClient()
        self.rag_manager = UserRAGManager()  # Initialize RAG manager
    
    def process_conversational_intent(
        self, 
        intent: str, 
        user_message: str, 
        conversation_history: List[Dict],
        slots: Dict[str, Any],
        user_data: Optional[Dict] = None  # Add user_data parameter
    ) -> str:
        """
        Process conversational intents with user context augmentation
        """
        # Prepare enhanced system prompt with user context
        system_prompt = self._build_enhanced_system_prompt(
            base_prompt=SYSTEM_PROMPTS["conversational"],
            conversation_history=conversation_history,
            user_data=user_data,
            intent=intent,
            slots=slots
        )
        
        response = self.llm_client.chat_completion(
            system_prompt=system_prompt,
            user_message=user_message,
            conversation_history=conversation_history,
            temperature=0.7
        )
        
        return self._format_conversational_response(intent, response, slots)
    
    def process_financial_tips_intent(
        self,
        intent: str,
        user_message: str,
        conversation_history: List[Dict],
        slots: Dict[str, Any],
        user_data: Optional[Dict] = None  # Add user_data parameter
    ) -> str:
        """
        Process financial tips with personalized user context
        """
        # Prepare enhanced system prompt with user context
        system_prompt = self._build_enhanced_system_prompt(
            base_prompt=SYSTEM_PROMPTS["financial_tips"],
            conversation_history=conversation_history,
            user_data=user_data,
            intent=intent,
            slots=slots
        )
        
        response = self.llm_client.chat_completion(
            system_prompt=system_prompt,
            user_message=user_message,
            conversation_history=conversation_history,
            temperature=0.4
        )
        
        return self._format_financial_tips_response(intent, response, slots)

    def process_expense_report_intent(
        self,
        intent: str,
        user_message: str,
        conversation_history: List[Dict],
        slots: Dict[str, Any],
        user_data: Optional[Dict] = None  # Add user_data parameter
    ) -> str:
        """
        Process expense report with user spending context
        """
        system_prompt = self._build_enhanced_system_prompt(
            base_prompt=SYSTEM_PROMPTS["expense_report"],
            conversation_history=conversation_history,
            user_data=user_data,
            intent=intent,
            slots=slots
        )
        
        response = self.llm_client.chat_completion(
            system_prompt=system_prompt,
            user_message=user_message,
            conversation_history=conversation_history,
            temperature=0.3
        )
        
        return response

    def _build_enhanced_system_prompt(
        self,
        base_prompt: str,
        conversation_history: List[Dict],
        user_data: Optional[Dict],
        intent: str,
        slots: Dict
    ) -> str:
        """
        Build enhanced system prompt with user context RAG
        """
        # Prepare conversation context
        conversation_context = self._prepare_conversation_context(conversation_history)
        
        # Add user context if available
        user_context_section = ""
        if user_data:
            user_context = self.rag_manager.get_optimized_user_context(
                user_id=user_data.get("id", "unknown"),
                intent=intent,
                current_slots=slots,
                full_user_data=user_data
            )
            user_context_section = self.rag_manager.format_context_for_prompt(user_context)
        
        # Build the enhanced prompt
        enhanced_prompt = base_prompt.format(
            context=conversation_context,
            missing_slots="",
            topic=slots.get('topic', 'general')
        )
        
        # Append user context if available
        if user_context_section:
            enhanced_prompt += f"\n\n{user_context_section}\n\nIMPORTANT: Use the above user context to personalize your response. Consider their financial situation, goals, and history when providing advice."
        
        return enhanced_prompt

    def _format_conversational_response(self, intent: str, response: str, slots: Dict) -> str:
        """Format conversational responses using templates"""
        template_data = RESPONSE_TEMPLATES["conversational"]
        
        if intent in template_data:
            template = template_data[intent]
            return template.format(response=response, **slots)
        
        return response

    def _format_financial_tips_response(self, intent: str, response: str, slots: Dict) -> str:
        """Format financial tips responses using templates"""
        template_data = RESPONSE_TEMPLATES["financial_tips"]
        
        if intent in template_data:
            template = template_data[intent]
            return template.format(response=response, **slots)
        
        return response

    def _prepare_conversation_context(self, conversation_history: List[Dict]) -> str:
        """Prepare conversation context from history"""
        if not conversation_history:
            return "New conversation"
        
        context = "Recent conversation history:\n"
        for msg in conversation_history[-6:]:
            role = "User" if msg["role"] == "user" else "Assistant"
            context += f"{role}: {msg['content']}\n"
        
        return context