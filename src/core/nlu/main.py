from typing import Any, Dict
import logging

from core.histories.service.historyservice import HistoryService
from core.nlu.emitters.response import ResponseFormatter
from core.nlu.service.conversation_manager import ConversationManager
from core.nlu.service.intents import IntentDetector
from core.nlu.service.security import SecurityManager
from core.nlu.service.slot_manager import SlotManager
from utilities.dbconfig import SessionLocal

logger = logging.getLogger(__name__)


class LebeNLUSystem:
    """NLU system for processing user messages and routing to appropriate handlers."""

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
        intent, extracted_slots, _ = self.intent_detector.detect_intent_and_slots(
            user_message, state.conversation_history
        )

        # Validate and merge slots
        validated_slots = self.slot_manager.validate_slots(intent, extracted_slots)
        state.collected_slots.update(validated_slots)
        state.current_intent = intent

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
            # All slots collected, execute action directly
            # TODO: Re-enable PIN verification after payment flow is working
            response = self._execute_action(user_id, intent, state.collected_slots)

        # Add assistant response to history
        self.conversation_manager.update_conversation_history(user_id, "assistant", response)

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

            msg = f"PIN verified for user {user_id}. Executing pending action: "
            msg += f"intent={pending_intent}, slots={pending_slots}"
            print(msg)

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

        self.conversation_manager.update_conversation_history(user_id, "assistant", response)
        return response
    
    def _execute_action(self, user_id: str, intent: str, slots: Dict) -> str:
        """Execute the actual financial action through payment service"""
        try:
            print(f"[EXECUTE_ACTION] User {user_id}: intent={intent}, slots={slots}")

            # Payment intents that require Orchard API
            payment_intents = ["buy_airtime", "send_money", "pay_bill", "get_loan"]

            # Beneficiary intents
            beneficiary_intents = ["add_beneficiary", "view_beneficiaries", "delete_beneficiary"]

            if intent in payment_intents:
                msg = f"[EXECUTE_ACTION] Routing to payment processor for intent: {intent}"
                print(msg)
                return self._process_payment_intent(user_id, intent, slots)

            if intent in beneficiary_intents:
                msg = f"[EXECUTE_ACTION] Routing to beneficiary processor for intent: {intent}"
                print(msg)
                return self._process_beneficiary_intent(user_id, intent, slots)

            msg = f"[EXECUTE_ACTION] Routing to non-payment processor for intent: {intent}"
            print(msg)
            return self._process_non_payment_intent(user_id, intent, slots)

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
                    phoneNumber=slots.get('phone_number'),
                    network=network_map.get(slots.get('network', 'MTN'), Network.MTN),
                    paymentMethod=PaymentMethod.MOBILE_MONEY,
                    serviceName="Airtime Top-Up",
                    amountPaid=Decimal(slots.get('amount', '0')),
                    transactionId=str(UniqueIdGenerator.generate())
                )

            elif intent == "send_money":
                payment_dto = PaymentDto(
                    phoneNumber=slots.get('recipient'),
                    network=network_map.get(slots.get('network', 'MTN'), Network.MTN),
                    paymentMethod=PaymentMethod.MOBILE_MONEY,
                    customerName=slots.get('recipient_name', 'Unknown'),
                    serviceName=f"Money Transfer to {slots.get('recipient')}",
                    amountPaid=Decimal(slots.get('amount', '0')),
                    transactionId=str(UniqueIdGenerator.generate())
                )

            elif intent == "pay_bill":
                payment_dto = PaymentDto(
                    phoneNumber=user_id,  # Use user's phone
                    network=network_map.get(slots.get('network', 'MTN'), Network.MTN),
                    paymentMethod=PaymentMethod.MOBILE_MONEY,
                    serviceName=f"Bill Payment: {slots.get('bill_type')}",
                    amountPaid=Decimal(slots.get('amount', '0')),
                    transactionId=str(UniqueIdGenerator.generate())
                )

            elif intent == "get_loan":
                payment_dto = PaymentDto(
                    phoneNumber=user_id,  # User's phone for payout
                    network=network_map.get(slots.get('network', 'MTN'), Network.MTN),
                    paymentMethod=PaymentMethod.MOBILE_MONEY,
                    serviceName="Loan Disbursement",
                    amountPaid=Decimal(slots.get('loan_amount', '0')),
                    transactionId=str(UniqueIdGenerator.generate())
                )
            else:
                return self.response_formatter.format_response(intent, "error", message=f"Unknown payment intent: {intent}")

            print(f"[PAYMENT_INTENT] PaymentDto created successfully")
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
            if result.status == PaymentStatus.PENDING:
                # Payment request accepted by gateway, awaiting callback confirmation
                message = self._get_pending_message(intent, slots, result)
                return self.response_formatter.format_response(intent, "pending", message=message)
            elif result.status == PaymentStatus.SUCCESS:
                # Payment confirmed successful
                message = self._get_success_message(intent, slots, result)
                return self.response_formatter.format_response(intent, "success", message=message)
            else:
                error_msg = result.responseDescription or "Payment processing failed"
                return self.response_formatter.format_response(intent, "error", message=error_msg)

        finally:
            db.close()

    def _process_non_payment_intent(self, _user_id: str, intent: str, slots: Dict) -> str:
        """Process non-payment intents"""
        success_messages = {
            "create_new_account": "Your account has been created successfully!",
            "check_balance": "Your current balance is GHS 1,234.56",
            "track_expenses": "Here's your spending summary for this month...",
            "set_budget": f"Budget of GHS {slots.get('amount')} for {slots.get('category')}"
        }

        message = success_messages.get(intent, "Action completed successfully")
        return self.response_formatter.format_response(intent, "success", message=message)

    def _get_pending_message(self, intent: str, slots: Dict, result: Any) -> str:
        """Generate pending message for payment awaiting confirmation"""
        amount = slots.get('amount')
        phone = slots.get('phone_number')
        recipient = slots.get('recipient')
        loan_amt = slots.get('loan_amount')
        txn_id = result.transactionId

        pending_messages = {
            "buy_airtime": (
                f"⏳ Your airtime request of GHS {amount} to {phone} "
                f"is being processed. Transaction ID: {txn_id}"
            ),
            "send_money": (
                f"⏳ Your money transfer of GHS {amount} to {recipient} "
                f"is being processed. Transaction ID: {txn_id}"
            ),
            "pay_bill": (
                f"⏳ Your bill payment of GHS {amount} is being processed. "
                f"Transaction ID: {txn_id}"
            ),
            "get_loan": (
                f"⏳ Your loan application for GHS {loan_amt} is being processed. "
                f"Transaction ID: {txn_id}"
            )
        }
        default = "Payment is being processed. Please wait for confirmation."
        return pending_messages.get(intent, default)

    def _get_success_message(self, intent: str, slots: Dict, result: Any) -> str:
        """Generate success message based on intent"""
        amount = slots.get('amount')
        phone = slots.get('phone_number')
        recipient = slots.get('recipient')
        loan_amt = slots.get('loan_amount')
        txn_id = result.transactionId

        success_messages = {
            "buy_airtime": (
                f"✅ Airtime of GHS {amount} sent to {phone}. "
                f"Transaction ID: {txn_id}"
            ),
            "send_money": (
                f"✅ Successfully sent GHS {amount} to {recipient}. "
                f"Transaction ID: {txn_id}"
            ),
            "pay_bill": (
                f"✅ Bill payment of GHS {amount} processed. "
                f"Transaction ID: {txn_id}"
            ),
            "get_loan": (
                f"✅ Loan of GHS {loan_amt} application submitted. "
                f"Transaction ID: {txn_id}"
            )
        }
        return success_messages.get(intent, "Payment processed successfully")

    def _process_beneficiary_intent(
        self, user_id: str, intent: str, slots: Dict
    ) -> str:
        """Process beneficiary management intents"""
        from core.beneficiaries.service.beneficiary_service import BeneficiaryService

        db = SessionLocal()
        try:
            beneficiary_service = BeneficiaryService(db)

            print(f"[BENEFICIARY_INTENT] Processing intent: {intent}")

            if intent == "add_beneficiary":
                return self._handle_add_beneficiary(
                    user_id, slots, beneficiary_service
                )

            if intent == "view_beneficiaries":
                return self._handle_view_beneficiaries(user_id, beneficiary_service)

            if intent == "delete_beneficiary":
                return self._handle_delete_beneficiary(
                    user_id, slots, beneficiary_service
                )

            msg = "Unknown beneficiary action"
            return self.response_formatter.format_response(
                intent, "error", message=msg
            )

        finally:
            db.close()

    def _handle_add_beneficiary(self, user_id: str, slots: Dict, beneficiary_service) -> str:
        """Handle adding a new beneficiary"""
        print(f"[BENEFICIARY_INTENT] Adding beneficiary with slots: {slots}")

        name = slots.get('beneficiary_name')
        customer_number = slots.get('customer_number')
        network = slots.get('network')
        bank_code = slots.get('bank_code')

        if not name or not customer_number:
            return self.response_formatter.format_response(
                "add_beneficiary", "error",
                message="Please provide both beneficiary name and phone/account number"
            )

        success, beneficiary, message = beneficiary_service.add_beneficiary(
            user_id=user_id,
            name=name,
            customer_number=customer_number,
            network=network,
            bank_code=bank_code
        )

        if success:
            print(f"[BENEFICIARY_INTENT] Beneficiary added successfully: {beneficiary.id}")
            return self.response_formatter.format_response(
                "add_beneficiary", "success",
                message=f"✅ {message}"
            )

        print(f"[BENEFICIARY_INTENT] Failed to add beneficiary: {message}")
        return self.response_formatter.format_response(
            "add_beneficiary", "error",
            message=f"Could not save beneficiary: {message}"
        )

    def _handle_view_beneficiaries(self, user_id: str, beneficiary_service) -> str:
        """Handle viewing beneficiaries"""
        print(f"[BENEFICIARY_INTENT] Fetching beneficiaries for user: {user_id}")

        beneficiaries = beneficiary_service.get_beneficiaries(user_id)
        beneficiary_list = beneficiary_service.format_beneficiary_list(beneficiaries)

        print(f"[BENEFICIARY_INTENT] Found {len(beneficiaries)} beneficiaries")
        return self.response_formatter.format_response(
            "view_beneficiaries", "success",
            message=beneficiary_list
        )

    def _handle_delete_beneficiary(self, user_id: str, slots: Dict, beneficiary_service) -> str:
        """Handle deleting a beneficiary"""
        beneficiary_name = slots.get('beneficiary_name')

        if not beneficiary_name:
            return self.response_formatter.format_response(
                "delete_beneficiary", "error",
                message="Please provide the name of the beneficiary to remove"
            )

        print(f"[BENEFICIARY_INTENT] Deleting beneficiary: {beneficiary_name}")

        # Find beneficiary by name
        beneficiaries = beneficiary_service.get_beneficiaries(user_id)
        matching_beneficiary = next(
            (b for b in beneficiaries if b.name.lower() == beneficiary_name.lower()),
            None
        )

        if not matching_beneficiary:
            return self.response_formatter.format_response(
                "delete_beneficiary", "error",
                message=f"Beneficiary '{beneficiary_name}' not found"
            )

        success, message = beneficiary_service.delete_beneficiary(
            matching_beneficiary.id, user_id
        )

        if success:
            msg = f"[BENEFICIARY_INTENT] Beneficiary deleted: {matching_beneficiary.id}"
            print(msg)
            return self.response_formatter.format_response(
                "delete_beneficiary", "success",
                message=f"✅ {message}"
            )

        msg = f"[BENEFICIARY_INTENT] Failed to delete beneficiary: {message}"
        print(msg)
        return self.response_formatter.format_response(
            "delete_beneficiary", "error",
            message=f"Could not remove beneficiary: {message}"
        )

    def initialize_user(self, user_id: str, pin: str) -> bool:
        """Initialize user with PIN during onboarding"""
        return self.security_manager.set_user_pin(user_id, pin)

