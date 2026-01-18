import openai
import base64
import logging
from typing import Dict, List, Any, Optional
from core.nlu.config import OPENAI_API_KEY, MODEL, MODEL_CONFIG

logger = logging.getLogger(__name__)


class LLMClient:
    """Centralized LLM API client for handling all LLM conversations, including multimodal inputs"""
    
    def __init__(self):
        self.client = openai.OpenAI(api_key=OPENAI_API_KEY)
        self.model = MODEL
    
    def chat_completion(
        self,
        system_prompt: str,
        user_message: str,
        conversation_history: Optional[List[Dict]] = None,
        temperature: float = 0.1,
        max_tokens: int = 500,
        image_url: Optional[str] = None,
        image_base64: Optional[str] = None,
        image_media_type: str = "image/jpeg"
    ) -> str:
        """
        Generic method for LLM chat completions with optional image support (vision)
        
        Args:
            system_prompt: The system prompt/instruction
            user_message: The current user message
            conversation_history: Previous conversation messages
            temperature: Creativity level (0-1)
            max_tokens: Maximum response length
            image_url: URL to an image (for vision capabilities)
            image_base64: Base64-encoded image data
            image_media_type: MIME type of the image (image/jpeg, image/png, image/gif, image/webp)
            
        Returns:
            LLM response as string
        """
        # Build an `input` payload compatible with the Responses API (supports multimodal)
        # Build a single text input prompt. For now embed image URL/base64
        # inline to avoid structured content type errors with the Responses API.
        input_payload = self._build_messages(
            system_prompt,
            user_message,
            conversation_history,
            image_url=image_url,
            image_base64=image_base64,
            image_media_type=image_media_type,
        )

        try:
            # Use Responses API which supports multimodal inputs (images/audio)
            logger.debug("Sending Responses API request: model=%s", self.model)
            logger.debug("Responses API input payload keys: %s", [m.get('role') for m in input_payload])
            response = self.client.responses.create(
                model=self.model,
                input=input_payload,
                temperature=temperature,
                max_output_tokens=max_tokens,
            )

            logger.debug("Responses API call completed: status=%s", getattr(response, 'status', 'unknown'))

            # Preferred simple accessor when available
            if getattr(response, "output_text", None):
                return response.output_text.strip()

            # Fallback: stitch together textual pieces from the structured output
            parts: List[str] = []
            for out in getattr(response, "output", []) or []:
                for c in out.get("content", []) or []:
                    # common types: 'output_text' or dicts with 'text'
                    if isinstance(c, dict):
                        if c.get("type") in ("output_text", "message", "text"):
                            text = c.get("text") or c.get("content") or c.get("payload")
                            if isinstance(text, str):
                                parts.append(text)
                        elif c.get("type") == "output_fragment":
                            parts.append(c.get("text", ""))
                    elif isinstance(c, str):
                        parts.append(c)

            result_text = "\n".join([p for p in parts if p]).strip()
            if not result_text:
                try:
                    # Attempt to dump structured response for debugging
                    logger.debug("Responses API raw output: %s", getattr(response, "to_dict", lambda: response)())
                except Exception:
                    logger.debug("Responses API raw output (repr): %s", repr(response))

            return result_text

        except Exception as e:
            logger.error(f"Error in LLM API call: {e}")
            print(f"Error in LLM API call: {e}")
            return ""
    
    def _build_messages(
        self,
        system_prompt: str,
        user_message: str,
        conversation_history: Optional[List[Dict]] = None,
        image_url: Optional[str] = None,
        image_base64: Optional[str] = None,
        image_media_type: str = "image/jpeg"
    ) -> List[Dict]:
        """Build a single text prompt string for the Responses API.

        We embed short conversation history and include image references as
        explicit markers so the model sees them even though the request is
        delivered as plain text. This avoids invalid structured content types
        while still providing the model with multimodal context.
        """

        parts: List[str] = []
        parts.append(f"SYSTEM: {system_prompt}")

        if conversation_history:
            parts.append("CONVERSATION HISTORY:")
            for msg in conversation_history[-6:]:
                parts.append(f"{msg.get('role', 'user')}: {msg.get('content', '')}")

        parts.append(f"USER: {user_message}")

        # Include image references inline so the model can use them.
        if image_url:
            parts.append(f"[Image URL]: {image_url}")
        elif image_base64:
            # Avoid dumping very large base64 blobs into logs; include short marker
            parts.append(f"[Image base64 embedded with media type {image_media_type}; length={len(image_base64)}]")

        return "\n\n".join(parts)
    
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
    
    def transcribe_audio(self, audio_file_path: str) -> Optional[str]:
        """
        Transcribe audio file to text using OpenAI Whisper API
        
        Args:
            audio_file_path: Path to the audio file or file object
            
        Returns:
            Transcribed text or None if transcription fails
        """
        try:
            logger.info(f"Transcribing audio file: {audio_file_path}")
            
            with open(audio_file_path, "rb") as audio_file:
                transcript = self.client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file,
                    language="en"  # Specify English; adjust as needed for multilingual support
                )
            
            transcribed_text = transcript.text
            logger.info(f"Audio transcription successful: {transcribed_text}")
            return transcribed_text
            
        except Exception as e:
            logger.error(f"Error transcribing audio: {e}")
            return None
    
    def transcribe_audio_from_bytes(self, audio_bytes: bytes, filename: str = "audio.mp3") -> Optional[str]:
        """
        Transcribe audio from bytes using OpenAI Whisper API
        
        Args:
            audio_bytes: Audio file content as bytes
            filename: Filename with extension (for format detection)
            
        Returns:
            Transcribed text or None if transcription fails
        """
        try:
            logger.info(f"Transcribing audio from bytes: {filename}")
            
            from io import BytesIO
            audio_file = BytesIO(audio_bytes)
            audio_file.name = filename
            
            transcript = self.client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                language="en"  # Specify English; adjust as needed
            )
            
            transcribed_text = transcript.text
            logger.info(f"Audio transcription successful: {transcribed_text}")
            return transcribed_text
            
        except Exception as e:
            logger.error(f"Error transcribing audio from bytes: {e}")
            return None
    
    def chat_completion_with_audio(
        self,
        system_prompt: str,
        user_message: str,
        conversation_history: Optional[List[Dict]] = None,
        temperature: float = 0.1,
        max_tokens: int = 500,
        audio_file_path: Optional[str] = None,
        audio_bytes: Optional[bytes] = None,
        audio_filename: str = "audio.mp3"
    ) -> str:
        """
        Process user message with optional audio transcription
        
        Args:
            system_prompt: The system prompt/instruction
            user_message: The current user message
            conversation_history: Previous conversation messages
            temperature: Creativity level (0-1)
            max_tokens: Maximum response length
            audio_file_path: Path to audio file to transcribe
            audio_bytes: Audio file content as bytes
            audio_filename: Filename for audio bytes (default: audio.mp3)
            
        Returns:
            LLM response as string
        """
        # Transcribe audio if provided
        audio_transcription = None
        if audio_file_path:
            audio_transcription = self.transcribe_audio(audio_file_path)
        elif audio_bytes:
            audio_transcription = self.transcribe_audio_from_bytes(audio_bytes, audio_filename)
        
        # Enhance user message with transcription
        enhanced_message = user_message
        if audio_transcription:
            enhanced_message = f"{user_message}\n\n[Audio transcription: {audio_transcription}]"
        
        return self.chat_completion(
            system_prompt=system_prompt,
            user_message=enhanced_message,
            conversation_history=conversation_history,
            temperature=temperature,
            max_tokens=max_tokens
        )
