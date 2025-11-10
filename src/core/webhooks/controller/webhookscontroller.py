from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
import json
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
from core.nlu.nlu import LebeNLUSystem
from core.subscription.service.subscription_service import SubscriptionService
from core.webhooks.service.whatsapp_service import WhatsAppService
from utilities.phone_utils import normalize_ghana_phone_number

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
async def start_dialog(
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Handles incoming WhatsApp webhooks from Meta.
    Routes to appropriate handler based on webhook type.
    """
    # Parse the incoming payload as generic dict
    payload = await request.json()

    # Log the incoming webhook payload
    logger.info(f"Received webhook payload: {json.dumps(payload, indent=2)}")

    try:
        # Check if this is a valid webhook payload
        if "object" not in payload or "entry" not in payload:
            logger.warning("Invalid webhook payload structure")
            return {"status": "ok", "message": "Invalid payload structure"}

        # Extract entry and changes
        entries = payload.get("entry", [])
        if not entries:
            logger.warning("No entries in webhook payload")
            return {"status": "ok", "message": "No entries"}

        entry = entries[0]
        changes = entry.get("changes", [])
        if not changes:
            logger.warning("No changes in webhook entry")
            return {"status": "ok", "message": "No changes"}

        change = changes[0]
        value = change.get("value", {})
        field = change.get("field", "")

        logger.info(f"Webhook field type: {field}")

        # Route based on webhook type

        # 1. Handle incoming messages (text, image, etc.)
        if "messages" in value:
            return handle_incoming_message(
                value=value,
                db=db
            )

        # 2. Handle message status updates (delivered, read, failed)
        elif "statuses" in value:
            return handle_message_status(
                value=value,
                db=db
            )

        # 3. Handle other webhook types
        else:
            logger.info(f"Unsupported webhook field: {field}")
            return {"status": "ok", "message": "Webhook type not handled"}

    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        logger.error(f"Unexpected error processing webhook: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error processing webhook"
        )


def handle_incoming_message(value: dict, db: Session):
    """
    Handles incoming messages from users.
    Processes text messages, Flow responses, and other message types.
    """
    try:
        # Get phone number ID from metadata (needed for sending messages)
        metadata = value.get("metadata", {})
        phone_number_id = metadata.get("phone_number_id")
        if not phone_number_id:
            logger.error("Missing phone_number_id in metadata")
            return {"status": "error", "message": "Missing phone_number_id"}

        logger.info(f"Phone number ID: {phone_number_id}")

        # Get sender phone number
        contacts = value.get("contacts", [])
        if not contacts:
            logger.error("Missing contacts in webhook payload")
            return {"status": "error", "message": "Missing contacts"}

        phone = contacts[0].get("wa_id")
        if not phone:
            logger.error("Missing wa_id in contacts")
            return {"status": "error", "message": "Missing wa_id"}

        logger.info(f"Extracted phone number: {phone}")

        # Get the message
        messages = value.get("messages", [])
        if not messages:
            logger.warning("No messages in payload")
            return {"status": "ok", "message": "No messages"}

        message = messages[0]
        message_type = message.get("type")

        # Handle different message types
        if message_type == "text":
            return handle_text_message(
                message=message,
                phone=phone,
                phone_number_id=phone_number_id,
                db=db
            )

        elif message_type == "interactive":
            # This handles Flow responses
            return handle_interactive_message(
                message=message,
                phone=phone,
                phone_number_id=phone_number_id,
                db=db
            )

        elif message_type in ["image", "video", "audio", "document"]:
            logger.info(f"Received {message_type} message from {phone}")
            whatsapp_service = WhatsAppService()
            whatsapp_service.send_message(
                phone_number_id=phone_number_id,
                recipient_phone=phone,
                message_text=f"Thanks for the {message_type}! Currently, I only support text messages."
            )
            return {"status": "ok", "message": f"{message_type} message received"}

        else:
            logger.warning(f"Unsupported message type: {message_type}")
            whatsapp_service = WhatsAppService()
            whatsapp_service.send_message(
                phone_number_id=phone_number_id,
                recipient_phone=phone,
                message_text="Sorry, I don't support this message type yet."
            )
            return {"status": "ok", "message": f"Unsupported message type: {message_type}"}

    except Exception as e:
        logger.error(f"Error handling incoming message: {e}", exc_info=True)
        raise


def handle_text_message(message: dict, phone: str, phone_number_id: str, db: Session):
    """Handle regular text messages"""
    text_data = message.get("text")
    if not text_data or "body" not in text_data:
        logger.warning("Text message has no body")
        return {"status": "ok", "message": "Empty text message"}

    message_text = text_data.get("body")
    logger.info(f"Extracted text message: {message_text}")

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

        return {"status": "success", "message": "Registration template sent"}

    else:
        # Existing user - process message through NLU
        logger.info(f"Existing user detected: {phone}. Processing message through NLU.")

        # Initialize NLU system and subscription service
        nlu_system = LebeNLUSystem()
        subscription_service = SubscriptionService(db)

        # Get user subscription status
        result = subscription_service.get_user_subscription_status_by_phone(phone)

        # Process the message
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

        return {"status": "success", "message": "Message processed and sent"}


def handle_interactive_message(message: dict, phone: str, phone_number_id: str, db: Session):
    """
    Handle interactive messages like Flow responses and button replies.
    This is where you'll receive the registration form data!
    """
    interactive = message.get("interactive", {})
    interactive_type = interactive.get("type")

    logger.info(f"Received interactive message type: {interactive_type}")

    if interactive_type == "nfm_reply":
        # This is a Flow response (your registration form!)
        nfm_reply = interactive.get("nfm_reply", {})
        response_json = nfm_reply.get("response_json", "{}")
        flow_token = nfm_reply.get("flow_token")

        logger.info(f"Flow response received from {phone}")
        logger.info(f"Flow token: {flow_token}")
        logger.info(f"Response data: {response_json}")

        # Parse the registration form data
        registration_data = json.loads(response_json)

        # Log the complete registration data
        logger.info(f"Registration data received: {json.dumps(registration_data, indent=2)}")

        try:
            # Extract registration fields from Flow response
            first_name = registration_data.get("screen_0_First_Name__0", "").strip()
            last_name = registration_data.get("screen_0_Last_Name__1", "").strip()
            user_phone = registration_data.get("screen_0_Phone_Number__2", "").strip()
            email = registration_data.get("screen_0_Email_3", "").strip()
            pin = registration_data.get("screen_0_PIN_4", "").strip()

            # Validate required fields
            if not all([first_name, last_name, user_phone, email, pin]):
                logger.error("Missing required fields in registration data")
                whatsapp_service = WhatsAppService()
                whatsapp_service.send_message(
                    phone_number_id=phone_number_id,
                    recipient_phone=phone,
                    message_text="Registration failed. Please ensure all fields are filled correctly."
                )
                return {"status": "error", "message": "Missing required fields"}

            # Normalize phone numbers
            normalized_user_phone = normalize_ghana_phone_number(user_phone)
            normalized_wa_id = normalize_ghana_phone_number(phone)

            logger.info(f"Phone normalization - Form: {user_phone} -> {normalized_user_phone}")
            logger.info(f"Phone normalization - WhatsApp: {phone} -> {normalized_wa_id}")

            # Check if user already exists
            existing_user = db.query(User).filter(
                (User.phone == normalized_wa_id) | (User.email == email)
            ).first()

            if existing_user:
                logger.warning(f"User already exists: {email} or {normalized_wa_id}")
                whatsapp_service = WhatsAppService()
                whatsapp_service.send_message(
                    phone_number_id=phone_number_id,
                    recipient_phone=phone,
                    message_text="This phone number or email is already registered. Please sign in instead."
                )
                return {"status": "error", "message": "User already exists"}

            # Create user using AuthService
            auth_service = AuthService(db)

            # Generate unique user ID
            user_id = auth_service.generate_user_id()

            # Hash the PIN
            hashed_pin = auth_service.hash_password(pin)

            # Create new user
            new_user = User(
                id=user_id,
                username=email,  # Use email as username
                first_name=first_name,
                last_name=last_name,
                phone=normalized_wa_id,  # Use WhatsApp ID as primary phone
                email=email,
                hashed_pin=hashed_pin,
                enabled=True,  # Enable immediately for WhatsApp users
                created_at=datetime.now()
            )

            db.add(new_user)
            db.commit()
            db.refresh(new_user)

            logger.info(f"User registered successfully: {user_id} - {email}")

            # Send confirmation message
            whatsapp_service = WhatsAppService()
            whatsapp_service.send_message(
                phone_number_id=phone_number_id,
                recipient_phone=phone,
                message_text=f"🎉 Welcome {first_name}! Your registration is complete. You can now start using Lebe."
            )

        except Exception as e:
            logger.error(f"Error processing registration: {e}", exc_info=True)
            db.rollback()

            # Send error message to user
            whatsapp_service = WhatsAppService()
            whatsapp_service.send_message(
                phone_number_id=phone_number_id,
                recipient_phone=phone,
                message_text="Sorry, registration failed. Please try again later."
            )

            return {"status": "error", "message": f"Registration failed: {str(e)}"}

        return {"status": "success", "message": "Flow response processed"}

    elif interactive_type == "button_reply":
        # Handle button replies
        button_reply = interactive.get("button_reply", {})
        button_id = button_reply.get("id")
        button_text = button_reply.get("title")

        logger.info(f"Button clicked: {button_id} - {button_text}")

        # Process button action
        # ...

        return {"status": "success", "message": "Button reply processed"}

    else:
        logger.warning(f"Unsupported interactive type: {interactive_type}")
        return {"status": "ok", "message": f"Unsupported interactive type: {interactive_type}"}


def handle_message_status(value: dict, db: Session):
    """
    Handle message status updates (sent, delivered, read, failed).
    Useful for tracking message delivery and updating your database.
    """
    try:
        statuses = value.get("statuses", [])

        for status_update in statuses:
            message_id = status_update.get("id")
            status_type = status_update.get("status")  # sent, delivered, read, failed
            timestamp = status_update.get("timestamp")
            recipient_id = status_update.get("recipient_id")

            logger.info(f"Message {message_id} to {recipient_id}: {status_type}")

            if status_type == "failed":
                # Handle failed message
                errors = status_update.get("errors", [])
                if errors:
                    error = errors[0]
                    error_code = error.get("code")
                    error_title = error.get("title")
                    logger.error(f"Message failed: {error_code} - {error_title}")

            elif status_type == "read":
                # Message was read by recipient
                logger.info(f"Message {message_id} was read")

            # TODO: Update message status in your database
            # db.query(Message).filter(Message.whatsapp_id == message_id).update({
            #     "status": status_type,
            #     "delivered_at": timestamp if status_type == "delivered" else None,
            #     "read_at": timestamp if status_type == "read" else None
            # })
            # db.commit()

        return {"status": "success", "message": "Status updates processed"}

    except Exception as e:
        logger.error(f"Error handling message status: {e}", exc_info=True)
        raise