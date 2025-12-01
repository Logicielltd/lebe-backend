
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
    
    def process_message(self, user_id: str, user_message: str, user_subscription_status: str) -> str:
        """Main method to process user messages"""

        # Get conversation state
        state = self.conversation_manager.get_conversation_state(user_id)

        # Add user message to history
        self.conversation_manager.update_conversation_history(user_id, "user", user_message)

        # Check if waiting for payment confirmation
        if state.waiting_for_payment_confirmation:
            return self._handle_payment_confirmation(user_id, user_message)

        # Check if waiting for PIN
        if state.waiting_for_pin:
            return self._handle_pin_verification(user_id, user_message)
        
        # Detect intent and extract slots
        intent, extracted_slots, missing_slots = self.intent_detector.detect_intent_and_slots(
            user_message, state.conversation_history, state.current_intent
        )

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

    def _handle_payment_confirmation(self, user_id: str, user_response: str) -> str:
        """Handle user's yes/no response for payment confirmation"""
        state = self.conversation_manager.get_conversation_state(user_id)

        # Check if pending payment exists
        if not state.pending_payment_dto:
            error_response = self.response_formatter.format_response("", "error", message="No pending payment found. Please start over.")
            self.conversation_manager.update_conversation_history(user_id, "assistant", error_response)
            state.waiting_for_payment_confirmation = False
            self.conversation_manager._save_conversation_state(state)
            return error_response

        # Check user's response (yes/no/confirm/proceed/etc.)
        user_response_lower = user_response.lower().strip()
        confirmation_keywords = ["yes", "y", "confirm", "ok", "okay", "proceed", "go ahead"]
        rejection_keywords = ["no", "n", "cancel", "don't", "dont", "stop"]

        if any(keyword in user_response_lower for keyword in confirmation_keywords):
            # User confirmed payment
            logger.info(f"[PAYMENT_CONFIRMATION] User {user_id} confirmed payment")
            intent = state.current_intent
            slots = state.collected_slots

            # Execute the payment
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
        from core.payments.dto.paymentdto import PaymentDto
        from core.payments.model.paymentmethod import PaymentMethod
        from core.payments.model.paymentstatus import PaymentStatus
        from core.payments.model.paynetwork import Network
        from core.payments.service.paymentservice import PaymentService
        from utilities.uniqueidgenerator import UniqueIdGenerator
        from decimal import Decimal

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
                payment_dto = PaymentDto(
                    senderPhone=user_id,  # User initiating the payment
                    receiverPhone=slots.get('recipient'),  # Recipient gets the money
                    network=network_map.get(slots.get('network', 'MTN'), Network.MTN),
                    paymentMethod=PaymentMethod.MOBILE_MONEY,
                    customerName=slots.get('recipient_name', 'Unknown'),
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

                # Try to match bill_type to network, default to GOT if unknown
                selected_network = Network.GOT
                for key, network in bill_network_map.items():
                    if key in bill_type.lower():
                        selected_network = network
                        break

                payment_dto = PaymentDto(
                    senderPhone=user_id,  # User initiating the payment (paying the bill)
                    receiverPhone=account_number,  # Smart card/account number where bill is paid
                    network=selected_network,  # Utility provider (GoTV, DStv, ECG, etc.)
                    paymentMethod=PaymentMethod.MOBILE_MONEY,
                    serviceName=f"Bill Payment: {bill_type}",
                    amountPaid=Decimal(slots.get('amount', '0')),
                    transactionId=str(UniqueIdGenerator.generate())
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

            # For send_money, perform account inquiry and wait for confirmation
            if intent == "send_money":
                logger.info(f"[ACCOUNT_INQUIRY] Performing account inquiry for send_money")
                try:
                    payment_service = PaymentService(db)
                    recipient_phone = slots.get('recipient')
                    recipient_network = network_map.get(slots.get('network', 'MTN'), Network.MTN)

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

                        # Create confirmation message
                        confirmation_msg = f"Confirm: Send GHS {amount} to {account_name} ({recipient_phone})?\nPlease reply 'yes' to confirm or 'no' to cancel."

                        # Store payment info and set waiting for confirmation
                        state = self.conversation_manager.get_conversation_state(user_id)
                        state.waiting_for_payment_confirmation = True
                        state.pending_payment_dto = {
                            "account_name": account_name,
                            "recipient_phone": recipient_phone,
                            "amount": amount
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
                return self.response_formatter.format_response(intent, "processing", message=message)
            elif result.status == PaymentStatus.SUCCESS:
                message = self._get_success_message(intent, slots, result)
                return self.response_formatter.format_response(intent, "success", message=message)
            else:
                error_msg = result.responseDescription or "Payment processing failed"
                return self.response_formatter.format_response(intent, "error", message=error_msg)

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
                'sender': sender,
                'receiver': receiver,
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
        processing_messages = {
            "buy_airtime": f"Payment of GHS {slots.get('amount')} for airtime to {slots.get('phone_number')} is being processed. Transaction ID: {result.transactionId}",
            "send_money": f"Payment of GHS {slots.get('amount')} to {slots.get('recipient')} is being processed. Transaction ID: {result.transactionId}",
            "pay_bill": f"Bill payment of GHS {slots.get('amount')} is being processed. Transaction ID: {result.transactionId}",
            "get_loan": f"Loan application for GHS {slots.get('loan_amount')} is being processed. Transaction ID: {result.transactionId}"
        }
        return processing_messages.get(intent, "Payment is being processed. Transaction ID: {result.transactionId}")

    def _get_success_message(self, intent: str, slots: Dict, result: Any) -> str:
        """Generate success message based on intent"""
        success_messages = {
            "buy_airtime": f"✅ Airtime of GHS {slots.get('amount')} sent to {slots.get('phone_number')}. Transaction ID: {result.transactionId}",
            "send_money": f"✅ Successfully sent GHS {slots.get('amount')} to {slots.get('recipient')}. Transaction ID: {result.transactionId}",
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