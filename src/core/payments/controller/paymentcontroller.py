from fastapi import APIRouter, Depends, HTTPException, Path, Request
from fastapi_jwt_auth import AuthJWT
import jwt
from sqlalchemy.orm import Session
from typing import List
from decimal import Decimal
import logging
from fastapi_jwt_auth.exceptions import MissingTokenError
from datetime import datetime

from core.exceptions.PaymentException import PaymentNotFoundException
from core.payments.dto.paymentdto import PaymentDto
from core.payments.dto.response.pagedpaymentresponse import PagedPaymentResponse
from core.payments.dto.response.paymentcallbackresponse import PaymentCallbackResponse
from core.payments.dto.response.paymentresultresponse import PaymentResultResponse
from core.payments.model.paymentmethod import PaymentMethod
from core.payments.model.timeline import Timeline
from core.payments.service.paymentservice import PaymentService
from utilities.dbconfig import SessionLocal


logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def validate_token(authjwt: AuthJWT = Depends()):
    try:
        authjwt.jwt_required()
        return authjwt
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=401, 
            detail="Token expired. Please log in again."
        )
    except MissingTokenError:
        raise HTTPException(
            status_code=401,
            detail="No token found. Please create an account and log in.",
        )
    except Exception as e:
        logger.error(f"Token validation error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=401,
            detail=f"Invalid token: {str(e)}"
        )

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
        
payment_routes = APIRouter()

@payment_routes.post("pay", response_model=PaymentResultResponse)
def create_payment(
    payment: PaymentDto,
    request: Request,
    db: Session = Depends(get_db),
    authjwt: AuthJWT = Depends(validate_token)
):
    payment_service = PaymentService(db)
    return payment_service.make_payment(payment, request)

@payment_routes.get("/get-payment-by-id/{id}", response_model=PaymentDto)
def get_payment_by_id(
    id: int = Path(..., description="Payment ID"),
    db: Session = Depends(get_db),
    authjwt: AuthJWT = Depends(validate_token)
):
    payment_service = PaymentService(db)
    return payment_service.get_payment_by_id(id)

@payment_routes.get("/get-all-payment/{page}/{size}/{timeline}", response_model=PagedPaymentResponse)
def get_all_payments(
    page: int = Path(..., description="Page number"),
    size: int = Path(..., description="Page size"),
    timeline: Timeline = Path(..., description="Timeline filter"),
    db: Session = Depends(get_db),
    authjwt: AuthJWT = Depends(validate_token)
):
    payment_service = PaymentService(db)
    return payment_service.get_all_payments(page, size, timeline)


@payment_routes.get("/method/{payment_method}", response_model=List[PaymentDto])
def get_payments_by_method(
    payment_method: PaymentMethod = Path(..., description="Payment method"),
    db: Session = Depends(get_db),
    authjwt: AuthJWT = Depends(validate_token)
):
    payment_service = PaymentService(db)
    return payment_service.get_payments_by_method(payment_method)

@payment_routes.get("/revenue", response_model=Decimal)
def get_total_revenue(
    db: Session = Depends(get_db),
    authjwt: AuthJWT = Depends(validate_token)
):
    payment_service = PaymentService(db)
    return payment_service.get_total_revenue()

@payment_routes.get("/revenue/{timeline}", response_model=Decimal)
def get_total_revenue_within_timeline(
    timeline: Timeline = Path(..., description="Timeline filter"),
    db: Session = Depends(get_db),
    authjwt: AuthJWT = Depends(validate_token)
):
    payment_service = PaymentService(db)
    return payment_service.get_total_revenue_within_timeline(timeline)

@payment_routes.get("/service/{service_name}", response_model=List[PaymentDto])
def get_payments_by_service_name(
    service_name: str = Path(..., description="Service name"),
    db: Session = Depends(get_db),
    authjwt: AuthJWT = Depends(validate_token)
):
    payment_service = PaymentService(db)
    return payment_service.get_payments_by_service_name(service_name)

@payment_routes.get("/customer/{customer_name}", response_model=List[PaymentDto])
def get_payments_by_customer_name(
    customer_name: str = Path(..., description="Customer name"),
    db: Session = Depends(get_db),
    authjwt: AuthJWT = Depends(validate_token)
):
    payment_service = PaymentService(db)
    return payment_service.get_payments_by_customer_name(customer_name)

@payment_routes.get("/status/{transaction_id}")
def get_payment_status(
    transaction_id: str = Path(..., description="Transaction ID to check status"),
    db: Session = Depends(get_db),
    authjwt: AuthJWT = Depends(validate_token)
):
    """
    Check the status of a payment by transaction ID.
    Useful when user wants to verify if their payment was completed.

    Returns:
    - PENDING: Payment request accepted, awaiting processing confirmation
    - SUCCESS: Payment completed successfully
    - FAILED: Payment failed
    """
    from core.payments.model.payment import Payment

    try:
        payment = db.query(Payment).filter(Payment.transaction_id == transaction_id).first()

        if not payment:
            raise HTTPException(
                status_code=404,
                detail=f"No payment found with transaction ID: {transaction_id}"
            )

        return {
            "transaction_id": payment.transaction_id,
            "payment_id": payment.id,
            "status": payment.status,
            "amount": payment.amount_paid,
            "payment_method": payment.payment_method,
            "created_at": payment.date_paid,
            "updated_at": payment.updated_on
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error checking payment status for transaction {transaction_id}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Error checking payment status. Please try again."
        )

@payment_routes.post("/callback")
def handle_payment_callback(
    callback_response: PaymentCallbackResponse,
    db: Session = Depends(get_db)
):
    logger.debug(f"Callback payload: {callback_response}")

    if callback_response.trans_ref is None:
        logger.error("Missing trans_ref in callback")
        raise HTTPException(status_code=400, detail="trans_ref is required")

    try:
        payment_service = PaymentService(db)
        payment_service.process_payment_callback(callback_response)
        logger.info(f"Callback processed successfully for transaction: {callback_response.trans_ref}")

        # Send WhatsApp notification after successful callback processing
        _send_payment_notification_to_user(callback_response, db)

        return {"message": "Callback processed successfully"}
    except PaymentNotFoundException as ex:
        logger.error(f"Payment not found for transaction: {callback_response.trans_ref}", exc_info=True)
        raise HTTPException(status_code=404, detail=f"Payment record not found for reference: {callback_response.trans_ref}")
    except ValueError as ex:
        logger.error(f"Invalid callback data: {ex}")
        raise HTTPException(status_code=400, detail=str(ex))
    except Exception as ex:
        logger.error("Unexpected error during callback processing", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to process callback. Please try again or contact support.")


def _send_payment_notification_to_user(callback_response: PaymentCallbackResponse, db: Session):
    """
    Generate receipt and send WhatsApp notification to user after payment callback

    Args:
        callback_response: The payment callback response
        db: Database session
    """
    import os
    from datetime import datetime
    from core.webhooks.service.whatsapp_service import WhatsAppService
    from core.payments.model.payment import Payment
    from core.nlu.nlu import LebeNLUSystem
    from utilities.phone_utils import normalize_ghana_phone_number

    try:
        # Get WhatsApp phone number ID from environment
        phone_number_id = os.getenv("WHATSAPP_PHONE_NUMBER_ID")
        if not phone_number_id:
            logger.warning("WHATSAPP_PHONE_NUMBER_ID not set in environment variables")
            return

        # Get payment record
        payment = db.query(Payment).filter(
            Payment.transaction_id == str(callback_response.trans_ref)
        ).first()

        if not payment:
            logger.error(f"Payment not found for notification: {callback_response.trans_ref}")
            return

        # Normalize phone number for WhatsApp (must be in format 233XXXXXXXXX)
        normalized_phone = normalize_ghana_phone_number(payment.phone_number)

        # Determine status from callback
        status_code = callback_response.trans_status[:3] if callback_response.trans_status else None
        is_success = status_code == "000"

        # Initialize WhatsApp service
        whatsapp_service = WhatsAppService()

        if is_success:
            # Generate receipt using NLU system's method
            # Use the intent stored in the payment record
            intent = payment.intent or "payment"

            # Use NLU's receipt generation method
            nlu_system = LebeNLUSystem()
            receipt_url = nlu_system.generate_receipt_after_payment(
                transaction_id=payment.transaction_id,
                user_id=payment.phone_number,
                intent=intent,
                amount=payment.amount_paid,
                status='SUCCESS',
                sender=payment.phone_number,
                receiver=payment.phone_number,
                payment_method=payment.payment_method.name,
                timestamp=payment.updated_on or datetime.now()
            )

            # Send receipt image with caption containing all transaction details
            success_caption = (
                f"✅ Payment Successful!\n\n"
                f"{payment.service_name}\n"
                f"Amount: GHS {payment.amount_paid}\n"
                f"Transaction ID: {payment.transaction_id}"
            )

            whatsapp_service.send_message_receipt(
                phone_number_id=phone_number_id,
                recipient_phone=normalized_phone,
                image_url=receipt_url,
                caption=success_caption
            )

        else:
            # Generate failure receipt using NLU system's method
            # Use the intent stored in the payment record
            intent = payment.intent or "payment"

            # Use NLU's receipt generation method with FAILED status
            nlu_system = LebeNLUSystem()
            receipt_url = nlu_system.generate_receipt_after_payment(
                transaction_id=payment.transaction_id,
                user_id=payment.phone_number,
                intent=intent,
                amount=payment.amount_paid,
                status='FAILED',
                sender=payment.phone_number,
                receiver=payment.phone_number,
                payment_method=payment.payment_method.name,
                timestamp=payment.updated_on or datetime.now()
            )

            # Send failure receipt image with caption
            failure_caption = (
                f"❌ Payment Failed\n\n"
                f"{payment.service_name}\n"
                f"Amount: GHS {payment.amount_paid}\n"
                f"Transaction ID: {payment.transaction_id}\n\n"
                f"Reason: {callback_response.message}\n\n"
                f"Please try again or contact support if the issue persists."
            )

            whatsapp_service.send_message_receipt(
                phone_number_id=phone_number_id,
                recipient_phone=normalized_phone,
                image_url=receipt_url,
                caption=failure_caption
            )

    except Exception as e:
        logger.error(f"[CALLBACK] Error sending payment notification: {str(e)}", exc_info=True)
        # Don't raise exception - notification failure shouldn't break callback processing