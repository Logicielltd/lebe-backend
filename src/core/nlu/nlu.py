
import base64
from dataclasses import dataclass
from decimal import Decimal
import io
from core.cloudstorage.service.storageservice import StorageService
from core.histories.service.historyservice import HistoryService
import openai
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
import logging
from core.auth.service.authservice import AuthService
from core.nlu.config import INTENT_CATEGORIES
from core.nlu.service.intentprocessor import IntentProcessor
from core.nlu.service.intents import IntentDetector
from core.nlu.service.slot_manager import SlotManager
from core.nlu.service.conversation_manager import ConversationManager
from core.nlu.service.security import SecurityManager
from core.nlu.emitters.response import ResponseFormatter
from core.receipts.service.image_gen import ReceiptGenerator
from core.user.service.user_service import UserService
from utilities.dbconfig import SessionLocal
from core.auth.dto.request.user_create import UserCreateRequest
from core.receipts.service.receipt_service import ReceiptService
from core.payments.dto.paymentdto import PaymentDto
from core.payments.model.paymentmethod import PaymentMethod
from core.payments.model.paymentstatus import PaymentStatus
from core.payments.model.paynetwork import Network
from core.payments.service.paymentservice import PaymentService
from utilities.uniqueidgenerator import UniqueIdGenerator
from decimal import Decimal
from core.beneficiaries.utility.network_detector import NetworkDetector


logger = logging.getLogger(__name__)

@dataclass
class ReceiptData:
    transaction_id: str
    user_id: str
    transaction_type: str
    amount: str
    status: str
    sender: str
    receiver: str
    payment_method: str
    timestamp: datetime
    # Optional loan fields
    interest_rate: Optional[str] = None
    loan_period: Optional[str] = None
    expected_pay_date: Optional[str] = None
    penalty_rate: Optional[str] = None

class LebeNLUSystem:
    def __init__(self):
        self.intent_detector = IntentDetector()
        self.slot_manager = SlotManager()
        self.conversation_manager = ConversationManager()
        self.security_manager = SecurityManager()
        self.response_formatter = ResponseFormatter()
        self.intent_processor = IntentProcessor()
    
    def process_message(
        self, 
        user_id: str, 
        user_message: str, 
        user_subscription_status: str,
        image_media_id: Optional[str] = None,
        image_url: Optional[str] = None,
        audio_media_id: Optional[str] = None,
        audio_url: Optional[str] = None
    ) -> str:
        """
        Main method to process user messages with optional multimodal inputs (images/audio)
        
        Args:
            user_id: User identifier
            user_message: Text message from user
            user_subscription_status: User's subscription status
            image_media_id: WhatsApp media ID for image
            image_url: Direct URL to image
            audio_media_id: WhatsApp media ID for audio
            audio_url: Direct URL to audio
        """

        # Get conversation state
        state = self.conversation_manager.get_conversation_state(user_id)

        # Add user message to history
        logger.info("Received message from %s: %s", user_id, (user_message or '')[:200])
        self.conversation_manager.update_conversation_history(user_id, "user", user_message)

        # Process multimodal inputs (images/audio)
        media_context = {}
        if image_media_id or image_url or audio_media_id or audio_url:
            logger.info("Processing media inputs for user %s", user_id)
            media_context = self._process_media_inputs(
                user_id,
                image_media_id=image_media_id,
                image_url=image_url,
                audio_media_id=audio_media_id,
                audio_url=audio_url
            )
            logger.debug("Media context returned: %s", {k: (len(v) if isinstance(v, (bytes, str)) else type(v).__name__) for k,v in (media_context or {}).items()})

        # Check if waiting for payment confirmation
        if state.waiting_for_payment_confirmation:
            return self._handle_payment_confirmation(user_id, user_message, media_context)

        # Check if waiting for PIN
        if state.waiting_for_pin:
            return self._handle_pin_verification(user_id, user_message)
        
        # Detect intent and extract slots
        logger.info("Detecting intent for user %s (current_intent=%s)", user_id, state.current_intent)
        intent, extracted_slots, missing_slots = self.intent_detector.detect_intent_and_slots(
            user_message, state.conversation_history, state.current_intent, media_context
        )
        # If the model explicitly reported it cannot process the image, ask the user
        if intent == "cannot_process_image":
            logger.info("Model cannot process image for user %s; asking for description", user_id)
            response = self.response_formatter.format_response("", "ask_for_image_description")
            self.conversation_manager.update_conversation_history(user_id, "assistant", response)
            return response
        logger.info("Detected intent=%s missing=%s", intent, missing_slots)

        # Validate and merge slots
        validated_slots = self.slot_manager.validate_slots(intent, extracted_slots)

        state.collected_slots.update(validated_slots)

        state.current_intent = intent
        
        # CHECK SUBSCRIPTION STATUS EARLY
        # print (f"User Subscription Status: {user_subscription_status}")
        # if not user_subscription_status and intent != "create_new_account":
        #     # User needs subscription but isn't trying to create account
        #     response = self.response_formatter.format_response(
        #         "subscription_required", 
        #         "need_subscription",
        #         current_intent=intent  # Pass the original intent for context
        #     )
        #     self.conversation_manager.update_conversation_history(user_id, "assistant", response)
        #     return response
        
        # Check for missing required slots
        current_missing = self.slot_manager.get_missing_slots(intent, state.collected_slots)
        
        if intent in ["greeting"]:
            # Handle simple intents directly
            response = self.response_formatter.format_response(intent, "greeting")

        elif current_missing:
            # Ask for missing slots
            prompt = self.slot_manager.generate_slot_prompt(intent, current_missing)
            response = self.response_formatter.format_response(
                intent, "missing_slots", prompt=prompt
            )
 
        else:
            # All slots collected, execute action directly (PIN verification commented out for testing)
            # TODO: Re-enable PIN verification after payment flow is working
            # if self.security_manager.is_pin_required(intent):
            #     # Set pending action using ConversationManager method
            #     self.conversation_manager.set_pending_action(
            #         user_id,
            #         intent,
            #         state.collected_slots.copy()
            #     )
            #     response = self.response_formatter.format_response(
            #         intent, "confirm_action", **state.collected_slots
            #     )
            # else:
            #     # Execute non-secure action directly
            response = self._execute_action(user_id, intent, state.collected_slots, user_message, state.conversation_history)
        
        # Add assistant response to history
        self.conversation_manager.update_conversation_history(user_id, "assistant", response)

        # Clear collected slots if action was executed
        if not current_missing:
            self.conversation_manager.clear_collected_slots(user_id)
        
        return response
    
    def _handle_pin_verification(self, user_id: str, pin_input: str) -> str:
        """Handle PIN verification for pending actions"""
        state = self.conversation_manager.get_conversation_state(user_id)

        # Validate pending action exists
        if not state.pending_action or "intent" not in state.pending_action or "slots" not in state.pending_action:
            error_response = self.response_formatter.format_response("", "error", message="No pending action found. Please start over.")
            self.conversation_manager.update_conversation_history(user_id, "assistant", error_response)
            self.conversation_manager.reset_conversation_state(user_id)
            return error_response

        if self.security_manager.verify_pin(user_id, pin_input):
            # PIN verified, execute action
            pending_intent = state.pending_action["intent"]
            pending_slots = state.pending_action["slots"]

            print(f"PIN verified for user {user_id}. Executing pending action: intent={pending_intent}, slots={pending_slots}")

            response = self._execute_action(
                user_id,
                pending_intent,
                pending_slots
            )
            # Reset conversation state
            self.conversation_manager.reset_conversation_state(user_id)
        else:
            # Invalid PIN
            response = self.response_formatter.format_response("", "invalid_pin")
            # Keep waiting for PIN

        self.conversation_manager.update_conversation_history(user_id, "assistant", response)
        return response

    def _handle_payment_confirmation(self, user_id: str, user_response: str, media_context: Optional[Dict[str, Any]] = None) -> str:
        """Handle user's yes/no response for payment confirmation"""
        state = self.conversation_manager.get_conversation_state(user_id)

        # Check if pending payment exists
        if not state.pending_payment_dto:
            error_response = self.response_formatter.format_response("", "error", message="No pending payment found. Please start over.")
            self.conversation_manager.update_conversation_history(user_id, "assistant", error_response)
            state.waiting_for_payment_confirmation = False
            self.conversation_manager._save_conversation_state(state)
            return error_response

        # If media (audio/image) was provided, try to extract a textual yes/no
        if media_context:
            # Prefer audio transcription if available
            try:
                if media_context.get("audio_bytes"):
                    transcription = None
                    try:
                        transcription = self.intent_detector.llm_client.transcribe_audio_from_bytes(
                            media_context.get("audio_bytes"),
                            filename=media_context.get("audio_filename", "audio.mp3")
                        )
                    except Exception:
                        transcription = None
                    if transcription:
                        user_response = transcription
                # If no audio, try to ask the LLM to interpret the image as a yes/no
                elif media_context.get("image_base64") or media_context.get("image_url"):
                    try:
                        system_prompt = (
                            "You are a concise classifier. Given an image supplied by the user, "
                            "determine whether the image indicates a CONFIRMATION (yes) or a REJECTION (no) of a pending payment. "
                            "Respond with a single word: yes or no. Do not add any extra text."
                        )
                        user_msg = (
                            "Interpret the attached image and respond with only 'yes' or 'no' "
                            "to indicate whether the user CONFIRMS the pending payment."
                        )
                        image_base64 = media_context.get("image_base64")
                        image_url = media_context.get("image_url")
                        image_mime = media_context.get("image_mime_type") or media_context.get("mime_type") or "image/jpeg"
                        img_response = self.intent_detector.llm_client.chat_completion(
                            system_prompt=system_prompt,
                            user_message=user_msg,
                            conversation_history=None,
                            temperature=0.0,
                            max_tokens=10,
                            image_url=image_url,
                            image_base64=image_base64,
                            image_media_type=image_mime,
                        )
                        if img_response:
                            user_response = img_response
                    except Exception:
                        pass
            except Exception:
                # If any media handling fails, fall back to textual user_response
                pass

        # Check user's response (yes/no/confirm/proceed/etc.)
        user_response_lower = (user_response or "").lower().strip()
        confirmation_keywords = ["yes", "y", "confirm", "ok", "okay", "proceed", "go ahead"]
        rejection_keywords = ["no", "n", "cancel", "don't", "dont", "stop"]

        if any(keyword in user_response_lower for keyword in confirmation_keywords):
            # User confirmed payment
            logger.info(f"[PAYMENT_CONFIRMATION] User {user_id} confirmed payment")
            intent = state.current_intent
            # Use slots stored in pending_payment_dto (includes receiver_name and providers)
            slots = state.pending_payment_dto.get("slots", state.collected_slots)

            # Execute the payment with confirmed slots
            response = self._execute_action(user_id, intent, slots, user_response, state.conversation_history)

            # Clear confirmation state
            state.waiting_for_payment_confirmation = False
            state.pending_payment_dto = {}
            self.conversation_manager._save_conversation_state(state)

        elif any(keyword in user_response_lower for keyword in rejection_keywords):
            # User rejected payment
            logger.info(f"[PAYMENT_CONFIRMATION] User {user_id} rejected payment")
            response = self.response_formatter.format_response(state.current_intent, "payment_cancelled")

            # Clear confirmation state
            state.waiting_for_payment_confirmation = False
            state.pending_payment_dto = {}
            state.current_intent = ""
            state.collected_slots = {}
            self.conversation_manager._save_conversation_state(state)

        else:
            # Unclear response, ask again
            logger.info(f"[PAYMENT_CONFIRMATION] User {user_id} gave unclear response: {user_response}")
            response = self.response_formatter.format_response(state.current_intent, "confirm_again",
                                                               message="I didn't understand. Please reply 'yes' to confirm or 'no' to cancel.")

        self.conversation_manager.update_conversation_history(user_id, "assistant", response)
        return response

    def _execute_action(self, user_id: str, intent: str, slots: Dict, user_message: str = "", conversation_history: List[Dict] = None) -> str:
        """Execute the actual financial action through payment service"""
        try:
            print(f"[EXECUTE_ACTION] User {user_id}: intent={intent}, slots={slots}")

            # Payment intents that require Orchard API
            payment_intents = ["buy_airtime", "send_money", "pay_bill", "get_loan"]

            if intent in payment_intents:
                print(f"[EXECUTE_ACTION] Routing to payment processor for intent: {intent}")
                return self._process_payment_intent(user_id, intent, slots)
            else:
                print(f"[EXECUTE_ACTION] Routing to non-payment processor for intent: {intent}")
                return self._process_non_payment_intent(user_id, intent, user_message, conversation_history, slots)

        except Exception as e:
            import traceback
            print(f"[EXECUTE_ACTION] ERROR: {e}")
            traceback.print_exc()
            return self.response_formatter.format_response(intent, "error", message=str(e))

    def _process_payment_intent(self, user_id: str, intent: str, slots: Dict) -> str:
        """Process payment intents through PaymentService"""

        print(f"[PAYMENT_INTENT] Starting payment processing for intent: {intent}")
        print(f"[PAYMENT_INTENT] Slots received: {slots}")

        db = SessionLocal()
        try:
            # Map network string to Network enum (per Orchard API spec)
            network_map = {
                "MTN": Network.MTN,
                "Vodafone": Network.VOD,
                "VOD": Network.VOD,
                "AirtelTigo": Network.AIR,
                "AIR": Network.AIR,
                "Mastercard": Network.MAS,
                "MAS": Network.MAS,
                "VISA": Network.VIS,
                "VIS": Network.VIS,
                "Bank": Network.BNK,
                "BNK": Network.BNK
            }

            print(f"[PAYMENT_INTENT] Creating PaymentDto for intent: {intent}")

            # Create PaymentDto based on intent
            if intent == "buy_airtime":
                payment_dto = PaymentDto(
                    senderPhone=user_id,  # User initiating the payment
                    receiverPhone=slots.get('phone_number', user_id),  # Use extracted phone number (supports buying airtime for others)
                    network=network_map.get(slots.get('network', 'MTN'), Network.MTN),
                    paymentMethod=PaymentMethod.MOBILE_MONEY,
                    serviceName="Airtime Top-Up",
                    amountPaid=Decimal(slots.get('amount', '0')),
                    transactionId=str(UniqueIdGenerator.generate())
                )

            elif intent == "send_money":
                # Get sender's actual name from database
                from core.user.model.User import User
                sender_name = "User"
                try:
                    sender_user = db.query(User).filter(User.phone == user_id).first()
                    if sender_user:
                        sender_name = f"{sender_user.first_name} {sender_user.last_name}".strip()
                except Exception as e:
                    logger.warning(f"Could not fetch user name for {user_id}: {e}")

                payment_dto = PaymentDto(
                    senderPhone=user_id,  # User initiating the payment
                    receiverPhone=slots.get('recipient'),  # Recipient gets the money
                    network=network_map.get(slots.get('network', 'MTN'), Network.MTN),
                    paymentMethod=PaymentMethod.MOBILE_MONEY,
                    customerName=slots.get('recipient_name', 'Unknown'),
                    senderName=sender_name,  # Actual user name from database
                    receiverName=slots.get('receiver_name'),  # Verified account holder name from account inquiry
                    senderProvider=slots.get('sender_provider'),  # Provider for sender
                    receiverProvider=slots.get('receiver_provider'),  # Provider for receiver
                    serviceName=f"Money Transfer to {slots.get('recipient')}",
                    amountPaid=Decimal(slots.get('amount', '0')),
                    transactionId=str(UniqueIdGenerator.generate())
                )

            elif intent == "pay_bill":
                # For bill payment: senderPhone is user, receiverPhone is the smart card/account number
                bill_type = slots.get('bill_type', '')
                account_number = slots.get('account_number', '')

                # Map bill_type to utility network codes (GOT, DST, ECG, GHW, etc.)
                # bill_type examples: GoTV, DStv, ECG, Ghana Water, Surfline, etc.
                bill_network_map = {
                    'gotv': Network.GOT,
                    'dstv': Network.DST,
                    'ecg': Network.ECG,
                    'ghana water': Network.GHW,
                    'water': Network.GHW,
                    'surfline': Network.SFL,
                    'telesol': Network.TLS,
                    'startimes': Network.STT,
                    'box office': Network.BXO,
                }

                # Telco bill networks (don't require external billers inquiry)
                # These are predefined in the system and don't need external biller lookup
                telco_networks = {Network.GOT, Network.DST, Network.STT}

                # Map non-telco bill types to external biller IDs (for ABS payments)
                # These are obtained from the /ext-billers INF endpoint
                biller_id_map = {
                    'ecg': '0E8440AA1',  # Electricity Company of Ghana
                    'ghana water': 'GHW_ID',  # Ghana Water Company (placeholder - get from INF)
                    'water': 'GHW_ID',
                    'surfline': 'SFL_ID',  # Surfline (placeholder)
                    'telesol': 'TLS_ID',  # Telesol (placeholder)
                    'box office': 'BXO_ID',  # Box Office (placeholder)
                    'gotv': 'F804DBCF',  # GoTV (if ABS instead of telco)
                }

                # Try to match bill_type to network, default to GOT if unknown
                selected_network = Network.GOT
                for key, network in bill_network_map.items():
                    if key in bill_type.lower():
                        selected_network = network
                        break

                # For ABS bills after confirmation, retrieve biller_id from pending_payment_dto
                ext_biller_ref_id = None
                amount_to_pay = slots.get('amount', '0')
                state_temp = self.conversation_manager.get_conversation_state(user_id)
                if state_temp.pending_payment_dto:
                    ext_biller_ref_id = state_temp.pending_payment_dto.get('biller_id')
                    # Use invoice amount if available (for fixed bills)
                    invoice_amount = state_temp.pending_payment_dto.get('invoice_amount')
                    if invoice_amount:
                        amount_to_pay = invoice_amount

                payment_dto = PaymentDto(
                    senderPhone=user_id,  # User initiating the payment (paying the bill)
                    receiverPhone=account_number,  # Smart card/account number where bill is paid
                    network=selected_network,  # Utility provider (GoTV, DStv, ECG, etc.)
                    paymentMethod=PaymentMethod.MOBILE_MONEY,
                    serviceName=f"Bill Payment: {bill_type}",
                    amountPaid=Decimal(amount_to_pay),
                    transactionId=str(UniqueIdGenerator.generate()),
                    extBillerRefId=ext_biller_ref_id  # Set biller ID for ABS bills
                )

            elif intent == "get_loan":
                payment_dto = PaymentDto(
                    senderPhone=user_id,  # User receiving payout (merchant → user)
                    receiverPhone=user_id,  # Payout to user's account
                    network=network_map.get(slots.get('network', 'MTN'), Network.MTN),
                    paymentMethod=PaymentMethod.MOBILE_MONEY,
                    serviceName="Loan Disbursement",
                    amountPaid=Decimal(slots.get('loan_amount', '0')),
                    transactionId=str(UniqueIdGenerator.generate())
                )
            else:
                return self.response_formatter.format_response(intent, "error", message=f"Unknown payment intent: {intent}")

            print(f"[PAYMENT_INTENT] PaymentDto created successfully")

            # For pay_bill with non-telco (ABS), perform invoice and biller inquiry
            state = self.conversation_manager.get_conversation_state(user_id)
            if intent == "pay_bill" and selected_network not in telco_networks and not state.pending_payment_dto:
                logger.info(f"[BILL_INQUIRY] Performing invoice and biller inquiry for non-telco bill: {bill_type}")
                try:
                    payment_service = PaymentService(db)

                    # Get biller ID from mapping
                    biller_id = None
                    for key, bid in biller_id_map.items():
                        if key in bill_type.lower():
                            biller_id = bid
                            break

                    if not biller_id:
                        return self.response_formatter.format_response(intent, "error", message=f"Unknown biller type: {bill_type}")

                    # Step 1: Call INV inquiry to get customer invoice details
                    logger.info(f"[BILL_INQUIRY] Calling INV for biller_id={biller_id}, customer_ref={account_number}")
                    invoice_response = payment_service.payment_gateway_client.external_biller_invoice_inquiry(
                        ext_biller_ref_id=biller_id,
                        ext_biller_pan=account_number,
                        ext_biller_ref_type=bill_type,
                        network="ABS",
                        operation="INV"
                    )

                    if invoice_response.status_code == 200:
                        invoice_data = invoice_response.json()
                        logger.info(f"[BILL_INQUIRY_INV_SUCCESS] Response: {invoice_data}")

                        # Extract invoice details
                        invoice_details = invoice_data.get("details", [{}])[0] if invoice_data.get("details") else {}
                        customer_name = invoice_details.get("invoiceName", "the customer")
                        invoice_amount = invoice_details.get("invoiceAmount")  # Can be null for flexible payments
                        invoice_id = invoice_details.get("invoiceId", account_number)

                        # Step 2: Call INF inquiry to get biller payment rules
                        logger.info(f"[BILL_INQUIRY] Calling INF for biller_id={biller_id}")
                        try:
                            biller_info_response = payment_service.payment_gateway_client.external_billers_inquiry(
                                customer_number=account_number,
                                network="ABS",
                                operation="INF"
                            )
                        except Exception as e:
                            logger.warning(f"[BILL_INQUIRY_INF_WARNING] Could not fetch biller rules: {str(e)}, continuing with invoice details only")
                            biller_info_response = None

                        biller_rules = {}
                        if biller_info_response and biller_info_response.status_code == 200:
                            billers_data = biller_info_response.json()
                            logger.info(f"[BILL_INQUIRY_INF_SUCCESS] Response received")

                            # Find matching biller in the list
                            for biller in billers_data.get("data", []):
                                if biller.get("billerId") == biller_id:
                                    biller_rules = {
                                        "billerName": biller.get("billerName"),
                                        "billerCategory": biller.get("billerCategory"),
                                        "paymentFlag": biller.get("paymentFlag"),  # PayPart or PayFull
                                        "minAmount": biller.get("minAmount"),
                                        "maxAmount": biller.get("maxAmount")
                                    }
                                    break

                        # Create confirmation message with invoice and biller details
                        if invoice_amount:
                            confirmation_msg = f"Bill for {customer_name}:\n"
                            confirmation_msg += f"Amount Due: GHS {invoice_amount}\n"
                            if biller_rules:
                                confirmation_msg += f"Min Payment: GHS {biller_rules.get('minAmount', 'N/A')}, "
                                confirmation_msg += f"Max: GHS {biller_rules.get('maxAmount', 'N/A')}\n"
                            confirmation_msg += f"Please reply 'yes' to confirm or 'no' to cancel."
                        else:
                            # Flexible payment - user can pay any amount
                            confirmation_msg = f"Bill for {customer_name} (Flexible Payment):\n"
                            if biller_rules:
                                confirmation_msg += f"Payment Range: GHS {biller_rules.get('minAmount', '0')} - GHS {biller_rules.get('maxAmount', 'unlimited')}\n"
                            confirmation_msg += f"Please reply 'yes' to confirm or 'no' to cancel."

                        # Store payment info and set waiting for confirmation
                        state.current_intent = intent
                        state.collected_slots = slots
                        state.waiting_for_payment_confirmation = True
                        state.pending_payment_dto = {
                            "bill_type": bill_type,
                            "customer_name": customer_name,
                            "customer_ref": account_number,
                            "biller_id": biller_id,
                            "invoice_amount": invoice_amount,
                            "invoice_id": invoice_id,
                            "biller_rules": biller_rules,
                            "slots": slots
                        }
                        self.conversation_manager._save_conversation_state(state)

                        logger.info(f"[BILL_INQUIRY] Waiting for payment confirmation from user {user_id}")
                        return self.response_formatter.format_response(intent, "payment_confirmation", message=confirmation_msg)

                    else:
                        try:
                            response_data = invoice_response.json()
                            error_msg = response_data.get("resp_desc", "Invoice inquiry failed") if isinstance(response_data, dict) else str(response_data)
                        except:
                            error_msg = f"API returned status {invoice_response.status_code}: {invoice_response.text[:100]}"
                        logger.error(f"[BILL_INQUIRY_FAILED] Status: {invoice_response.status_code}, Error: {error_msg}")
                        return self.response_formatter.format_response(intent, "error", message=f"Could not retrieve bill details: {error_msg}")

                except Exception as e:
                    logger.error(f"[BILL_INQUIRY_ERROR] Error during bill inquiry: {str(e)}", exc_info=True)
                    return self.response_formatter.format_response(intent, "error", message=f"Error retrieving bill details: {str(e)}")

            # For send_money, perform account inquiry and wait for confirmation (only if not already done)
            if intent == "send_money" and not state.pending_payment_dto:
                logger.info(f"[ACCOUNT_INQUIRY] Performing account inquiry for send_money")
                try:
                    payment_service = PaymentService(db)
                    recipient_phone = slots.get('recipient')
                    slot_network = slots.get('network')
                    detected_network, _ = NetworkDetector.detect_network_from_phone(recipient_phone or "")
                    recipient_network = network_map.get(slot_network) if slot_network else None
                    if not recipient_network and detected_network:
                        recipient_network = network_map.get(detected_network, Network.MTN)
                    if not recipient_network:
                        recipient_network = Network.MTN

                    # Call account inquiry
                    inquiry_response = payment_service.payment_gateway_client.account_inquiry(
                        customer_number=recipient_phone,
                        network=recipient_network.value
                    )

                    if inquiry_response.status_code == 200:
                        inquiry_data = inquiry_response.json()
                        logger.info(f"[ACCOUNT_INQUIRY_SUCCESS] Response: {inquiry_data}")

                        # Extract account holder name from response
                        account_name = inquiry_data.get("account_name") or inquiry_data.get("name") or "the recipient"
                        amount = slots.get('amount')

                        # Detect sender's network from sender's phone
                        from utilities.provider_mapper import ProviderMapper

                        sender_network_tuple = NetworkDetector.detect_network_from_phone(user_id)
                        sender_network_str = sender_network_tuple[0] if isinstance(sender_network_tuple, tuple) else sender_network_tuple
                        sender_network = network_map.get(sender_network_str, Network.MTN)

                        # Update PaymentDto with sender and receiver information
                        payment_dto.receiverName = account_name
                        payment_dto.senderProvider = ProviderMapper.get_provider(sender_network)
                        payment_dto.receiverProvider = ProviderMapper.get_provider(recipient_network)

                        # Add receiver_name to slots for later use
                        slots_with_receiver = dict(slots)
                        slots_with_receiver['receiver_name'] = account_name
                        slots_with_receiver['sender_provider'] = ProviderMapper.get_provider(sender_network)
                        slots_with_receiver['receiver_provider'] = ProviderMapper.get_provider(recipient_network)

                        # Create confirmation message with provider information
                        receiver_provider = ProviderMapper.get_provider(recipient_network)
                        confirmation_msg = f"Are you sure you want to send GHS {amount} to {recipient_phone} ({account_name}) on {receiver_provider}?\nPlease reply 'yes' to confirm or 'no' to cancel."

                        # Store payment info and set waiting for confirmation
                        state.current_intent = intent
                        state.collected_slots = slots_with_receiver
                        state.waiting_for_payment_confirmation = True
                        state.pending_payment_dto = {
                            "account_name": account_name,
                            "recipient_phone": recipient_phone,
                            "amount": amount,
                            "slots": slots_with_receiver,  # Store all slots with receiver_name for later use
                            "sender_provider": ProviderMapper.get_provider(sender_network),
                            "receiver_provider": ProviderMapper.get_provider(recipient_network)
                        }
                        self.conversation_manager._save_conversation_state(state)

                        logger.info(f"[ACCOUNT_INQUIRY] Waiting for payment confirmation from user {user_id}")
                        return self.response_formatter.format_response(intent, "payment_confirmation", message=confirmation_msg)

                    else:
                        error_msg = inquiry_response.json().get("resp_desc", "Account inquiry failed")
                        logger.error(f"[ACCOUNT_INQUIRY_FAILED] Status: {inquiry_response.status_code}, Error: {error_msg}")
                        return self.response_formatter.format_response(intent, "error", message=f"Could not verify recipient account: {error_msg}")

                except Exception as e:
                    logger.error(f"[ACCOUNT_INQUIRY_ERROR] Error during account inquiry: {str(e)}", exc_info=True)
                    # Fall back to regular processing if inquiry fails
                    logger.info(f"[ACCOUNT_INQUIRY_FALLBACK] Falling back to direct payment processing")

            print(f"[PAYMENT_INTENT] Calling PaymentService.make_payment() with intent={intent}")

            # Process payment through PaymentService
            payment_service = PaymentService(db)

            result = payment_service.make_payment(payment_dto, intent)

            print(f"[PAYMENT_INTENT] Payment result: status={result.status}, response_code={result.responseCode}, transaction_id={result.transactionId}")

            # Create history record
            history_service = HistoryService(db)

            transaction_mapping = {
                "buy_airtime": ("debit", slots.get('amount')),
                "send_money": ("debit", slots.get('amount')),
                "pay_bill": ("debit", slots.get('amount')),
                "get_loan": ("credit", slots.get('loan_amount'))
            }

            transaction_type, amount = transaction_mapping.get(intent, (None, None))

            if transaction_type:
                history_service.create_history(
                    user_id=user_id,
                    intent=intent,
                    transaction_type=transaction_type,
                    amount=amount,
                    recipient=slots.get('recipient') or slots.get('phone_number'),
                    phone_number=user_id,
                    description=f"{intent.replace('_', ' ').title()} - Transaction ID: {payment_dto.transactionId}",
                    metadata={"slots": slots, "payment_status": result.status}
                )

            # Return response based on payment result
            # NOTE: Receipt generation happens in the callback, not here
            if result.status == PaymentStatus.PENDING:
                message = self._get_processing_message(intent, slots, result)
                return self.response_formatter.format_response(intent, message_type="processing", message=message)
            elif result.status == PaymentStatus.SUCCESS:
                message = self._get_success_message(intent, slots, result)
                return self.response_formatter.format_response(intent, message_type="success", message=message)
            else:
                error_msg = result.responseDescription or "Payment processing failed"
                return self.response_formatter.format_response(intent, message_type="error", message=error_msg)

        finally:
            db.close()

    def _process_non_payment_intent(self, user_id: str, intent: str, user_message: str, conversation_history: List[Dict], slots: Dict) -> str:
        """Process non-payment intents"""
        """Route intent to the appropriate processor"""
        conversational_intents = INTENT_CATEGORIES["conversational"]
        financial_tips_intents = INTENT_CATEGORIES["financial_tips"]
        expense_report_intents = INTENT_CATEGORIES["expense_report"]
        beneficiaries_intents = INTENT_CATEGORIES["beneficiaries"]

        user_data = self._get_user_data(user_id)
        
        if intent in conversational_intents:
            return self.intent_processor.process_conversational_intent(
                intent,
                user_message, 
                conversation_history, 
                slots,
                user_data
            )
        elif intent in financial_tips_intents:
            return self.intent_processor.process_financial_tips_intent(
                intent,
                user_message, 
                conversation_history, 
                slots,
                user_data
            )
        elif intent in expense_report_intents:
            return self.intent_processor.process_expense_report_intent(
                intent,
                user_message,
                conversation_history, 
                slots,
                user_data
            )
        elif intent in beneficiaries_intents:
            return self.intent_processor.process_beneficiaries_intent(
                intent,
                user_message,
                conversation_history,
                slots,
                user_data
            )
        else:
            # Fallback for unhandled intents
            return self.response_formatter.format_response(intent, "error", message="Intent not supported")
        
    def generate_receipt_after_payment(self, transaction_id: str, user_id: str, intent: str,
                                  amount: Decimal, status: str, sender: str, receiver: str,
                                  sender_name: str, receiver_name: str,
                                  sender_provider: str, receiver_provider: str,
                                  payment_method: str, timestamp: datetime) -> str:
        """Generate receipt image and save to Azure Blob Storage"""
        try:

            logger.info(f"[RECEIPT] Generating receipt for transaction: {transaction_id}")
            
            # Map intent to transaction type for receipt
            transaction_type_map = {
                "buy_airtime": "Airtime Purchase",
                "send_money": "Money Transfer", 
                "pay_bill": "Bill Payment",
                "get_loan": "Loan Disbursement"
            }
            
            # Prepare receipt data
            receipt_data = {
                'transaction_id': transaction_id,
                'user_id': user_id,
                'transaction_type': transaction_type_map.get(intent, "Payment"),
                'amount': str(amount),
                'status': status,
                'sender_account': sender,
                'receiver_account': receiver,
                'sender_name': sender_name,
                'receiver_name': receiver_name,
                'sender_provider': sender_provider,
                'receiver_provider': receiver_provider,
                'payment_method': payment_method,
                'timestamp': timestamp
            }
            
            # Add loan-specific fields if it's a loan transaction
            if intent == "get_loan":
                receipt_data.update({
                    'interest_rate': '5',  # You might want to get this from your data
                    'loan_period': '30 days',  # Default or from slots
                    'expected_pay_date': (timestamp + timedelta(days=30)).strftime("%b %d, %Y"),
                    'penalty_rate': '2'  # Default penalty rate
                })
            
            # Generate receipt image
            receipt_generator = ReceiptGenerator()
            base64_data_url = receipt_generator.generate_receipt_image(receipt_data)
            
            # Extract base64 data from data URL
            base64_data = base64_data_url.split(',')[1]
            image_data = base64.b64decode(base64_data)
            
            # Create file-like object from image data
            image_file = io.BytesIO(image_data)
            
            # Generate filename with date and user ID
            date_str = timestamp.strftime("%Y%m%d_%H%M%S")
            filename = f"receipts/{date_str}_{user_id}_{transaction_id}.png"
            
            # Upload to Azure Blob Storage
            storage_service = StorageService()
            blob_url = storage_service.upload_file(
                file_obj=image_file,
                file_name=filename,
                content_type="image/png"
            )
            
            logger.info(f"[RECEIPT] Receipt saved to Azure Storage: {blob_url}")
            return blob_url

        except Exception as e:
            logger.error(f"[RECEIPT] Error generating/saving receipt: {str(e)}")
            # Return a fallback or empty string if receipt generation fails
            return ""

    def _get_processing_message(self, intent: str, slots: Dict, result: Any) -> str:
        """Generate message indicating payment is being processed"""
        if intent == "send_money":
            receiver_name = slots.get('receiver_name', 'Recipient')
            recipient_phone = slots.get('recipient')
            receiver_provider = slots.get('receiver_provider', 'the recipient provider')
            return f"Your Transfer to {recipient_phone} ({receiver_name}) on {receiver_provider} is being processed. Transaction ID: {result.transactionId}"

        processing_messages = {
            "buy_airtime": f"Airtime purchase of GHS {slots.get('amount')} for {slots.get('phone_number')} is being processed. Transaction ID: {result.transactionId}",
            "pay_bill": f"Bill payment of GHS {slots.get('amount')} is being processed. Transaction ID: {result.transactionId}",
            "get_loan": f"Loan application for GHS {slots.get('loan_amount')} is being processed. Transaction ID: {result.transactionId}"
        }
        return processing_messages.get(intent, "Your payment is being processed. Transaction ID: {result.transactionId}")

    def _get_success_message(self, intent: str, slots: Dict, result: Any) -> str:
        """Generate success message based on intent"""
        if intent == "send_money":
            receiver_name = slots.get('receiver_name', 'Recipient')
            recipient_phone = slots.get('recipient')
            receiver_provider = slots.get('receiver_provider', 'the recipient provider')
            return f"Your Transfer to {recipient_phone} ({receiver_name}) on {receiver_provider} has been successfully completed"

        success_messages = {
            "buy_airtime": f"✅ Airtime of GHS {slots.get('amount')} sent to {slots.get('phone_number')}. Transaction ID: {result.transactionId}",
            "pay_bill": f"✅ Bill payment of GHS {slots.get('amount')} processed. Transaction ID: {result.transactionId}",
            "get_loan": f"✅ Loan of GHS {slots.get('loan_amount')} application submitted. Transaction ID: {result.transactionId}"
        }
        return success_messages.get(intent, "Payment processed successfully")

    def _get_user_data(self, user_id: str) -> Optional[Dict]:
        """Fetch user data for personalized processing"""
        try:
            db = SessionLocal()
            user_service = UserService(db)
            
            # Get user by ID (assuming user_id is the same as email or you have a method to get by user_id)
            user = user_service.get_user_by_phone(user_id)
            
            if user:
                # Convert user data to dictionary format expected by RAG manager
                user_data = {
                    "user_id": user.id,
                    "username": user.username,
                    "email": user.email,
                    "first_name": user.first_name,
                    "last_name": user.last_name,
                    "is_active": user.is_active,
                    "created_at": user.created_at.isoformat() if user.created_at else None,
                    # Add any additional user fields you need
                }
                
                # You can also fetch additional user-specific data here:
                # - Transaction history
                # - Spending patterns  
                # - Financial goals
                # - Account balances
                # - Subscription status
                
                return user_data
            return None
            
        except Exception as e:
            logger.error(f"Error fetching user data for {user_id}: {e}")
            return None
        finally:
            db.close()

    def _process_media_inputs(
        self,
        user_id: str,
        image_media_id: Optional[str] = None,
        image_url: Optional[str] = None,
        audio_media_id: Optional[str] = None,
        audio_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Process multimodal inputs (images and audio)
        
        Args:
            user_id: User identifier
            image_media_id: WhatsApp media ID for image
            image_url: Direct URL to image
            audio_media_id: WhatsApp media ID for audio
            audio_url: Direct URL to audio
            
        Returns:
            Dictionary with processed media context
        """
        from core.nlu.service.media_processor import MediaProcessor
        
        media_processor = MediaProcessor()
        media_context = {}
        
        # Process image if provided
        if image_media_id or image_url:
            try:
                logger.info(f"[MEDIA_PROCESSING] Processing image for user {user_id}")
                image_data = media_processor.process_image(
                    media_id=image_media_id or "",
                    media_url=image_url
                )
                
                if image_data:
                    media_context["image_base64"] = image_data.get("base64")
                    media_context["image_url"] = image_data.get("url")
                    media_context["image_mime_type"] = image_data.get("mime_type")
                    logger.info(f"[MEDIA_PROCESSING] Image processed successfully")
                else:
                    logger.warning(f"[MEDIA_PROCESSING] Failed to process image")
                    
            except Exception as e:
                logger.error(f"[MEDIA_PROCESSING] Error processing image: {e}")
        
        # Process audio if provided
        if audio_media_id or audio_url:
            try:
                logger.info(f"[MEDIA_PROCESSING] Processing audio for user {user_id}")
                audio_data = media_processor.process_audio(
                    media_id=audio_media_id or "",
                    media_url=audio_url
                )
                
                if audio_data:
                    media_context["audio_bytes"] = audio_data.get("bytes")
                    media_context["audio_filename"] = audio_data.get("filename")
                    media_context["audio_mime_type"] = audio_data.get("mime_type")
                    logger.info(f"[MEDIA_PROCESSING] Audio processed successfully: {audio_data.get('size')} bytes")
                else:
                    logger.warning(f"[MEDIA_PROCESSING] Failed to process audio")
                    
            except Exception as e:
                logger.error(f"[MEDIA_PROCESSING] Error processing audio: {e}")
        
        return media_context
