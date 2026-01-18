import torch

from config import INTENTS

from transformers import (
    AutoTokenizer, 
    AutoModelForCausalLM,
    AutoModelForSeq2SeqLM,
    pipeline,
    GenerationConfig
)

from typing import Dict, List, Any, Tuple
import json
import re
from config import MODEL_CONFIG

class LocalModelHandler:
    def __init__(self):
        self.model_name = MODEL_CONFIG["model_name"]
        self.device = MODEL_CONFIG["device"]
        self.max_length = MODEL_CONFIG["max_length"]
        self.temperature = MODEL_CONFIG["temperature"]
        
        print(f"Loading model: {self.model_name}")
        
        # Load tokenizer and model
        self.tokenizer = AutoTokenizer.from_pretrained(
            self.model_name,
            local_files_only=MODEL_CONFIG["local_files_only"]
        )
        
        # Check if model is DialoGPT (causal LM) or T5 (seq2seq)
        if "dialo" in self.model_name.lower() or "gpt" in self.model_name.lower():
            self.model = AutoModelForCausalLM.from_pretrained(
                self.model_name,
                local_files_only=MODEL_CONFIG["local_files_only"],
                torch_dtype=torch.float16 if self.device == "cuda" else torch.float32
            )
            self.model_type = "causal"
        else:
            # For T5 and other seq2seq models
            self.model = AutoModelForSeq2SeqLM.from_pretrained(
                self.model_name,
                local_files_only=MODEL_CONFIG["local_files_only"],
                torch_dtype=torch.float16 if self.device == "cuda" else torch.float32
            )
            self.model_type = "seq2seq"
        
        self.model.to(self.device)
        
        # Add padding token if missing
        if self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token
        
        print(f"Model loaded successfully. Type: {self.model_type}")
    
    def generate_response(self, prompt: str, context: str = "") -> str:
        """Generate response using local model"""
        
        full_prompt = self._prepare_prompt(prompt, context)
        
        try:
            if self.model_type == "causal":
                return self._generate_causal(full_prompt)
            else:
                return self._generate_seq2seq(full_prompt)
                
        except Exception as e:
            print(f"Error in model generation: {e}")
            return ""
    
    def _prepare_prompt(self, prompt: str, context: str) -> str:
        """Prepare the prompt based on model type"""
        if self.model_type == "causal":
            # For DialoGPT-style models
            if context:
                return f"{context}\nUser: {prompt}\nAssistant:"
            else:
                return f"User: {prompt}\nAssistant:"
        else:
            # For T5-style models
            return prompt
    
    def _generate_causal(self, prompt: str) -> str:
        """Generate using causal LM (DialoGPT)"""
        inputs = self.tokenizer.encode(
            prompt, 
            return_tensors="pt", 
            max_length=self.max_length, 
            truncation=True
        ).to(self.device)
        
        with torch.no_grad():
            outputs = self.model.generate(
                inputs,
                max_length=len(inputs[0]) + 100,  # Generate up to 100 new tokens
                temperature=self.temperature,
                do_sample=MODEL_CONFIG["do_sample"],
                pad_token_id=self.tokenizer.eos_token_id,
                num_return_sequences=1
            )
        
        response = self.tokenizer.decode(outputs[0], skip_special_tokens=True)
        # Extract only the assistant's response
        if "Assistant:" in response:
            response = response.split("Assistant:")[-1].strip()
        
        return response
    
    def _generate_seq2seq(self, prompt: str) -> str:
        """Generate using seq2seq LM (T5)"""
        inputs = self.tokenizer.encode(
            prompt, 
            return_tensors="pt", 
            max_length=self.max_length, 
            truncation=True
        ).to(self.device)
        
        with torch.no_grad():
            outputs = self.model.generate(
                inputs,
                max_length=150,
                temperature=self.temperature,
                do_sample=MODEL_CONFIG["do_sample"],
                num_return_sequences=1
            )
        
        response = self.tokenizer.decode(outputs[0], skip_special_tokens=True)
        return response

class HuggingFaceIntentDetector:
    def __init__(self):
        self.model_handler = LocalModelHandler()
        self.intents = INTENTS
    
    def detect_intent_and_slots(self, user_message: str, conversation_history: List[Dict]) -> Tuple[str, Dict, List[str]]:
        """Detect intent and extract slots using local model"""
        
        context = self._prepare_context(conversation_history)
        
        prompt = f"""
        Read this user message and extract intent and information.
        
        User message: "{user_message}"
        
        Available intents: {list(self.intents.keys())}
        
        For each intent, these slots are needed:
        {self._format_intents_for_prompt()}
        
        Respond in this exact format:
        INTENT: [intent_name]
        SLOTS: {{"slot1": "value1", "slot2": "value2"}}
        MISSING: [missing_slot1, missing_slot2]
        
        If no clear intent, use INTENT: unknown
        """
        
        try:
            response = self.model_handler.generate_response(prompt, context)
            return self._parse_response(response)
            
        except Exception as e:
            print(f"Error in local intent detection: {e}")
            return "unknown", {}, []
    
    def _prepare_context(self, conversation_history: List[Dict]) -> str:
        """Prepare conversation context"""
        if not conversation_history:
            return ""
        
        context = "Previous conversation:\n"
        for msg in conversation_history[-3:]:  # Last 3 messages for context
            role = "User" if msg["role"] == "user" else "Assistant"
            context += f"{role}: {msg['content']}\n"
        return context
    
    def _format_intents_for_prompt(self) -> str:
        """Format intents for the prompt"""
        formatted = ""
        for intent, details in self.intents.items():
            formatted += f"- {intent}: requires {', '.join(details['required_slots'])}\n"
        return formatted
    
    def _parse_response(self, response_text: str) -> Tuple[str, Dict, List[str]]:
        """Parse the model response into structured data"""
        intent = "unknown"
        slots = {}
        missing_slots = []
        
        if not response_text:
            return intent, slots, missing_slots
        
        # Extract INTENT
        intent_match = re.search(r'INTENT:\s*([^\n]+)', response_text, re.IGNORECASE)
        if intent_match:
            intent = intent_match.group(1).strip().lower()
        
        # Extract SLOTS (JSON)
        slots_match = re.search(r'SLOTS:\s*(\{.*?\})', response_text, re.DOTALL)
        if slots_match:
            try:
                slots_str = slots_match.group(1)
                slots = json.loads(slots_str)
            except json.JSONDecodeError:
                # Fallback: try to extract key-value pairs
                slots = self._extract_slots_fallback(response_text)
        
        # Extract MISSING slots
        missing_match = re.search(r'MISSING:\s*(\[.*?\])', response_text, re.DOTALL)
        if missing_match:
            try:
                missing_str = missing_match.group(1)
                missing_slots = json.loads(missing_str)
            except json.JSONDecodeError:
                # Fallback: extract comma-separated values
                missing_text = missing_match.group(1).strip('[]')
                missing_slots = [s.strip() for s in missing_text.split(',') if s.strip()]
        
        return intent, slots, missing_slots
    
    def _extract_slots_fallback(self, text: str) -> Dict:
        """Fallback method to extract slots if JSON parsing fails"""
        slots = {}
        # Look for patterns like "slot: value"
        pattern = r'(\w+):\s*"([^"]*)"'
        matches = re.findall(pattern, text)
        for key, value in matches:
            if key.lower() != 'intent' and value.strip():
                slots[key] = value
        return slots