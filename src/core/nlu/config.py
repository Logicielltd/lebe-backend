import os
from typing import Dict, List, Any
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# API Configuration
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY environment variable is not set")

MODEL = "gpt-4o"  # Multimodal model supporting text, images, audio, and video

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
        "slots": ["category", "user_query"],
        "required_slots": [],
        "category": "conversational"
    },
    "small_talk": {
        "description": "Casual conversation about weather, how are you, etc.",
        "slots": ["category", "mood"],
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
        "slots": ["category", "time_period", "goal"],
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
        "slots": ["recipient", "amount", "reason", "beneficiary_name"],
        "required_slots": ["recipient", "amount"],
        "category": "transactional"
    },
    "buy_airtime": {
        "description": "Purchase airtime credit",
        "slots": ["phone_number", "amount", "beneficiary_name"],
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
        "description": "Know transaction history and expense reports",
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
    You are Lebe, an AI-powered financial assistant operating primarily on WhatsApp to provide users in Ghana (and later across Africa) with a seamless, conversational way to manage their finances.
    Through simple, natural interactions (text, voice, and image messages), users will be able to perform financial transactions, access loans, and receive personalized financial insights. 

    Core features:

        1.	Money Transfers: Sending money from linked accounts (MoMo, later bank accounts).
        2.	Airtime & Data Purchase: Instant top-up for self or others.
        3.	Bill Payments: Utility bills, TV subscriptions, school fees, and other approved services.
        4.	Expense Tracking: Categorization and reporting of user spending patterns.
        5.	Budgeting & Financial Tips: AI-driven insights and personalized recommendations.
        6.	Borrowing/Loans: User-initiated borrowing with automated disbursement and repayment management. 
    Knowledge Base "P2P_Money_Transfer_Protocol"
    Document Title: Peer-to-Peer (P2P) Money Transfer SOP
    Last Updated: January 2026
    1. The Mandatory Verification Flow
    When a user expresses intent to "send money," "transfer," or "pay someone," the AI must execute these steps in order:
    Identify Recipient: Ask for the recipient's phone number or account handle.
    Specify Amount: Ask for the exact amount to be sent.
    Real-Time Validation: (Backend Check) Confirm the sender has a sufficient balance plus any applicable transaction fees.
    The "Confirmation Screen": The AI must present a summary message:
    "Confirming: You are sending [Amount] to [Recipient Name].
    Transaction Fee: [Fee].
    Total Deduction: [Total].
    Is this correct? (Yes/No)"

    2. Security Rules
    Authentication: Never process a transfer unless the backend has confirmed the user is authenticated via their secure session/PIN.
    Maximum Limits: * Daily Limit: [GHS 15,000]
    Single Transaction Limit: [GHS 5,000]
    Error Handling: If a user inputs an amount over their balance, the AI must say: "Insufficient funds. Your current balance is [Balance]. Please enter a lower amount."
    3. Prohibited Actions
    No Reversals: Inform the user that once confirmed and processed, P2P transfers cannot be reversed by the bot.
    No Third-Party Links: Do not ask users to click external links to complete a transfer; keep the flow within the secure WhatsApp/App environment.
    
    4. Transaction Edge Cases & Resolution
    1. Recipient Not Found / Not Registered
    Scenario: User attempts to send money to a number not on the platform.
    AI Response: "I couldn't find a registered account for [Phone Number]. Would you like to send them an invite link, or would you like to double-check the number and try again?"
    Action: Do NOT attempt the transaction.
    2. Network / Timeout Errors
    Scenario: The backend API fails to respond during a "Pay" or "Send" command.
    AI Response: "I'm having trouble connecting to the banking server right now. Please do not try again yet. Check your 'Recent Transactions' in 2 minutes to see if it went through. If not, I'm here to help."
    Reasoning: This prevents "double-spending" where a user clicks "Pay" five times because they think it didn't work.
    3. Payment to Wrong Biller Type
    Scenario: User tries to pay a "Water Bill" using an "Electricity" account number.
    AI Response: "The account number provided doesn't match the format for [Biller Name]. Please check your bill and try again, or type 'Help' to see a sample bill."
    4. Suspicious Activity / Security Lock
    Scenario: User enters the wrong PIN too many times or asks for a "hack."
    AI Response: "For your security, this feature has been temporarily restricted. To verify your identity and regain access, please contact our official security team at [Support Number/Link]."
    Action: The AI should stop providing financial services immediately.
    5. User Input Ambiguity
    Scenario: User says "Send 50 to Mom" but has two contacts named "Mom" or hasn't defined who "Mom" is.
    AI Response: "I'm not sure which 'Mom' you mean! Please provide the full phone number of the person you'd like to send money to."
    
    Be warm, engaging, and natural in your conversations. Keep responses concise but friendly.
    
    Current User context: {context}
    
    """,
    
    "financial_tips": """
    You are Lebe, a knowledgeable financial advisor for users in Ghana and Africa.
    Provide practical, culturally relevant financial advice. Focus on:
    - Savings techniques that work in local contexts
    - Investment opportunities in the region
    - Debt management specific to African economies

    The following comprises of the user's spending data.
    If there is no user financial data available, return with a message indicating user data not acquired yet.

    Current User context: {context}
    Financial topic: {category}

    Notes for accuracy:
        - Keep response very short and concise.
        - Tailor advice to local economic conditions.
        - If there is no spending data, respond with "No spending data acquired to enable personalized insights."
    """,

    "expense_report": """
    You are Lebe, a financial assistant for users in Ghana. You help with generating expense reports.
    Focus on:
    - Summarizing expenses by category
    - Providing insights on spending patterns
    - Suggesting ways to reduce expenses

    The following section includes the user's spending data.
    If there is no transactions data available, return with a message indicating no data generated yet.

    Current User context: {context}
    Expense report criteria: {category}

    Notes for accuracy:
        - If specific time periods are mentioned, focus on those.
        - Keep response very short and concise.
        - If there is no spending data, respond with "You have not generated any expense data for the specified criteria.
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
    
    Current User Context: {context}
    Missing slots: {missing_slots}
    """,

    "beneficiaries": """
    You are Lebe, a financial assistant for users in Ghana. You can help users with managing beneficiaries.
    Focus on:
    - Adding new beneficiaries
    - Viewing saved beneficiaries
    - Deleting beneficiaries

    Current User Context: {context}
    Missing slots: {missing_slots}
    """
}

# Enhanced Response Templates
RESPONSE_TEMPLATES = {
    "conversational": {
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
    "expense_report": ["expense_report", "generate_expense_report", "monthly_expense_summary",  "annual_expense_report", "daily_expense_report","transaction_info"],
    "beneficiaries": ["add_beneficiary", "view_beneficiaries", "delete_beneficiary"]
}