from typing import Dict, List, Any, Tuple
import logging
from core.nlu.config import INTENTS, SYSTEM_PROMPTS
from core.nlu.service.llmclient import LLMClient  # Add this import

logger = logging.getLogger(__name__)

class IntentDetector:
    def __init__(self):
        self.intents = INTENTS
        self.llm_client = LLMClient()  # Replace direct openai client with LLMClient

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

        # Enhanced prompt with context awareness and precision
        prompt = self._create_enhanced_prompt(user_message, current_intent)
        
        # Create prompt for intent detection
        prompt = f"""
        Read the user's message and extract:
        1. The main intent from this list: {list(self.intents.keys())}
        2. Any relevant information (slots) for that intent
        
        User message: "{user_message}"
        
        Available intents and their slots:
        {self._format_intents_for_prompt()}
        
        IMPORTANT RULES FOR BENEFICIARY DETECTION:
        - For send_money and buy_airtime intents: If the user mentions a NAME (not a phone number), extract it as "beneficiary_name" slot
        - Examples of names: "Send to John", "Buy airtime for Mom", "Send money to Ama"
        - If a phone number is provided directly, use it as "recipient" or "phone_number" slot
        - Both name and number can be provided; if name is provided, prefer extracting the name as beneficiary_name slot
        - The system will look up the saved beneficiary by name and extract the phone number automatically

        IMPORTANT RULE FOR REFERENCE EXTRACTION:
        - Extract "for [purpose]" phrases as the reference slot, including the "for" keyword
        - Examples: "send 2 cedis to lebeney for food" → extract reference as "for food"
        - Examples: "send 50 to John for transport" → extract reference as "for transport"
        - Examples: "send 100 cedis to Ama for school fees" → extract reference as "for school fees"
        - The reference describes the purpose or reason for the payment
        
        Respond in this exact format:
        INTENT: [detected_intent]
        SLOTS: [json_object_with_slots]
        MISSING: [comma_separated_missing_slots]
        
        Example with beneficiary name:
        INTENT: send_money
        SLOTS: {{"amount": "50", "beneficiary_name": "John"}}
        MISSING: 
        
        Example with direct phone number:
        INTENT: send_money
        SLOTS: {{"amount": "50", "recipient": "0234567890"}}
        MISSING: reference
        """
        
        # If an image is attached, add an explicit instruction about it so the
        # model knows there is an image URL or embedded base64 included in the
        # user message (the actual image marker is appended by LLMClient).
        image_note = ""
        if media_context and (media_context.get("image_url") or media_context.get("image_base64")):
            image_note = "\n\nNOTE: The user has provided an image. The image is referenced below. If you can use the image, use it to infer the user's intent and extract slots. If you cannot access or process the image, respond with the intent: CANNOT_PROCESS_IMAGE."
            prompt = prompt + image_note

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
                    logger.debug("Audio transcription result: %s", transcription)
                    if transcription:
                        prompt = prompt + f"\n\n[Audio transcription]: {transcription}"
                except Exception as ex:
                    logger.warning("Audio transcription failed: %s", ex)

            # Pass image data to the LLM client when available so the model can
            # perform multimodal intent detection.
            image_base64 = None
            image_url = None
            image_media_type = None
            if media_context:
                image_base64 = media_context.get("image_base64")
                image_url = media_context.get("image_url")
                image_media_type = media_context.get("image_mime_type")
                logger.debug("Media context keys: %s", list(media_context.keys()))

            logger.info("Calling LLMClient for intent detection (model=%s)", self.llm_client.model)
            response_text = self.llm_client.chat_completion(
                system_prompt=system_prompt,
                user_message=prompt,
                conversation_history=conversation_history,
                temperature=0.1,
                max_tokens=500,
                image_url=image_url,
                image_base64=image_base64,
                image_media_type=image_media_type or "image/jpeg",
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
        INTENT DETECTION GUIDELINES:
        1. Be precise - read the exact words and phrasing in the user message
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
        
        current_intent_context = f"CURRENT_INTENT: {current_intent if current_intent else 'Intent Extraction'}"
        
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
        
        User message to read: "{user_message}"
        
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
        MISSING: reference

        User starts bill payment: "Make bill payment of 1 cedi to 95200204493"
        INTENT: pay_bill
        SLOTS: {{"amount": "1", "account_number": "95200204493"}}
        MISSING: bill_type

        User continues bill payment: "ECG, the card number is 95200204493"
        INTENT: pay_bill
        SLOTS: {{"bill_type": "ECG", "account_number": "95200204493"}}
        MISSING:

        User continues bill payment: "ECG, My account number is 95200204493 and I would like to send 1 cedi"
        INTENT: pay_bill
        SLOTS: {{"bill_type": "ECG", "account_number": "95200204493", "amount": "1"}}
        MISSING:

        User continues bill payment: "My smart card number is 95200204493"
        INTENT: pay_bill
        SLOTS: {{"account_number": "95200204493"}}
        MISSING: bill_type

        User continues bill payment: "Just the card is 95200204493"
        INTENT: pay_bill
        SLOTS: {{"account_number": "95200204493"}}
        MISSING: bill_type

        User continues bill payment: "95200204493"
        INTENT: pay_bill
        SLOTS: {{"account_number": "95200204493"}}
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
        MISSING: recipient,reference

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