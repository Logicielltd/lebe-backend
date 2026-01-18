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
            # input_payload may be a string prompt or a structured list; handle both
            if isinstance(input_payload, str):
                logger.debug("Responses API input payload is a string (len=%d): %s", len(input_payload), input_payload[:200])
            else:
                try:
                    keys = [m.get('role') for m in input_payload]
                except Exception:
                    keys = str(input_payload)
                logger.debug("Responses API input payload keys: %s", keys)
            response = self.client.responses.create(
                model=self.model,
                input=input_payload,
                temperature=temperature,
                max_output_tokens=max_tokens,
            )

            logger.debug("Responses API call completed: status=%s", getattr(response, 'status', 'unknown'))
            # Log key response fields for debugging
            try:
                # Log concise outputs at INFO to help trace intent failures
                if getattr(response, "output_text", None):
                    logger.info("Responses API output_text (truncated): %s", (response.output_text or '')[:1000])

                # Log structured `output` if present at DEBUG
                output_obj = getattr(response, "output", None)
                if output_obj is not None:
                    logger.debug("Responses API 'output' field present. Entries: %d", len(output_obj) if hasattr(output_obj, '__len__') else 1)

                # Attempt a safe full dump at DEBUG level; avoid crashing if to_dict is not available
                try:
                    to_dict_fn = getattr(response, "to_dict", None)
                    if callable(to_dict_fn):
                        resp_dict = to_dict_fn()
                        logger.debug("Responses API full payload (truncated): %s", str(resp_dict)[:4000])
                    else:
                        logger.debug("Responses API repr payload (truncated): %s", repr(response)[:4000])
                except Exception as ex:
                    logger.debug("Failed to serialize Responses API payload: %s", ex)
            except Exception as ex:
                logger.debug("Error while logging Responses API payload: %s", ex)

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
        """Build messages for the Responses API.

        The Responses API has specific requirements for content types.
        For system messages, we need to use `output_text` instead of `input_text`.
        """

        # When an image is provided, construct a structured payload compatible
        # with the Responses API's multimodal format
        if image_url or image_base64:
            messages: List[Dict] = []

            # Add system prompt as the FIRST item in content (not as a separate message)
            # For Responses API, system prompts should be included in the first message's content
            content_items: List[Dict[str, Any]] = []

            # Add system prompt using 'output_text' type (required by Responses API for system content)
            content_items.append(
                {
                    "type": "output_text",  # Changed from 'input_text' to 'output_text'
                    "text": system_prompt
                }
            )

            # Include conversation history as output_text items
            if conversation_history:
                for msg in conversation_history[-6:]:
                    role = msg.get("role", "user")
                    # For Responses API, we add history as text within the system/user context
                    if role == "system":
                        content_items.append({
                            "type": "output_text",
                            "text": msg.get("content", "")
                        })
                    else:
                        # User/assistant history can be included as context in the prompt
                        pass  # We'll handle this differently below

            # Build the user content
            user_content: List[Dict[str, Any]] = [{"type": "input_text", "text": user_message}]

            if image_base64:
                user_content.append(
                    {
                        "type": "input_image",
                        "image_base64": image_base64,
                        "mime_type": image_media_type,
                    }
                )
            else:
                # image_url
                user_content.append(
                    {"type": "input_image", "image_url": image_url, "mime_type": image_media_type}
                )

            # Combine system content and user content
            # For Responses API, the system prompt should be in output_text format
            # and user content in input_text/input_image format
            messages = [
                {
                    "role": "user",  # Responses API expects user role for input
                    "content": [
                        # First include system context as output_text
                        {
                            "type": "output_text",
                            "text": system_prompt
                        },
                        # Then include conversation history context
                        *([
                            {
                                "type": "output_text",
                                "text": f"Previous conversation:\n{' '.join([f'{m.get('role', 'user')}: {m.get('content', '')}' for m in conversation_history[-3:]])}"
                            }
                        ] if conversation_history else []),
                        # Finally include the actual user input with image
                        {
                            "type": "input_text",
                            "text": user_message
                        },
                        # Add image
                        {
                            "type": "input_image",
                            "image_url": image_url if image_url else f"data:{image_media_type};base64,{image_base64}",
                            "mime_type": image_media_type
                        }
                    ]
                }
            ]

            return messages

        # No image provided: keep previous simple plain-text prompt behavior
        parts: List[str] = []
        if system_prompt:
            parts.append(f"SYSTEM: {system_prompt}")

        if conversation_history:
            parts.append("CONVERSATION HISTORY:")
            for msg in conversation_history[-6:]:
                parts.append(f"{msg.get('role', 'user')}: {msg.get('content', '')}")

        parts.append(f"USER: {user_message}")

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
