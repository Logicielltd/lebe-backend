# core/nlu/service/intent_processor.py
from typing import Dict, List, Any, Optional
from core.beneficiaries.service.beneficiary_service import BeneficiaryService
from core.nlu.service.llmclient import LLMClient
from core.nlu.config import SYSTEM_PROMPTS, RESPONSE_TEMPLATES, INTENT_CATEGORIES
from core.nlu.service.user_rag import UserRAGManager
from core.user.controller.usercontroller import get_db
from core.beneficiaries.service.beneficiary_service import BeneficiaryService
from core.histories.service.historyservice import HistoryService
from utilities.dbconfig import SessionLocal
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

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
        user_data: Optional[Dict] = None
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
        
        return self._clean_markdown_formatting(response)
    
    def process_beneficiaries_intent(
    self,
    intent: str,
    user_message: str,
    conversation_history: List[Dict],
    slots: Dict[str, Any],
    user_data: Optional[Dict] = None
    ) -> str:
        """
        Process beneficiaries management using BeneficiaryService
        """

        db = next(get_db())

        beneficiary_service = BeneficiaryService(db)
        
        # For beneficiary DB operations we need the internal `users.id` (FK target).
        user_id = (user_data or {}).get("db_user_id") or (user_data or {}).get("user_id") or "unknown"
        
        if intent == "add_beneficiary":
            return self._handle_add_beneficiary(beneficiary_service, user_id, slots)
        elif intent == "view_beneficiaries":
            return self._handle_view_beneficiaries(beneficiary_service, user_id)
        elif intent == "delete_beneficiary":
            return self._handle_delete_beneficiary(beneficiary_service, user_id, slots)
        elif intent == "update_beneficiary":
            return self._handle_update_beneficiary(beneficiary_service, user_id, slots)
        else:
            return "Beneficiary intent not supported"

    def _handle_add_beneficiary(self, beneficiary_service: BeneficiaryService, user_id: str, slots: Dict) -> str:
        """Handle adding a new beneficiary"""
        name = slots.get("beneficiary_name")
        customer_number = slots.get("customer_number")
        network = slots.get("network")
        bank_code = slots.get("bank_code")

        # print user data
        print(f"[METHOD_HANDLE_ADD_BENEFICIARY] User Data for {user_id}")
        
        if not name or not customer_number:
            return "Please provide both beneficiary name and customer number to save a new beneficiary."
        
        success, beneficiary, message = beneficiary_service.add_beneficiary(
            user_id=user_id,
            name=name,
            customer_number=customer_number,
            network=network,
            bank_code=bank_code
        )
        
        return message

    def _handle_view_beneficiaries(self, beneficiary_service: BeneficiaryService, user_id: str) -> str:
        """Handle viewing all beneficiaries"""
        beneficiaries = beneficiary_service.get_beneficiaries(user_id)
        return beneficiary_service.format_beneficiary_list(beneficiaries)

    def _handle_delete_beneficiary(self, beneficiary_service: BeneficiaryService, user_id: str, slots: Dict) -> str:
        """Handle deleting a beneficiary"""
        beneficiary_name = slots.get("beneficiary_name")
        
        if not beneficiary_name:
            return "Please specify which beneficiary you want to remove."
        
        beneficiaries = beneficiary_service.get_beneficiaries(user_id)
        
        # Find beneficiary by name
        target_beneficiary = None
        for beneficiary in beneficiaries:
            if beneficiary.name.lower() == beneficiary_name.lower():
                target_beneficiary = beneficiary
                break
        
        if not target_beneficiary:
            return f"Beneficiary '{beneficiary_name}' not found in your saved beneficiaries."
        
        success, message = beneficiary_service.delete_beneficiary(target_beneficiary.id, user_id)
        return message

    def _handle_update_beneficiary(self, beneficiary_service: BeneficiaryService, user_id: str, slots: Dict) -> str:
        """Handle updating a beneficiary"""
        beneficiary_name = slots.get("beneficiary_name")
        new_name = slots.get("new_beneficiary_name")
        customer_number = slots.get("customer_number")
        bank_code = slots.get("bank_code")

        if not beneficiary_name:
            return "Please specify which beneficiary you want to edit."

        if not any([new_name, customer_number, bank_code]):
            return "What would you like to update? You can send a new name, phone number, or bank code."

        beneficiaries = beneficiary_service.get_beneficiaries(user_id)
        target_beneficiary = None
        for beneficiary in beneficiaries:
            if beneficiary.name.lower() == beneficiary_name.lower():
                target_beneficiary = beneficiary
                break

        if not target_beneficiary:
            return f"Beneficiary '{beneficiary_name}' not found in your saved beneficiaries."

        success, beneficiary, message = beneficiary_service.update_beneficiary(
            beneficiary_id=target_beneficiary.id,
            user_id=user_id,
            name=new_name,
            customer_number=customer_number,
            bank_code=bank_code
        )
        return message
    
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
        # Add user context if available
        user_context_section = ""
        if user_data:
            # user_data produced by NLU uses the key 'user_id' (not 'id')
            # Ensure we pass a string user_id to the RAG manager so it matches
            # the History.user_id column (which is stored as string).
            user_id_for_rag = str(user_data.get("user_id"))
            user_context = self.rag_manager.get_extracted_user_context(
                user_id=user_id_for_rag,
                intent=intent,
                current_slots=slots,
                full_user_data=user_data
            )
        
        
        # Build the enhanced prompt
        enhanced_prompt = base_prompt.format(
            context=user_context,
            missing_slots="",
            category=slots.get('category', 'general')
        )
        
        # Append user context if available
        if user_context:
            enhanced_prompt += f"\n\n{user_context}\n\nIMPORTANT: Use the above user context to personalize your response. Consider their financial situation, goals, and history when providing advice."
        
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

    def _clean_markdown_formatting(self, response: str) -> str:
        """
        Remove markdown formatting from response.
        Removes bold (**text**), italic (*text*), and other common markdown symbols
        """
        import re
        
        # Remove bold (**text** or __text__)
        response = re.sub(r'\*\*(.+?)\*\*', r'\1', response)
        response = re.sub(r'__(.+?)__', r'\1', response)
        
        # Remove italic (*text* or _text_) - be careful not to remove single asterisks
        response = re.sub(r'\*([^*\n]+)\*', r'\1', response)
        response = re.sub(r'_([^_\n]+)_', r'\1', response)
        
        # Remove markdown headings (# ## ### etc)
        response = re.sub(r'^#+\s+', '', response, flags=re.MULTILINE)
        
        # Remove markdown code blocks (```code```)
        response = re.sub(r'```.*?```', '', response, flags=re.DOTALL)
        
        # Remove inline code (`code`)
        response = re.sub(r'`([^`]+)`', r'\1', response)
        
        return response.strip()

    def _prepare_conversation_context(self, conversation_history: List[Dict]) -> str:
        """Prepare conversation context from history"""
        if not conversation_history:
            return "New conversation"
        
        context = "Recent conversation history:\n"
        for msg in conversation_history:
            role = "User" if msg["role"] == "user" else "Assistant"
            context += f"{role}: {msg['content']}\n"
        
        return context
