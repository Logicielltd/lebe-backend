import os
from typing import Dict, List, Any
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# API Configuration
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY environment variable is not set")

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
    "create_new_account": {
        "description": "Handle new account creation",
        "slots": ["first_name", "last_name", "phone", "email", "pin"],
        "required_slots": ["first_name", "last_name", "phone", "email", "pin"]
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
    },
    # Beneficiary management intents
    "add_beneficiary": {
        "description": "Save a new payment recipient (beneficiary)",
        "slots": ["beneficiary_name", "customer_number", "network", "bank_code"],
        "required_slots": ["beneficiary_name", "customer_number"]
    },
    "view_beneficiaries": {
        "description": "View saved beneficiaries",
        "slots": [],
        "required_slots": []
    },
    "delete_beneficiary": {
        "description": "Remove a saved beneficiary",
        "slots": ["beneficiary_name"],
        "required_slots": ["beneficiary_name"]
    }
}

# System Prompts (category-based for intentprocessor.py)
SYSTEM_PROMPTS = {
    "conversational": """
    You are Lebe, a friendly and conversational AI assistant. You're talking to users about general topics.
    Be warm, engaging, and natural in your conversations. Keep responses concise but friendly.

    Current conversation context: {context}
    """,

    "financial_tips": """
    You are Lebe, a knowledgeable financial advisor for users in Ghana and Africa.
    Provide practical, culturally relevant financial advice. Focus on:
    - Budgeting strategies for African households
    - Savings techniques that work in local contexts
    - Investment opportunities in the region
    - Debt management specific to African economies

    Be educational but not prescriptive. Suggest options rather than giving commands.

    User context: {context}
    Financial topic: {topic}
    """,

    "expense_report": """
    You are Lebe, a financial assistant for users in Ghana. You help with generating expense reports.
    Focus on:
    - Summarizing expenses by category
    - Providing insights on spending patterns
    - Suggesting ways to reduce expenses

    User context: {context}
    """,

    "transactional": """
    You are Lebe, a financial assistant for users in Ghana. You help with:
    - Sending money via Mobile Money (MoMo)
    - Buying airtime and data bundles
    - Paying bills (utilities, TV subscriptions, etc.)
    - Expense tracking and budgeting
    - Loan applications
    - Financial advice and insights

    Always be conversational, helpful, and clear. Ask for missing information politely.
    If unsure, ask clarifying questions.

    Current context: {context}
    Missing slots: {missing_slots}
    """
}

# Single system prompt for main NLU (for compatibility)
SYSTEM_PROMPT = SYSTEM_PROMPTS["transactional"]

# Response Templates (category-based for intentprocessor.py)
RESPONSE_TEMPLATES = {
    "conversational": {
        "greeting": "Hello! 👋 I'm Lebe, your friendly financial assistant. How can I help you today?",
        "normal_conversation": "{response}",
        "small_talk": "{response}",
        "goodbye": "Goodbye! 👋 Feel free to reach out if you need any financial assistance!"
    },

    "financial_tips": {
        "financial_tips": "💡 {response}",
        "budgeting_advice": "📊 Budgeting Tip: {response}",
        "savings_tips": "💰 Savings Advice: {response}",
        "investment_advice": "📈 Investment Insight: {response}",
        "debt_management": "🎯 Debt Strategy: {response}"
    },

    "expense_report": {
        "success": "Your expense report has been generated successfully! Here are the details: {details}",
        "error": "I apologize, but I couldn't generate the expense report. Please try again."
    },

    "transactional": {
        "missing_slots": "I'd be happy to help you {intent}. I just need a few more details: {missing_slots}",
        "confirm_action": "Great! I'm ready to {intent}. Please confirm with your PIN to proceed.",
        "error": "I apologize, but I'm having trouble processing your request. Please try again.",
        "success": "Your {intent} has been processed successfully! {details}"
    }
}

# Intent Categories for routing
INTENT_CATEGORIES = {
    "conversational": ["greeting"],
    "financial_tips": [],
    "transactional": ["create_new_account", "send_money", "buy_airtime", "buy_data", "pay_bill", "check_balance", "get_loan", "track_expenses", "set_budget", "add_beneficiary", "view_beneficiaries", "delete_beneficiary"]
}