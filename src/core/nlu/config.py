import os
from typing import Dict, List, Any

# API Configuration
OPENAI_API_KEY = "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"
MODEL = "gpt-4"  # or "gpt-3.5-turbo" for cost efficiency

# Local Model Configuration
MODEL_CONFIG = {
    "model_name": "microsoft/DialoGPT-large",  # or "google/flan-t5-base"
    "local_files_only": False,  # Set to True after first download
    "device": "cpu",  # or "cuda" if you have GPU
    "max_length": 512,
    "temperature": 0.1,
    "do_sample": True
}

# Intent Configuration
INTENTS = {
    # Greetings need an intent slot to continue the flow
    "greeting": {
        "description": "Greet the user",
        "slots": [],
        "required_slots": []
    },
    "send_money": {
        "description": "Send money to another person",
        "slots": ["recipient", "amount", "network", "reason"],
        "required_slots": ["recipient", "amount"]
    },
    "buy_airtime": {
        "description": "Purchase airtime credit",
        "slots": ["phone_number", "amount", "network"],
        "required_slots": ["phone_number", "amount"]
    },
    "buy_data": {
        "description": "Purchase data bundle",
        "slots": ["phone_number", "data_plan", "amount", "network"],
        "required_slots": ["phone_number", "data_plan"]
    },
    "pay_bill": {
        "description": "Pay utility bills",
        "slots": ["bill_type", "account_number", "amount", "provider"],
        "required_slots": ["bill_type", "account_number", "amount"]
    },
    "check_balance": {
        "description": "Check account balance",
        "slots": [],
        "required_slots": []
    },
    "get_loan": {
        "description": "Apply for a loan",
        "slots": ["loan_amount", "duration", "purpose"],
        "required_slots": ["loan_amount"]
    },
    "track_expenses": {
        "description": "View expense tracking",
        "slots": ["time_period", "category"],
        "required_slots": []
    },
    "set_budget": {
        "description": "Set spending budget",
        "slots": ["category", "amount", "period"],
        "required_slots": ["category", "amount"]
    }
}

# System Prompts
SYSTEM_PROMPT = """
You are Lebe, a friendly financial assistant for users in Ghana. You help with:
- Sending money via Mobile Money (MoMo)
- Buying airtime and data bundles
- Paying bills (utilities, TV subscriptions, etc.)
- Expense tracking and budgeting
- Loan applications
- Financial advice and insights

Always be conversational, helpful, and clear. Ask for missing information politely.
If unsure, ask clarifying questions.

Current user context: {context}
Missing slots: {missing_slots}
"""

# Response Templates
RESPONSE_TEMPLATES = {
    "missing_slots": "I'd be happy to help you {intent}. I just need a few more details: {missing_slots}",
    "confirm_action": "Great! I'm ready to {intent}. Please confirm with your PIN to proceed.",
    "error": "I apologize, but I'm having trouble processing your request. Please try again.",
    "success": "Your {intent} has been processed successfully! {details}"
}