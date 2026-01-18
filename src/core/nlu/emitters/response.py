from typing import Dict, Any

class ResponseFormatter:
    @staticmethod
    def format_response(intent: str, message_type: str, **kwargs) -> str:
        """Format responses in a friendly financial assistant style"""
        
        if message_type == "greeting":
            return "💳 Hello! I'm Lebe, your financial assistant. How can I help you today? I can help you send money, buy airtime, pay bills, and more!"
        
        elif message_type == "missing_slots":
            return f"💬 {kwargs.get('message', 'I need a few more details to help you:')} {kwargs.get('prompt', '')}"
        
        elif message_type == "confirm_action":
            action_descriptions = {
                "send_money": f"send GHS {kwargs.get('amount')} to {kwargs.get('recipient')}",
                "buy_airtime": f"buy GHS {kwargs.get('amount')} airtime for {kwargs.get('phone_number')}",
                "buy_data": f"buy {kwargs.get('data_plan')} data for {kwargs.get('phone_number')}",
                "pay_bill": f"pay {kwargs.get('bill_type')} bill of GHS {kwargs.get('amount')}",
                "get_loan": f"apply for a GHS {kwargs.get('loan_amount')} loan"
            }
            action_desc = action_descriptions.get(intent, "complete this transaction")
            return f"🔒 Please enter your 5-digit PIN to confirm {action_desc}."
        
        elif message_type == "success":
            return f"✅ {kwargs.get('message', 'Action completed successfully!')}"
        
        elif message_type == "error":
            return f"Lebe encountered an issue. Please try again later."
        
        elif message_type == "invalid_pin":
            return "🔒 Invalid PIN. Please try again."

        elif message_type == "payment_confirmation":
            return kwargs.get('message', 'Please confirm this transaction.')

        elif message_type == "payment_cancelled":
            return "❌ Transaction cancelled. Your account has not been charged."

        elif message_type == "confirm_again":
            return f"❓ {kwargs.get('message', 'Please reply yes or no.')}"

        elif message_type == "processing":
            return kwargs.get('message', 'Your payment is being processed.')

        else:
            return f"💬 {kwargs.get('message', '')}"