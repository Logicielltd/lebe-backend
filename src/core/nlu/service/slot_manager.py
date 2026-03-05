from typing import Dict, List, Any, Optional
from core.nlu.config import INTENTS

class SlotManager:
    def __init__(self):
        self.intents = INTENTS
    
    def get_missing_slots(self, intent: str, current_slots: Dict) -> List[str]:
        """Get list of missing required slots for an intent"""
        if intent not in self.intents:
            return []
        
        required_slots = self.intents[intent].get("required_slots", [])
        missing = []
        
        for slot in required_slots:
            if slot not in current_slots or not current_slots[slot]:
                missing.append(slot)
        
        return missing
    
    def validate_slots(self, intent: str, slots: Dict) -> Dict:
        """Validate and clean extracted slots"""
        validated_slots = {}

        for slot, value in slots.items():
            if value:
                # Basic validation based on slot type
                if "amount" in slot:
                    validated_slots[slot] = self._validate_amount(value)
                elif "account_number" in slot:
                    # Account numbers should not be validated - they can be in any format
                    validated_slots[slot] = str(value).strip()
                elif "phone" in slot or "recipient" in slot or "number" in slot:
                    validated_slots[slot] = self._validate_phone_number(value)
                else:
                    validated_slots[slot] = str(value).strip()

        return validated_slots
    
    def _validate_amount(self, amount: str) -> Optional[str]:
        """Validate amount format"""
        try:
            # Remove currency symbols and commas
            clean_amount = ''.join(c for c in str(amount) if c.isdigit() or c == '.')
            if clean_amount:
                return str(float(clean_amount))
        except:
            pass
        return None
    
    def _validate_phone_number(self, phone: str) -> Optional[str]:
        """Validate Ghana phone number format"""
        # Remove spaces, dashes, etc.
        clean_phone = ''.join(c for c in str(phone) if c.isdigit())
        
        # Ghana numbers: 10 digits starting with 0, or 9 digits without 0
        if len(clean_phone) == 10 and clean_phone.startswith('0'):
            return clean_phone
        elif len(clean_phone) == 9:
            return f"0{clean_phone}"
        
        return None
    
    def generate_slot_prompt(self, intent: str, missing_slots: List[str]) -> str:
        """Generate natural language prompt for missing slots with intent-aware context"""
        
        # If no missing slots provided, ask for the entire operation again
        if not missing_slots:
            return "can you be more detailed about your request?"

        # Available bill providers and their codes
        bill_providers = {
            "GoTV": "GOT",
            "DStv": "DST",
            "ECG": "ECG",
            "Ghana Water": "GHW",
            "Surfline": "SFL",
            "Telesol": "TLS",
            "Startimes": "STT",
            "Box Office": "BXO",
        }

        slot_descriptions = {
            "recipient": "Who would you like to send money to? Please provide the phone number.",
            "amount": "How much would you like to send?",
            "network": "Which mobile network? (MTN, Vodafone, AirtelTigo)",
            "reference": "What's the reference for this transfer?",
            "phone_number": "Which phone number should I top up?",
            "data_plan": "Which data plan would you like?",
            "bill_type": self._generate_bill_type_prompt(bill_providers),
            "account_number": "What's your account number (smart card number)?",
            "provider": "Who is the service provider?",
            "loan_amount": "How much would you like to borrow?",
            "duration": "How long would you like the loan for?",
            "purpose": "What will you use the loan for?",
            "category": "Which category?",
            "period": "For what period?",
            "time_period": "For what time period?",
            "beneficiary_name": "Whose name do you want to send to (from your saved contacts)?",
            "new_beneficiary_name": "What should the new beneficiary name be?",
            "customer_number": "Beneficiary mobile number?"
        }

        prompts = []
        for slot in missing_slots:
            if slot in slot_descriptions:
                prompts.append(slot_descriptions[slot])
            else:
                prompts.append(f"What's the {slot}?")

        return " ".join(prompts)

    def _generate_bill_type_prompt(self, bill_providers: Dict[str, str]) -> str:
        """Generate prompt with list of available bill providers on separate lines"""
        providers_list = "\n".join([f"• {name} ({code})" for name, code in bill_providers.items()])
        return f"Which bill would you like to pay?\nAvailable options:\n{providers_list}"
