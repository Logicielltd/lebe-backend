import openai
from typing import Dict, List, Any, Optional
from core.nlu.config import OPENAI_API_KEY, MODEL, MODEL_CONFIG

class LLMClient:
    """Centralized LLM API client for handling all LLM conversations"""
    
    def __init__(self):
        self.client = openai.OpenAI(api_key=OPENAI_API_KEY)
        self.model = MODEL
    
    def chat_completion(
        self,
        system_prompt: str,
        user_message: str,
        conversation_history: Optional[List[Dict]] = None,
        temperature: float = 0.1,
        max_tokens: int = 500
    ) -> str:
        """
        Generic method for LLM chat completions
        
        Args:
            system_prompt: The system prompt/instruction
            user_message: The current user message
            conversation_history: Previous conversation messages
            temperature: Creativity level (0-1)
            max_tokens: Maximum response length
            
        Returns:
            LLM response as string
        """
        messages = self._build_messages(system_prompt, user_message, conversation_history)
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens
            )
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            print(f"Error in LLM API call: {e}")
            return ""
    
    def _build_messages(
        self,
        system_prompt: str,
        user_message: str,
        conversation_history: Optional[List[Dict]] = None
    ) -> List[Dict]:
        """Build the messages array for the LLM API"""
        messages = [{"role": "system", "content": system_prompt}]
        
        # Add conversation history if provided
        if conversation_history:
            for msg in conversation_history:
                messages.append({"role": msg["role"], "content": msg["content"]})
        
        # Add current user message
        messages.append({"role": "user", "content": user_message})
        
        return messages
    
    def structured_completion(
        self,
        system_prompt: str,
        user_message: str,
        expected_format: str,
        conversation_history: Optional[List[Dict]] = None
    ) -> str:
        """
        For structured outputs where you expect specific format
        
        Args:
            expected_format: Description of expected output format
        """
        enhanced_prompt = f"{user_message}\n\nPlease respond in this format:\n{expected_format}"
        
        return self.chat_completion(
            system_prompt=system_prompt,
            user_message=enhanced_prompt,
            conversation_history=conversation_history,
            temperature=0.1  # Lower temperature for structured outputs
        )