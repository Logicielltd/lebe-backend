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
        
        1. **Primary Decision Rules** (in order of priority):
        - If message contains explicit financial transaction keywords (send, pay, buy, check, loan, budget), prioritize transactional intents
        - If message is casual (hello, hi, how are you), use conversational intents
        - If message asks for advice/tips, use financial_tips category intents
        - If message mentions beneficiaries, use beneficiary management intents
        
        2. **Context Preservation Rules**:
        - When current_intent exists, evaluate message relevance before changing
        - Message is "continuation" if it provides: additional details, corrections, clarifications, or confirms missing slots
        - Message is "new intent" only if: topic completely changes, explicit new action verb, or contradicts current flow
        
        3. **Slot Extraction Precision**:
        - Extract only explicitly mentioned values
        - For numbers: identify if amount, phone, account, or duration based on context
        - For names: distinguish between beneficiary_name, bill_type, provider
        - Handle partial information: extract what's present, leave others empty
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
        
        IMPORTANT VALIDATION:
        - SLOTS must be valid JSON (use double quotes)
        - INTENT must exactly match available intent names
        - MISSING should list only required_slots that are not in SLOTS
        - If current_intent exists and message relates to it, PREFER keeping same intent

        FINAL ACCURACY CHECK:
        - If the user's message clarifies or adds to the current active intent**, do not change it.
        - Only switch to a new intent if the user message explicitly refers to a different goal or action.
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
