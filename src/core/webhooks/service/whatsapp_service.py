import json
import os
import threading
from pathlib import Path

import requests
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class TypingIndicatorLoop:
    """Keep WhatsApp typing active while a long-running operation completes."""

    def __init__(
        self,
        service: "WhatsAppService",
        phone_number_id: str,
        recipient_phone: str,
        message_id: str,
        refresh_interval_seconds: float = 4.0
    ):
        self.service = service
        self.phone_number_id = phone_number_id
        self.recipient_phone = recipient_phone
        self.message_id = message_id
        self.refresh_interval_seconds = refresh_interval_seconds
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def _run(self) -> None:
        self.service.send_typing_indicator(
            phone_number_id=self.phone_number_id,
            recipient_phone=self.recipient_phone,
            message_id=self.message_id
        )

        while not self._stop_event.wait(self.refresh_interval_seconds):
            self.service.send_typing_indicator(
                phone_number_id=self.phone_number_id,
                recipient_phone=self.recipient_phone,
                message_id=self.message_id
            )

    def __enter__(self) -> "TypingIndicatorLoop":
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=1.0)


class WhatsAppService:
    """Service for sending messages via Meta's WhatsApp Cloud API"""

    def __init__(self):
        self.api_key = os.getenv("META_API_KEY")
        self.base_url = "https://graph.facebook.com/v24.0"

    def create_registration_flow(self, phone_number_id: str) -> Optional[str]:
        """
        Create the registration Flow template in Meta using the local JSON definition.

        Args:
            phone_number_id: Meta phone number ID to associate with the Flow

        Returns:
            Optional[str]: The created flow_id, if successful
        """
        json_path = (
            Path(__file__).resolve().parent.parent
            / "templates"
            / "registration_form_flow.json"
        )

        try:
            with open(json_path, "r", encoding="utf-8") as flow_file:
                flow_definition = json.load(flow_file)
        except FileNotFoundError:
            logger.error(f"Flow definition file not found: {json_path}")
            return None

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        url = f"{self.base_url}/{phone_number_id}/flows"
        payload = {
            "flow": flow_definition
        }

        try:
            logger.info(f"Creating WhatsApp registration Flow for {phone_number_id}")
            response = requests.post(url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
            flow_id = data.get("id")
            logger.info(f"Registration Flow created with id: {flow_id}")
            return flow_id

        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to create WhatsApp registration Flow: {e}")
            if hasattr(e, "response") and e.response is not None:
                logger.error(f"Response content: {e.response.text}")
            return None

    def send_message(
        self,
        phone_number_id: str,
        recipient_phone: str,
        message_text: str,
        preview_url: bool = False
    ) -> bool:
        """
        Send a text message via WhatsApp Cloud API

        Args:
            phone_number_id: The phone number ID from Meta webhook metadata
            recipient_phone: The recipient's WhatsApp ID (phone number)
            message_text: The message to send
            preview_url: Whether to show URL preview in the message

        Returns:
            bool: True if message sent successfully, False otherwise
        """
        url = f"{self.base_url}/{phone_number_id}/messages"

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "messaging_product": "whatsapp",
            "to": recipient_phone,
            "type": "text",
            "text": {
                "preview_url": preview_url,
                "body": message_text
            }
        }

        try:
            logger.info(f"Sending WhatsApp text message to {recipient_phone}")
            response = requests.post(url, headers=headers, json=payload)
            response.raise_for_status()

            logger.info(
                f"WhatsApp message sent successfully: {response.json()}")
            return True

        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to send WhatsApp message: {e}")
            if hasattr(e, 'response') and e.response is not None:
                logger.error(f"Response content: {e.response.text}")
            return False

    def send_registration_template(
        self,
        phone_number_id: str,
        recipient_phone: str
    ) -> bool:
        """
        Send registration template via WhatsApp Cloud API
        Args:
            phone_number_id: The phone number ID from Meta webhook metadata
            recipient_phone: The recipient's WhatsApp ID (phone number)
        Returns:
            bool: True if template sent successfully, False otherwise
        """
        url = f"{self.base_url}/{phone_number_id}/messages"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "messaging_product": "whatsapp",
            "to": recipient_phone,
            "type": "template",
            "template": {
                "name": "registration",
                "language": {"code": "en"},
                "components": [
                    {
                        "type": "button",
                        "sub_type": "flow",
                        "index": "0",
                        "parameters": [
                            {
                                "type": "action",
                                "action": {
                                    "flow_token": "2002104030434872"
                                }
                            }
                        ]
                    }
                ]
            }
        }
        try:
            # Log API key info for debugging
            logger.info(f"API Key (first 30 chars): {self.api_key[:30]}...")
            logger.info(f"API Key length: {len(self.api_key)}")
            logger.info(f"Base URL: {self.base_url}")
            logger.info(f"Full URL: {url}")
            logger.info(
                f"Sending WhatsApp registration template to {recipient_phone}")

            response = requests.post(url, headers=headers, json=payload)
            response.raise_for_status()
            logger.info(
                f"WhatsApp template sent successfully: {response.json()}")
            return True
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to send WhatsApp template: {e}")
            if hasattr(e, 'response') and e.response is not None:
                logger.error(f"Response content: {e.response.text}")
            return False

    def send_typing_indicator(
        self,
        phone_number_id: str,
        recipient_phone: str,
        message_id: str
    ) -> bool:
        """
        Mark message as read and show typing indicator to the user.

        Args:
            phone_number_id: The phone number ID from Meta webhook metadata
            recipient_phone: The recipient's WhatsApp ID (phone number)
            message_id: The incoming message ID to mark as read

        Returns:
            bool: True if typing indicator sent successfully, False otherwise
        """
        url = f"{self.base_url}/{phone_number_id}/messages"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        typing_payload = {
            "messaging_product": "whatsapp",
            "status": "read",
            "message_id": message_id,
            "typing_indicator": {
                "type": "text"
            }
        }

        try:
            response = requests.post(url, headers=headers, json=typing_payload)
            response.raise_for_status()
            logger.info(
                f"Typing indicator sent to {recipient_phone} for message {message_id}"
            )
            return True
        except requests.exceptions.RequestException as e:
            logger.warning(f"Failed to send typing indicator: {e}")
            if hasattr(e, 'response') and e.response is not None:
                logger.warning(f"Response content: {e.response.text}")
            return False

    def send_message_receipt(
        self,
        phone_number_id: str,
        recipient_phone: str,
        image_url: str,
        caption: Optional[str] = None
    ) -> bool:
        """
        Send a receipt image via WhatsApp Cloud API

        Args:
            phone_number_id: The phone number ID from Meta webhook metadata
            recipient_phone: The recipient's WhatsApp ID (phone number)
            image_url: The URL of the receipt image to send (must be publicly accessible)
            caption: Optional caption for the receipt

        Returns:
            bool: True if receipt sent successfully, False otherwise
        """
        url = f"{self.base_url}/{phone_number_id}/messages"

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "messaging_product": "whatsapp",
            "to": recipient_phone,
            "type": "image",
            "image": {
                "link": image_url
            }
        }

        # Add caption if provided
        if caption:
            payload["image"]["caption"] = caption

        try:
            logger.info(f"Sending WhatsApp receipt to {recipient_phone}")
            logger.debug(f"Receipt URL: {image_url}")
            response = requests.post(url, headers=headers, json=payload)
            response.raise_for_status()

            logger.info(
                f"WhatsApp receipt sent successfully: {response.json()}")
            return True

        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to send WhatsApp receipt: {e}")
            if hasattr(e, 'response') and e.response is not None:
                logger.error(f"Response content: {e.response.text}")
            return False

    def typing_indicator_loop(
        self,
        phone_number_id: str,
        recipient_phone: str,
        message_id: str,
        refresh_interval_seconds: float = 4.0
    ) -> TypingIndicatorLoop:
        return TypingIndicatorLoop(
            service=self,
            phone_number_id=phone_number_id,
            recipient_phone=recipient_phone,
            message_id=message_id,
            refresh_interval_seconds=refresh_interval_seconds
        )
