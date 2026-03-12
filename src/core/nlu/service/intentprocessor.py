# core/nlu/service/intent_processor.py
import json
from typing import Dict, List, Any, Optional
from core.beneficiaries.service.beneficiary_service import BeneficiaryService
from core.nlu.service.llmclient import LLMClient
from core.nlu.config import SYSTEM_PROMPTS, RESPONSE_TEMPLATES
from core.nlu.service.datapipe.dataconfig import FINANCIAL_INSIGHTS_SYSTEM_PROMPT, INSIGHTS_SYSTEM_PROMPT
from core.nlu.service.datapipe.user_rag import UserRAGManager
from core.user.controller.usercontroller import get_db
from core.beneficiaries.service.beneficiary_service import BeneficiaryService
import logging
from core.nlu.service.datapipe.dataengine import EnhancedUserRAGManager

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
        Process expense report with enhanced financial insights
        """
        
        # Build enhanced system prompt
        system_prompt = self._build_enhanced_system_prompt(
            base_prompt=SYSTEM_PROMPTS["expense_report"],
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

    def process_payflows_intent(
        self,
        intent: str,
        user_message: str,
        conversation_history: List[Dict],
        slots: Dict[str, Any],
        user_data: Optional[Dict] = None
    ) -> str:
        """
        Process payflows management using PayflowService.
        Payflows are saved snapshots of successful payment transactions.
        """
        db = next(get_db())
        
        from core.payflows.service.payflow_service import PayflowService
        payflow_service = PayflowService(db)
        
        # For payflow DB operations we need the internal `users.id` (FK target).
        user_id = (user_data or {}).get("db_user_id") or (user_data or {}).get("user_id") or "unknown"
        
        if intent == "save_payflow":
            return self._handle_save_payflow(payflow_service, user_id, slots)
        elif intent == "view_payflows":
            return self._handle_view_payflows(payflow_service, user_id, slots)
        elif intent == "execute_payflow":
            return self._handle_execute_payflow(payflow_service, user_id, slots)
        elif intent == "delete_payflow":
            return self._handle_delete_payflow(payflow_service, user_id, slots)
        elif intent == "update_payflow":
            return self._handle_update_payflow(payflow_service, user_id, slots)
        else:
            return "Payflow intent not supported"

    def _handle_save_payflow(self, payflow_service, user_id: str, slots: Dict) -> str:
        """Handle saving a new payflow after successful transaction"""
        payflow_name = slots.get("payflow_name")
        
        if not payflow_name:
            return "Please provide a name for this payment template."
        
        # Get the saved payflow data from slots
        intent_name = slots.get("intent_name")
        slot_values = slots.get("slot_values", {})
        
        if not intent_name or not slot_values:
            return "Unable to save payflow: incomplete transaction data. Please complete a full transaction first."
        
        success, payflow, message = payflow_service.save_payflow(
            user_id=user_id,
            name=payflow_name,
            description=slots.get("description"),
            intent_name=intent_name,
            slot_values=slot_values,
            payment_method=slots.get("payment_method"),
            recipient_phone=slots.get("recipient_phone"),
            recipient_name=slots.get("recipient_name"),
            account_number=slots.get("account_number"),
            bill_provider=slots.get("bill_provider"),
            last_amount=slots.get("amount") or slots.get("last_amount"),
            requires_confirmation=slots.get("requires_confirmation", True)
        )
        
        return message

    def _handle_view_payflows(self, payflow_service, user_id: str, slots: Dict) -> str:
        """Handle viewing all payflows"""
        intent_filter = slots.get("intent_filter")
        payflows = payflow_service.list_payflows(user_id, intent_filter=intent_filter)
        
        if not payflows:
            return "You don't have any saved payment templates yet. Save one after completing a payment!"
        
        # Format payflow list
        payflow_list = "\n".join([
            f"✅ {pf.name}: {pf.intent_name.replace('_', ' ').title()} "
            f"({'Requires confirmation' if pf.requires_confirmation else 'Quick pay'}) - "
            f"Used {pf.transaction_count} times"
            for pf in payflows
        ])
        
        return f"Your saved payment templates:\n{payflow_list}"

    def _handle_execute_payflow(self, payflow_service, user_id: str, slots: Dict) -> str:
        """Handle executing a saved payflow"""
        payflow_name = slots.get("payflow_name")
        
        if not payflow_name:
            return "Please specify which payment template you want to use."
        
        # Lookup payflow by name
        payflow = payflow_service.get_payflow_by_name(user_id, payflow_name)
        
        if not payflow:
            return f"Payment template '{payflow_name}' not found. Would you like to view your saved templates?"
        
        # Prepare execution
        override_amount = slots.get("amount")
        success, prepared_slots, message = payflow_service.execute_payflow(
            user_id=user_id,
            payflow_id=payflow.id,
            override_amount=override_amount
        )
        
        if not success:
            return message
        
        # Return execution response - in real flow, this would trigger payment processing
        intent_display = payflow.intent_name.replace('_', ' ').title()
        amount = prepared_slots.get('amount', 'N/A')
        requires_confirmation = payflow.requires_confirmation
        
        if requires_confirmation:
            return f"Ready to replay your '{payflow_name}' template ({intent_display}, Amount: {amount}). Please confirm with your PIN to proceed."
        else:
            return f"Initiating direct payment using '{payflow_name}' template..."

    def _handle_delete_payflow(self, payflow_service, user_id: str, slots: Dict) -> str:
        """Handle deleting a payflow"""
        payflow_name = slots.get("payflow_name")
        
        if not payflow_name:
            return "Please specify which payment template you want to remove."
        
        # Lookup payflow by name
        payflow = payflow_service.get_payflow_by_name(user_id, payflow_name)
        
        if not payflow:
            return f"Payment template '{payflow_name}' not found."
        
        success, message = payflow_service.delete_payflow(user_id, payflow.id)
        return message

    def _handle_update_payflow(self, payflow_service, user_id: str, slots: Dict) -> str:
        """Handle updating a payflow"""
        payflow_name = slots.get("payflow_name")
        
        if not payflow_name:
            return "Please specify which payment template you want to edit."
        
        # Lookup payflow by name
        payflow = payflow_service.get_payflow_by_name(user_id, payflow_name)
        
        if not payflow:
            return f"Payment template '{payflow_name}' not found."
        
        # Prepare updates
        updates = {}
        if slots.get("new_payflow_name"):
            updates["name"] = slots.get("new_payflow_name")
        if "last_amount" in slots:
            updates["last_amount"] = slots.get("last_amount")
        
        if not updates:
            return "What would you like to update? You can change the template name or amount."
        
        success, updated_payflow, message = payflow_service.update_payflow(
            user_id=user_id,
            payflow_id=payflow.id,
            **updates
        )
        
        return message
    
    def _build_enhanced_system_prompt(
        self,
        base_prompt: str,
        user_data: Optional[Dict],
        intent: str,
        slots: Dict
    ) -> str:
        """
        Build enhanced system prompt with user context RAG
        """
        # Add user context if available
        user_context_section = ""
        if user_data and intent == "expense_report":
            # user_data produced by NLU uses the key 'user_id' (not 'id')
            # Ensure we pass a string user_id to the RAG manager so it matches
            # the History.user_id column (which is stored as string).
            # Get user name
            user_name = f"{user_data.get('first_name', '')} {user_data.get('last_name', '')}".strip()
            if not user_name:
                user_name = user_data.get('username', 'User')
            
            # Get time frame from slots or default
            time_frame = slots.get('time_period', 'the selected period')
            
            # Fetch transactions using your existing method
            transactions = self.rag_manager.get_transaction_history(
                user_id=user_data.get('user_id'),
                intent=intent,
                slots=slots
            )
            
            rag_manager = EnhancedUserRAGManager()
            
            user_financial_context = rag_manager.get_financial_insights_context(
                user_name=user_name,
                user_id=user_data.get('user_id'),
                transactions=transactions,
                time_frame=time_frame,
                user_phone=user_data.get('phone_number')
            )
            user_context_section = f"User Transaction Data:\n{json.dumps(user_financial_context, indent=2)}"
            print(f"[ENHANCED_SYSTEM_PROMPT] User Transaction Data for {user_name}:\n{json.dumps(user_financial_context, indent=2)}")
        # Build the enhanced prompt
        enhanced_prompt = base_prompt.format(
            context=user_context_section,
            missing_slots="",
            category=slots.get('category', 'general')
        )
             
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


