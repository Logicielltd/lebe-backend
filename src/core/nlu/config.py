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
    # ===== CONVERSATIONAL INTENTS =====
    "greeting": {
        "description": "Greet the user",
        "slots": [],
        "required_slots": [],
        "category": "conversational"
    },
    "normal_conversation": {
        "description": "Handle general non-financial conversations",
        "slots": ["topic", "user_query"],
        "required_slots": [],
        "category": "conversational"
    },
    "small_talk": {
        "description": "Casual conversation about weather, how are you, etc.",
        "slots": ["topic", "mood"],
        "required_slots": [],
        "category": "conversational"
    },
    "goodbye": {
        "description": "End conversation politely",
        "slots": [],
        "required_slots": [],
        "category": "conversational"
    },
    
    # ===== FINANCIAL TIPS INTENTS =====
    "financial_tips": {
        "description": "Provide general financial advice and tips",
        "slots": ["topic", "time_period", "goal"],
        "required_slots": [],
        "category": "financial_tips"
    },
    "budgeting_advice": {
        "description": "Provide budgeting recommendations",
        "slots": ["income_level", "expense_category", "savings_goal"],
        "required_slots": [],
        "category": "financial_tips"
    },
    "savings_tips": {
        "description": "Offer savings strategies and advice",
        "slots": ["savings_goal", "timeframe", "current_savings"],
        "required_slots": [],
        "category": "financial_tips"
    },
    "investment_advice": {
        "description": "Provide basic investment guidance",
        "slots": ["risk_tolerance", "investment_amount", "time_horizon"],
        "required_slots": [],
        "category": "financial_tips"
    },
    "debt_management": {
        "description": "Offer debt management strategies",
        "slots": ["debt_type", "debt_amount", "income"],
        "required_slots": [],
        "category": "financial_tips"
    },
    
    # ===== TRANSACTIONAL INTENTS =====
    "send_money": {
        "description": "Send money to another person",
        "slots": ["recipient", "amount", "network", "reason"],
        "required_slots": ["recipient", "amount"],
        "category": "transactional"
    },
    "buy_airtime": {
        "description": "Purchase airtime credit",
        "slots": ["phone_number", "amount", "network"],
        "required_slots": ["phone_number", "amount"],
        "category": "transactional"
    },
    "pay_bill": {
        "description": "Pay utility bills",
        "slots": ["bill_type", "account_number", "amount", "provider"],
        "required_slots": ["bill_type", "account_number", "amount"],
        "category": "transactional"
    },
    "check_balance": {
        "description": "Check account balance",
        "slots": [],
        "required_slots": [],
        "category": "transactional"
    },
    "get_loan": {
        "description": "Apply for a loan",
        "slots": ["loan_amount", "duration", "purpose"],
        "required_slots": ["loan_amount"],
        "category": "transactional"
    },
    "expense_report": {
        "description": "View expense tracking",
        "slots": ["time_period", "category"],
        "required_slots": [],
        "category": "expense_report"
    },
    "set_budget": {
        "description": "Set spending budget",
        "slots": ["category", "amount", "period"],
        "required_slots": ["category", "amount"],
        "category": "transactional"
    },
    # ===== BENEFICIARY MANAGEMENT INTENTS =====
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

# Enhanced System Prompts by Category
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
    Future enhancement: This will be augmented with user's actual financial data.
    
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
    Expense report criteria: {category}
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
    """,

    "beneficiaries": """
    You are Lebe, a financial assistant for users in Ghana. You can help users with managing beneficiaries.
    Focus on:
    - Adding new beneficiaries
    - Viewing saved beneficiaries
    - Deleting beneficiaries

    User context: {context}
    Missing slots: {missing_slots}
    """
}

# Enhanced Response Templates
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
    },
    "beneficiaries": {
        "add_beneficiary": "The beneficiary {beneficiary_name} has been added successfully.",
        "view_beneficiaries": "Here are your saved beneficiaries: {beneficiaries_list}",
        "delete_beneficiary": "The beneficiary {beneficiary_name} has been removed successfully."
    }
}

# Intent Categories for routing
INTENT_CATEGORIES = {
    "conversational": ["greeting", "normal_conversation", "small_talk", "goodbye"],
    "financial_tips": ["financial_tips", "budgeting_advice", "savings_tips", "investment_advice", "debt_management"],
    "transactional": ["send_money", "buy_airtime", "pay_bill", "check_balance", "get_loan", "track_expenses", "set_budget"],
    "expense_report": ["expense_report", "generate_expense_report", "monthly_expense_summary",  "annual_expense_report", "daily_expense_report"],
    "beneficiaries": ["add_beneficiary", "view_beneficiaries", "delete_beneficiary"]
}