from core.histories.service.historyservice import HistoryService
import openai
from typing import Dict, Any, Optional
from datetime import datetime
from core.auth.service.authservice import AuthService
from core.nlu.service.intents import IntentDetector
from core.nlu.service.slot_manager import SlotManager
from core.nlu.service.conversation_manager import ConversationManager
from core.nlu.service.security import SecurityManager
from core.nlu.emitters.response import ResponseFormatter
from utilities.dbconfig import SessionLocal
from core.auth.dto.request.user_create import UserCreateRequest

class LebeNLUSystem:
    def __init__(self):
        self.intent_detector = IntentDetector()
        self.slot_manager = SlotManager()
        self.conversation_manager = ConversationManager()
        self.security_manager = SecurityManager()
        self.response_formatter = ResponseFormatter()
    
    def process_message(self, user_id: str, user_message: str, user_subscription_status: str) -> str:
        """Main method to process user messages"""
        
        # Get conversation state
        state = self.conversation_manager.get_conversation_state(user_id)
        
        # Add user message to history
        self.conversation_manager.update_conversation_history(user_id, "user", user_message)
        
        # Check if waiting for PIN
        if state.waiting_for_pin:
            return self._handle_pin_verification(user_id, user_message)
        
        # Detect intent and extract slots
        intent, extracted_slots, missing_slots = self.intent_detector.detect_intent_and_slots(
            user_message, state.conversation_history
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
            # All slots collected, request PIN if needed
            if self.security_manager.is_pin_required(intent):
                state.waiting_for_pin = True
                state.pending_action = {
                    "intent": intent,
                    "slots": state.collected_slots.copy()
                }
                response = self.response_formatter.format_response(
                    intent, "confirm_action", **state.collected_slots
                )
            else:
                # Execute non-secure action directly
                response = self._execute_action(user_id, intent, state.collected_slots)
        
        # Add assistant response to history
        self.conversation_manager.update_conversation_history(user_id, "assistant", response)
        
        return response
    
    def _handle_pin_verification(self, user_id: str, pin_input: str) -> str:
        """Handle PIN verification for pending actions"""
        state = self.conversation_manager.get_conversation_state(user_id)
        
        if self.security_manager.verify_pin(user_id, pin_input):
            # PIN verified, execute action
            response = self._execute_action(
                user_id, 
                state.pending_action["intent"], 
                state.pending_action["slots"]
            )
            # Reset conversation state
            self.conversation_manager.reset_conversation_state(user_id)
        else:
            # Invalid PIN
            response = self.response_formatter.format_response("", "invalid_pin")
            # Keep waiting for PIN
        
        self.conversation_manager.update_conversation_history(user_id, "assistant", response)
        return response
    
    def _execute_action(self, user_id: str, intent: str, slots: Dict) -> str:
        """Execute the actual financial action through payment service"""
        try:
            print(f"Executing action for intent: {intent} with slots: {slots}")

            # Payment intents that require Orchard API
            payment_intents = ["buy_airtime", "send_money", "pay_bill", "get_loan"]

            if intent in payment_intents:
                return self._process_payment_intent(user_id, intent, slots)
            else:
                return self._process_non_payment_intent(user_id, intent, slots)

        except Exception as e:
            print(f"Error executing action: {e}")
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

        db = SessionLocal()
        try:
            # Map network string to Network enum
            network_map = {
                "MTN": Network.MTN,
                "Vodafone": Network.VODAFONE,
                "VOD": Network.VODAFONE,
                "AirtelTigo": Network.AIRTELTIGO,
                "AIR": Network.AIRTELTIGO
            }

            # Create PaymentDto based on intent
            if intent == "buy_airtime":
                payment_dto = PaymentDto(
                    amount_paid=Decimal(slots.get('amount', '0')),
                    phone_number=slots.get('phone_number'),
                    network=network_map.get(slots.get('network', 'MTN'), Network.MTN),
                    payment_method=PaymentMethod.MOBILE_MONEY,
                    service_name="Airtime Top-Up",
                    transaction_id=str(UniqueIdGenerator.generate())
                )

            elif intent == "send_money":
                payment_dto = PaymentDto(
                    amount_paid=Decimal(slots.get('amount', '0')),
                    phone_number=slots.get('recipient'),
                    network=network_map.get(slots.get('network', 'MTN'), Network.MTN),
                    payment_method=PaymentMethod.MOBILE_MONEY,
                    customer_name=slots.get('recipient_name', 'Unknown'),
                    service_name=f"Money Transfer to {slots.get('recipient')}",
                    transaction_id=str(UniqueIdGenerator.generate())
                )

            elif intent == "pay_bill":
                payment_dto = PaymentDto(
                    amount_paid=Decimal(slots.get('amount', '0')),
                    phone_number=user_id,  # Use user's phone
                    network=network_map.get(slots.get('network', 'MTN'), Network.MTN),
                    payment_method=PaymentMethod.MOBILE_MONEY,
                    service_name=f"Bill Payment: {slots.get('bill_type')}",
                    transaction_id=str(UniqueIdGenerator.generate())
                )

            elif intent == "get_loan":
                payment_dto = PaymentDto(
                    amount_paid=Decimal(slots.get('loan_amount', '0')),
                    phone_number=user_id,  # User's phone for payout
                    network=network_map.get(slots.get('network', 'MTN'), Network.MTN),
                    payment_method=PaymentMethod.MOBILE_MONEY,
                    service_name="Loan Disbursement",
                    transaction_id=str(UniqueIdGenerator.generate())
                )
            else:
                return self.response_formatter.format_response(intent, "error", message=f"Unknown payment intent: {intent}")

            # Process payment through PaymentService
            payment_service = PaymentService(db)
            result = payment_service.make_payment(payment_dto, intent)

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
                    description=f"{intent.replace('_', ' ').title()} - Transaction ID: {payment_dto.transaction_id}",
                    metadata={"slots": slots, "payment_status": result.status}
                )

            # Return response based on payment result
            if result.status == PaymentStatus.PENDING:
                message = self._get_success_message(intent, slots, result)
                return self.response_formatter.format_response(intent, "success", message=message)
            elif result.status == PaymentStatus.SUCCESS:
                message = self._get_success_message(intent, slots, result)
                return self.response_formatter.format_response(intent, "success", message=message)
            else:
                error_msg = result.response_description or "Payment processing failed"
                return self.response_formatter.format_response(intent, "error", message=error_msg)

        finally:
            db.close()

    def _process_non_payment_intent(self, user_id: str, intent: str, slots: Dict) -> str:
        """Process non-payment intents"""
        success_messages = {
            "create_new_account": "Your account has been created successfully!",
            "check_balance": "Your current balance is GHS 1,234.56",
            "track_expenses": "Here's your spending summary for this month...",
            "set_budget": f"Budget of GHS {slots.get('amount')} set for {slots.get('category')}"
        }

        message = success_messages.get(intent, "Action completed successfully")
        return self.response_formatter.format_response(intent, "success", message=message)

    def _get_success_message(self, intent: str, slots: Dict, result: Any) -> str:
        """Generate success message based on intent"""
        success_messages = {
            "buy_airtime": f"✅ Airtime of GHS {slots.get('amount')} sent to {slots.get('phone_number')}. Transaction ID: {result.transaction_id}",
            "send_money": f"✅ Successfully sent GHS {slots.get('amount')} to {slots.get('recipient')}. Transaction ID: {result.transaction_id}",
            "pay_bill": f"✅ Bill payment of GHS {slots.get('amount')} processed. Transaction ID: {result.transaction_id}",
            "get_loan": f"✅ Loan of GHS {slots.get('loan_amount')} application submitted. Transaction ID: {result.transaction_id}"
        }
        return success_messages.get(intent, "Payment processed successfully")
    
    def initialize_user(self, user_id: str, pin: str) -> bool:
        """Initialize user with PIN during onboarding"""
        return self.security_manager.set_user_pin(user_id, pin)

# Usage example
# if __name__ == "__main__":
#     nlu_system = LebeNLUSystem()
    
#     # Simulate user onboarding
#     nlu_system.initialize_user("user123", "1234")
    
#     # Simulate conversation
#     test_messages = [
#         "Hello",
#         "I want to send money",
#         "Send 50 cedis to 0234567890",
#         "1234"  # PIN
#     ]
    
#     user_id = "user123"
#     for message in test_messages:
#         print(f"User: {message}")
#         response = nlu_system.process_message(user_id, message)
#         print(f"Lebe: {response}\n")