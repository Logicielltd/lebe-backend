from typing import Dict, List, Any, Tuple
import logging
from core.nlu.config import INTENTS, SYSTEM_PROMPTS
from core.nlu.service.llmclient import LLMClient  # Add this import

logger = logging.getLogger(__name__)

class IntentDetector:
    def __init__(self):
        self.intents = INTENTS
        self.llm_client = LLMClient()

    def detect_intent_and_slots(self, user_message: str, conversation_history: List[Dict], current_intent: str = None, media_context: Dict = None) -> Tuple[str, Dict, List[str]]:
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
        
        try:
            logger.debug("Intent detection start: user_message=%s current_intent=%s media_present=%s", user_message, current_intent, bool(media_context))

            # If audio bytes are present, transcribe and include transcription
            if media_context and media_context.get("audio_bytes"):
                try:
                    logger.info("Transcribing audio for intent detection: filename=%s", media_context.get("audio_filename"))
                    transcription = self.llm_client.transcribe_audio_from_bytes(
                        media_context.get("audio_bytes"),
                        filename=media_context.get("audio_filename", "audio.mp3")
                    )
                    logger.info("Audio transcription result: %s", transcription)
                    
                    if transcription:
                        user_message = user_message + f"\n{transcription}"
                        
                except Exception as ex:
                    logger.warning("Audio transcription failed: %s", ex)

            # If image is present, extract text and include in prompt (not as image parameter)
            if media_context and (media_context.get("image_base64") or media_context.get("image_url")):
                try:
                    logger.info("Extracting text from image for intent detection")
                    image_base64 = media_context.get("image_base64")
                    image_url = media_context.get("image_url")
                    image_media_type = media_context.get("image_mime_type", "image/jpeg")
                    
                    extracted_text = self.llm_client.extract_text_from_image(
                        image_base64=image_base64,
                        image_url=image_url,
                        image_media_type=image_media_type
                    )
                    logger.debug("Image text extraction result: %s", extracted_text)
                    if extracted_text:
                        user_message = user_message + f"\n{extracted_text}"
                except Exception as ex:
                    logger.warning("Image text extraction failed: %s", ex)

            logger.info("Calling LLMClient for intent detection (model=%s)", self.llm_client.model)
            
            # Enhanced prompt with context awareness and precision
            logger.info("User message for intent detection (truncated): %s", (user_message))
            
            prompt = self._create_enhanced_prompt(user_message, current_intent)
            
            response_text = self.llm_client.chat_completion(
                system_prompt=system_prompt,
                user_message=prompt,
                conversation_history=conversation_history,
                temperature=0.1,
                max_tokens=500,
            )

            logger.debug("Intent detection response text (truncated): %s", (response_text or '')[:1000])

            # Detect if model refused or reported inability to process images
            refusal_phrases = [
                "unable to process images",
                "i'm unable to process",
                "cannot process images",
                "can't process images",
                "cannot access the image",
                "cannot view the image",
                "can't view images",
                "do not have the ability to view images",
                "i cannot process images",
                "i can't process images",
                "i'm not able to process images"
            ]
            if response_text:
                low = response_text.lower()
                if any(p in low for p in refusal_phrases) or "cannot_process_image" in low or "cannot_process_image" in (response_text or ""):
                    logger.info("Model reported it cannot process images; returning special intent")
                    return "cannot_process_image", {}, []

            return self._parse_response(response_text)
            
        except Exception as e:
            print(f"Error in intent detection: {e}")
            return "unknown", {}, []
    
    def _create_enhanced_prompt(self, user_message: str, current_intent: str = None) -> str:
        """Create enhanced prompt with context awareness and precision"""
        
        intent_guidelines = """
        INTENT DETECTION & SLOT EXTRACTION FRAMEWORK:
        
        1. **Context Preservation Rules**:
        - When current_intent exists, evaluate message relevance before changing
        - Message is "continuation" if it provides: additional details, corrections, clarifications, or confirms missing slots
        - Message is "new intent" only if: topic completely changes, explicit new action verb, or contradicts current flow
        
        2. **Slot Extraction Precision**:
        - Extract only explicitly mentioned values
        - For numbers: identify if amount, phone, account, or duration based on context
        - For names: distinguish between beneficiary_name, bill_type, provider, and PAYFLOW_NAME
        - Handle partial information: extract what's present, leave others empty
        
        3. **CRITICAL PAYFLOW vs BENEFICIARY DETECTION** (High Priority):
        - Keywords "Use", "Send using", "Pay with" + NAME → ALWAYS execute_payflow
        - Compound/Descriptive names + amount = likely payflow (e.g., "Mom Payment", "Get Manager Airtime", "Electricity Bill")
        - Generic single names (John, Mom, Mary) without payflow action verbs = likely beneficiary_name
        - If name matches known payflow patterns, prefer execute_payflow
        - Payflow names typically describe the transaction type + recipient/purpose
        
        4. **Payflow Action Pattern Recognition**:
        - "Use [Name]" → execute_payflow (highest confidence)
        - "Send using [Name]" → execute_payflow (highest confidence)
        - "Pay with [Name]" → execute_payflow (highest confidence)
        - "[Payflow Name] of [Amount]" → execute_payflow with amount override
        - "View/Show templates/payflows" → view_payflows
        - "Delete [Payflow Name]" → delete_payflow
        - "Rename/Update [Payflow Name]" → update_payflow
        """
        
        current_intent_context = f"""
        CURRENT CONTEXT:
        - Active Intent: {current_intent if current_intent else 'None (Starting Fresh)'}
        - Priority: {'Maintain current intent' if current_intent else 'Detect new intent'}
        """
        
        # Enhanced examples covering all intent types
        examples = """
        EXAMPLES BY CATEGORY:
        
        CONVERSATIONAL:
        User: "Hello there"
        INTENT: greeting
        SLOTS: {}
        MISSING: 
        
        User: "How's the weather today?"
        INTENT: small_talk
        SLOTS: {"category": "weather"}
        MISSING: mood
        
        User: "Thanks for your help, goodbye"
        INTENT: goodbye
        SLOTS: {}
        MISSING: 
        
        FINANCIAL TIPS:
        User: "Give me some tips to save money"
        INTENT: savings_tips
        SLOTS: {}
        MISSING: 
        
        User: "How can I budget better with 2000 income?"
        INTENT: budgeting_advice
        SLOTS: {"income_level": "2000"}
        MISSING: expense_category, savings_goal
        
        User: "I have 5000 debt, need advice"
        INTENT: debt_management
        SLOTS: {"debt_amount": "5000"}
        MISSING: debt_type, income
        
        TRANSACTIONAL - CONTINUATION PATTERNS:
        User (new): "Send money to mom for food"
        INTENT: send_money
        SLOTS: {"beneficiary_name": "mom", "reference": "food"}
        MISSING: recipient, amount, reference
        
        User (continue): "Her number is 0551234567"
        INTENT: send_money  
        SLOTS: {"recipient": "0551234567"}
        MISSING: amount, reference
        
        User (continue): "Send 100 cedis for fuel"
        INTENT: send_money
        SLOTS: {"amount": "100", "reference": "fuel"}
        MISSING: recipient, reference
        
        BENEFICIARY MANAGEMENT:
        User: "Add John as new beneficiary, his number is 0551234567"
        INTENT: add_beneficiary
        SLOTS: {"beneficiary_name": "John", "customer_number": "0551234567"}
        MISSING: network, bank_code
        
        User: "Show my saved beneficiaries"
        INTENT: view_beneficiaries
        SLOTS: {}
        MISSING: 
        
        User: "Remove beneficiary Mary"
        INTENT: delete_beneficiary
        SLOTS: {"beneficiary_name": "Mary"}
        MISSING: 

        User: "Update beneficiary John to John Jr"
        INTENT: update_beneficiary
        SLOTS: {"beneficiary_name": "John", "update_field": "name", "new_beneficiary_name": "John Jr"}
        MISSING: 

        EXPENSE REPORT:
        User: "Show my expenses for last month"
        INTENT: expense_report
        SLOTS: {"time_period": "last month"}
        MISSING: category
        
        User: "How much did I spend on food?"
        INTENT: expense_report
        SLOTS: {"category": "food"}
        MISSING: time_period
        
        PAYFLOW MANAGEMENT - EXECUTION (THE KEY DISTINCTION):
        *** CRITICAL: Action verbs "Use", "Send using", "Pay with" + NAME = PAYFLOW EXECUTION ***
        *** Names WITHOUT action verbs alone = Could be beneficiary or need more context ***
        
        User: "Use Get Manager Airtime"
        INTENT: execute_payflow
        SLOTS: {"payflow_name": "Get Manager Airtime"}
        MISSING: 
        REASONING: "Use" verb + descriptive name "Get Manager Airtime" clearly indicates using a saved payflow template
        
        User: "Send using Mom Payment"
        INTENT: execute_payflow
        SLOTS: {"payflow_name": "Mom Payment"}
        MISSING: 
        REASONING: "Send using" + payflow name "Mom Payment" indicates executing saved template
        
        User: "Pay with Electricity Bill"
        INTENT: execute_payflow
        SLOTS: {"payflow_name": "Electricity Bill"}
        MISSING: 
        REASONING: "Pay with" + payflow name "Electricity Bill" indicates using saved bill payment template
        
        User: "Mom Payment of 50"
        INTENT: execute_payflow
        SLOTS: {"payflow_name": "Mom Payment", "amount": "50"}
        MISSING: 
        REASONING: Payflow name "Mom Payment" + amount override shows intent to repeat saved template with new amount
        
        User: "John Airtime of 20"
        INTENT: execute_payflow
        SLOTS: {"payflow_name": "John Airtime", "amount": "20"}
        MISSING: 
        REASONING: Payflow name "John Airtime" (compound, descriptive) + amount override = payflow execution
        
        User: "View my payment templates"
        INTENT: view_payflows
        SLOTS: {}
        MISSING: 
        REASONING: Request to view payflows
        
        User: "Show payflows"
        INTENT: view_payflows
        SLOTS: {}
        MISSING: 
        REASONING: Direct payflow viewing request
        
        User: "Delete Mom Payment"
        INTENT: delete_payflow
        SLOTS: {"payflow_name": "Mom Payment"}
        MISSING: 
        REASONING: Delete action + known payflow name
        
        User: "Rename Electricity Bill to Power Bill"
        INTENT: update_payflow
        SLOTS: {"payflow_name": "Electricity Bill", "update_field": "name", "new_payflow_name": "Power Bill"}
        MISSING: 
        REASONING: Rename/update action + payflow name
        
        COMPARISON: PAYFLOW vs BENEFICIARY DETECTION:
        User: "Buy airtime for John"
        INTENT: buy_airtime
        SLOTS: {"beneficiary_name": "John"}
        MISSING: amount
        REASONING: Generic name "John" without payflow action verb = beneficiary, not payflow
        
        User: "Send to Mom"
        INTENT: send_money
        SLOTS: {"beneficiary_name": "Mom"}
        MISSING: recipient, amount, reference
        REASONING: Generic beneficiary name without payflow action verb or payflow-specific language
        
        User: "Use John Airtime"
        INTENT: execute_payflow
        SLOTS: {"payflow_name": "John Airtime"}
        MISSING: 
        REASONING: Same person "John" but "Use" verb + full payflow name "John Airtime" = payflow template, not beneficiary
        
        User: "Send using Mom"
        INTENT: send_money (if "Mom" is a saved beneficiary for send_money) OR execute_payflow (if "Mom" is a full payflow name)
        SLOTS: {"beneficiary_name": "Mom"}  OR {"payflow_name": "Mom"}
        MISSING: recipient, amount, reference (for beneficiary) OR nothing (for payflow)
        REASONING: "Send using" + single name is ambiguous; check if matches saved payflow or beneficiary; if exact payflow match, use execute_payflow; otherwise treat as send_money with beneficiary lookup
        """
        
        return f"""

        You are an expert conversational AI that identifies user intents and extracts relevant slot information.
        A slot is a specific piece of information needed to fulfill an intent (e.g., amount, recipient).

        Your goals:
        1. Identify the user's **main intent** from the list below:
        List of defined intents: {list(self.intents.keys())}
        2. Extract slot values relevant to that intent.
        3. If the message is a continuation of an existing intent (current_intent = "{current_intent}"), 
        maintain that same intent **unless** the user clearly starts a new topic.
        4. Accurately identify missing required slots for that intent.
        
        {intent_guidelines}
        
        {current_intent_context}
        
        Available intents and their slots:
        {self._format_intents_for_prompt()}
        
        User message: "{user_message}"
        
        {examples}
        
        DECISION PROCESS:
        - Is this message clearly about a NEW intent? → Use new intent
        - Is this message continuing/refining the CURRENT intent? → Keep current intent
        - Is this message ambiguous but contextually related? → Prefer current intent
        
        CRITICAL SLOT EXTRACTION RULES:
        - Phone numbers: Extract as "recipient" or "phone_number"
        - Amounts: Extract as numeric string, preserve currency mentions for context
        - Beneficiary Names: Extract as beneficiary_name for send_money, buy_airtime
        - Time periods: Extract as "time_period" for reports, "timeframe" for tips
        - Reference/Description: Extract any additional details as "reference" or "description"
        
        RESPONSE FORMAT (STRICT):
        INTENT: [one intent from provided list]
        SLOTS: [valid JSON object with extracted slots]
        MISSING: [comma-separated list of required slots not yet provided]
        CONFIDENCE: [HIGH, MEDIUM, or LOW]
        
        CONFIDENCE SCORING WITH PAYFLOW PRIORITY:
        - HIGH: 
          * User message contains "Use [Name]", "Send using [Name]", "Pay with [Name]" → execute_payflow (highest)
          * User clearly expresses specific intent with unambiguous language
          * Payflow-specific action verbs detected with identifiable payflow name
        - MEDIUM: 
          * Intent is likely but with some ambiguity or less clear language
          * Compound names without explicit action verbs (could be payflow or beneficiary)
          * User message has partial payflow indicators
        - LOW: 
          * Single generic name alone (John, Mom) without payflow action verbs
          * User message is vague or could refer to multiple intents
          * Insufficient information to determine payflow vs beneficiary
        
        PAYFLOW DETECTION CONFIDENCE RULES:
        - "Use" + name = HIGH confidence for execute_payflow
        - "Send using" + name = HIGH confidence for execute_payflow
        - "Pay with" + name = HIGH confidence for execute_payflow
        - Descriptive name (2+ words) + amount = MEDIUM-HIGH for execute_payflow
        - Generic name alone = LOW for payflow, prefer beneficiary_name extraction
        
        IMPORTANT VALIDATION:
        - SLOTS must be valid JSON (use double quotes)
        - INTENT must exactly match available intent names
        - MISSING should list only required_slots that are not in SLOTS
        - CONFIDENCE must be HIGH, MEDIUM, or LOW
        
        IMPORTANT RULES FOR BENEFICIARY DETECTION:
        - For send_money and buy_airtime intents: If the user mentions a NAME (not a phone number), extract it as "beneficiary_name" slot
        - Examples of names: "Send to John", "Buy airtime for Mom", "Send money to Ama"
        - If a phone number is provided directly, use it as "recipient" or "phone_number" slot
        - Both name and number can be provided; if name is provided, prefer extracting the name as beneficiary_name slot
        - The system will look up the saved beneficiary by name and extract the phone number automatically
        
        IMPORTANT RULE FOR PAYFLOW DETECTION (OVERRIDES BENEFICIARY WHEN ACTION VERB PRESENT):
        - When user says "Use [Name]", "Send using [Name]", or "Pay with [Name]" → This is ALWAYS execute_payflow, NOT a beneficiary lookup
        - The name in payflow context is payflow_name, not beneficiary_name
        - Payflows are saved TEMPLATES with specific names created by the user (e.g., "Mom Payment", "Get Manager Airtime")
        - If you see action verbs like "Use", "Send using", "Pay with", "pay using", "execute" + a name → extract as payflow_name, NOT beneficiary_name
        - Example: "Use Get Manager Airtime" → execute_payflow with payflow_name="Get Manager Airtime", NOT buy_airtime with beneficiary_name="Get Manager Airtime"

        FINAL ACCURACY CHECK:
        - If the user's message clarifies or adds to the current active intent, do not change it.
        - Only switch to a new intent if the user message explicitly refers to a different goal or action.
        - Always ensure `SLOTS` is valid JSON.
        
        PAYFLOW-SPECIFIC FINAL CHECKS:
        - If message contains action verbs "Use", "Send using", or "Pay with" + name → MUST be execute_payflow (not the regular intent)
        - If message is "[Descriptive Name] of [Amount]" → Treat as execute_payflow with amount override
        - If previous context shows user has saved payflows and mentions a payflow-like name → Prefer execute_payflow
        - If unsure between generic beneficiary name vs payflow name → Ask for clarification or check saved payflows first
        - Single generic names (John, Mary) mentioned alone = beneficiary lookup, NOT payflow
        - Compound/descriptive names (Mom Payment, Get Manager Airtime, Electricity Bill) = payflow names
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
        confidence = "MEDIUM"  # Default confidence
        
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
            elif line.startswith('CONFIDENCE:'):
                confidence = line.replace('CONFIDENCE:', '').strip().upper()
        
        # If confidence is LOW, return intent_not_clear instead
        if confidence == "LOW":
            logger.info("Low confidence intent detected (original: %s), returning intent_not_clear", intent)
            return "intent_not_clear", {}, []
        
        return intent, slots, missing_slots
