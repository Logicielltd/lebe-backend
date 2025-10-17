import os
import requests
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class WhatsAppService:
    """Service for sending messages via Meta's WhatsApp Cloud API"""

    def __init__(self):
        self.api_key = os.getenv("META_API_KEY")
        self.base_url = "https://graph.facebook.com/v22.0"

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
                "name": "registration_form",
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
                                    "flow_token": "1151913393050063"
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
