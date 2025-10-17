from fastapi import APIRouter, Depends, HTTPException, status, Query
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel
from core.auth.service.sessiondriver import SessionDriver, TokenData
from fastapi_jwt_auth import AuthJWT
from core.exceptions import *
from core.webhooks.dto.request.dialogrequest import DialogRequest
from utilities.dbconfig import SessionLocal
from sqlalchemy.orm import Session
import logging
import os
from core.user.model.User import User
from core.nlu.main import LebeNLUSystem
from core.subscription.service.subscription_service import SubscriptionService
from core.webhooks.service.whatsapp_service import WhatsAppService

# DTO Models
from core.notification.dto.response.message_response import MessageResponse
from core.webhooks.dto.response.message_response import LebeResponse

from fastapi_jwt_auth.exceptions import MissingTokenError
from core.auth.service.authservice import AuthService

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Reuse your existing token validation and DB dependencies
from core.user.controller.usercontroller import validate_token, get_db

# Controller (Router)
webhooks_routes = APIRouter()

@webhooks_routes.get("/start-dialog")
def verify_webhook(
    mode: Optional[str] = Query(None, alias="hub.mode"),
    challenge: Optional[str] = Query(None, alias="hub.challenge"),
    verify_token: Optional[str] = Query(None, alias="hub.verify_token")
):
    """
    Webhook verification endpoint for Meta (Facebook/WhatsApp) webhooks.
    Meta will send a GET request with hub.mode, hub.challenge, and hub.verify_token.
    """
    expected_verify_token = os.getenv("VERIFY_TOKEN")

    if mode == "subscribe" and verify_token == expected_verify_token:
        logger.info("WEBHOOK VERIFIED")
        return int(challenge)
    else:
        logger.warning("Webhook verification failed")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Verification failed"
        )

@webhooks_routes.post("/start-dialog")
def start_dialog(
    dialog_payload: DialogRequest,
    db: Session = Depends(get_db)
):
    """
    Handles incoming WhatsApp messages from Meta webhook.
    Extracts the user's phone number and message, processes it through the NLU system,
    and sends the response back to the user via WhatsApp Cloud API.
    """
    # Log the incoming webhook payload
    logger.info(f"Received webhook payload: {dialog_payload.json(indent=2)}")

    try:
        # Extract the phone number (wa_id) and message from the nested structure
        entry = dialog_payload.entry[0]
        change = entry.changes[0]
        value = change.value

        # Get phone number ID from metadata (needed to send messages)
        phone_number_id = value.metadata.phone_number_id
        logger.info(f"Phone number ID: {phone_number_id}")

        # Get phone number from contacts
        phone = value.contacts[0].wa_id
        logger.info(f"Extracted phone number: {phone}")

        # Get message text
        message = value.messages[0]
        if message.type == "text" and message.text:
            message_text = message.text.body
            logger.info(f"Extracted message: {message_text}")
        else:
            logger.warning(f"Unsupported message type: {message.type}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported message type: {message.type}"
            )

        # Check if user exists in database
        existing_user = db.query(User).filter(User.phone == phone).first()
        whatsapp_service = WhatsAppService()

        if not existing_user:
            # New user - send registration template
            logger.info(f"New user detected: {phone}. Sending registration template.")
            message_sent = whatsapp_service.send_registration_template(
                phone_number_id=phone_number_id,
                recipient_phone=phone
            )

            if not message_sent:
                logger.error("Failed to send WhatsApp registration template")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to send WhatsApp registration template"
                )
        else:
            # Existing user - process message through NLU and send text response
            logger.info(f"Existing user detected: {phone}. Processing message through NLU.")

            # Initialize NLU system and subscription service
            nlu_system = LebeNLUSystem()
            subscription_service = SubscriptionService(db)

            # Get user subscription status
            result = subscription_service.get_user_subscription_status_by_phone(phone)

            # Initialize user and process message
            nlu_system.initialize_user(phone, "00000")
            response_message = nlu_system.process_message(
                phone,
                message_text,
                result["has_active_subscription"]
            )

            logger.info(f"Generated response: {response_message}")

            # Send the response back to the user via WhatsApp
            message_sent = whatsapp_service.send_message(
                phone_number_id=phone_number_id,
                recipient_phone=phone,
                message_text=response_message
            )

            if not message_sent:
                logger.error("Failed to send WhatsApp message")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to send WhatsApp message"
                )

        # Return success response to Meta
        return {"status": "success", "message": "Message processed and sent"}

    except IndexError as e:
        logger.error(f"Error parsing webhook payload: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid webhook payload structure"
        )
    except Exception as e:
        logger.error(f"Error processing message: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )