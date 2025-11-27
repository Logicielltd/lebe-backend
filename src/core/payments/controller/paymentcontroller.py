from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request
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

@payment_routes.post("/send-money")
def send_money_direct(
    amount: Decimal = Query(..., description="Amount in GHS to send"),
    phone_number: str = Query(..., description="Receiver phone number (0XXXXXXXXX or 233XXXXXXXXX)"),
    reference: str = Query("Direct Payout", description="Optional reference description"),
    db: Session = Depends(get_db)
):
    """
    Send money directly to a phone number using MTC (Merchant to Customer).
    No database records created - direct payout to Orchard API.
    Useful for payouts, refunds, or direct transfers.

    Args:
        amount: Amount in GHS to send
        phone_number: Receiver phone number (0XXXXXXXXX or 233XXXXXXXXX format)
        reference: Optional reference description

    Returns:
        - success: Boolean indicating if MTC was sent to gateway
        - transaction_id: MTC transaction ID
        - resp_code: Orchard response code (015 = accepted for processing)
        - message: Status message
        - receiver_phone: Phone number money was sent to
    """
    from utilities.uniqueidgenerator import UniqueIdGenerator
    from utilities.phone_utils import convert_to_local_ghana_format
    from core.beneficiaries.utility.network_detector import NetworkDetector

    try:
        # Validate inputs
        if not amount or amount <= 0:
            raise HTTPException(
                status_code=400,
                detail="Amount must be greater than 0"
            )

        if not phone_number:
            raise HTTPException(
                status_code=400,
                detail="Phone number is required"
            )

        logger.info(f"[SEND_MONEY_DIRECT] Direct MTC payout: Amount={amount}, Phone={phone_number}, Reference={reference}")

        # Generate transaction ID
        mtc_transaction_id = str(UniqueIdGenerator.generate())

        # Detect network from phone
        detected_network, network_message = NetworkDetector.detect_network_from_phone(phone_number)
        logger.info(f"[SEND_MONEY_DIRECT_NETWORK] Phone: {phone_number} -> Network: {detected_network} ({network_message})")

        # Build MTC request
        amount_decimal = Decimal(str(amount))
        mtc_request = {
            "amount": str(amount_decimal.quantize(Decimal('0.00'))),
            "customer_number": convert_to_local_ghana_format(phone_number),
            "exttrid": mtc_transaction_id,
            "nw": detected_network,
            "reference": reference,
            "service_id": "4892",
            "ts": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "callback_url": "https://lebe-dcahe0a8cjecffcm.canadacentral-01.azurewebsites.netapi/api/v1/payment/callback",
            "trans_type": "MTC"
        }

        logger.info(f"[SEND_MONEY_DIRECT_REQUEST] Sending MTC request: {mtc_request}")

        # Send to Orchard API
        payment_service = PaymentService(db)
        response = payment_service.payment_gateway_client.process_payment(mtc_request)

        logger.info(f"[SEND_MONEY_DIRECT_RESPONSE] Orchard response: status_code={response.status_code}")

        if response.status_code == 200:
            response_data = response.json()
            resp_code = response_data.get("resp_code")

            return {
                "success": True,
                "message": f"Payout sent successfully (resp_code: {resp_code})",
                "transaction_id": mtc_transaction_id,
                "resp_code": resp_code,
                "resp_desc": response_data.get("resp_desc"),
                "amount": str(amount),
                "receiver_phone": convert_to_local_ghana_format(phone_number),
                "network": detected_network,
                "reference": reference,
                "timestamp": datetime.now().isoformat()
            }
        else:
            error_msg = response.text
            logger.error(f"[SEND_MONEY_DIRECT_ERROR] Gateway error: {error_msg}")
            raise HTTPException(
                status_code=response.status_code,
                detail=f"Gateway error: {error_msg}"
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error sending money: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error sending money: {str(e)}"
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
        from core.payments.model.payment import Payment
        payment = db.query(Payment).filter(
            (Payment.transaction_id == str(callback_response.trans_ref)) |
            (Payment.ctm_transaction_id == str(callback_response.trans_ref)) |
            (Payment.mtc_transaction_id == str(callback_response.trans_ref))
        ).first()

        if payment:
            from core.payments.model.paymentstatus import PaymentStatus

            status_code = callback_response.trans_status[:3] if callback_response.trans_status else None
            is_success = status_code == "000"

            # Only send notification if payment is not already in terminal state
            # This prevents duplicate notifications if background job already processed it
            if payment.status not in [PaymentStatus.SUCCESS, PaymentStatus.FAILED, PaymentStatus.CTM_FAILED, PaymentStatus.MTC_FAILED]:
                payment_service.send_payment_notification(
                    payment,
                    is_success=is_success,
                    failure_reason=callback_response.message if not is_success else None
                )
                logger.info(f"[CALLBACK_NOTIFICATION] Notification sent for payment {payment.id}")
            else:
                logger.info(f"[CALLBACK_SKIP_NOTIFICATION] Payment {payment.id} already in terminal state {payment.status.name}, skipping duplicate notification")

            # Stop the background check job now that callback has arrived
            # This prevents job from running again if it's still scheduled
            from core.payments.service.payment_check_service import PaymentCheckService
            check_service = PaymentCheckService(db)
            check_service._stop_check_job(payment.id)
            logger.info(f"[CALLBACK_JOB_STOPPED] Background job stopped for payment {payment.id} - callback processed")

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
