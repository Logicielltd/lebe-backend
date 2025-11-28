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

            # Only stop the job if payment is in terminal state
            # If payment is in MTC_PROCESSING or ATP_PROCESSING, job must continue to check status
            if payment.status in [PaymentStatus.SUCCESS, PaymentStatus.FAILED, PaymentStatus.CTM_FAILED, PaymentStatus.MTC_FAILED, PaymentStatus.ATP_FAILED]:
                from core.payments.service.payment_check_service import PaymentCheckService
                check_service = PaymentCheckService(db)
                check_service._stop_check_job(payment.id)
                logger.info(f"[CALLBACK_JOB_STOPPED] Background job stopped for payment {payment.id} - payment in terminal state {payment.status.name}")
            elif payment.status == PaymentStatus.MTC_PROCESSING:
                logger.info(f"[CALLBACK_JOB_CONTINUING] Payment {payment.id} now in MTC_PROCESSING state, job will continue to check MTC status")
            elif payment.status == PaymentStatus.ATP_PROCESSING:
                logger.info(f"[CALLBACK_JOB_CONTINUING] Payment {payment.id} now in ATP_PROCESSING state, job will continue to check ATP status")

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

# Test endpoints for debugging/Postman testing
@payment_routes.get("/balance-check")
def balance_check(db: Session = Depends(get_db)):
    """
    Test endpoint to check merchant wallet balance.
    Returns wallet balance for all transaction types (payout, airtime, billpay, etc.)

    Response includes:
    - sms_bal: SMS balance
    - payout_bal: Balance available for MTC (money transfer)
    - billpay_bal: Balance for bill payments
    - available_collect_bal: Available collection balance
    - airtime_bal: Balance for airtime top-up
    - actual_collect_bal: Actual collection balance
    """
    try:
        logger.info("[TEST_BALANCE_CHECK] Testing wallet balance check endpoint")
        payment_service = PaymentService(db)

        # Build balance check request (BLC - Balance Check)
        balance_check_request = {
            "service_id": payment_service.service_id,
            "trans_type": "BLC",
            "ts": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

        logger.info(f"[TEST_BALANCE_CHECK_REQUEST] Request: {balance_check_request}")

        # Call Orchard API
        http_response = payment_service.payment_gateway_client.process_payment(balance_check_request)

        logger.info(f"[TEST_BALANCE_CHECK_RESPONSE] Status: {http_response.status_code}, Body: {http_response.text}")

        if http_response.status_code == 200:
            balance_data = http_response.json()
            return {
                "status": "success",
                "http_status": http_response.status_code,
                "data": balance_data
            }
        else:
            error_data = http_response.json()
            return {
                "status": "error",
                "http_status": http_response.status_code,
                "data": error_data
            }

    except Exception as e:
        logger.error(f"[TEST_BALANCE_CHECK_ERROR] Error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error checking balance: {str(e)}")

@payment_routes.post("/account-inquiry")
def account_inquiry(
    customer_number: str = Query(..., description="Customer phone number (e.g., 233200018204)"),
    network: str = Query(..., description="Network code (e.g., MTN, VOD, AIR, BNK)"),
    bank_code: str = Query(None, description="Bank code (required for BNK network)"),
    db: Session = Depends(get_db)
):
    """
    Test endpoint for Account Information Inquiry (AII).
    Use this to verify account details before initiating transactions.

    Parameters:
    - customer_number: Phone number or account number (e.g., 233200018204)
    - network: Network/Bank code (MTN, VOD, AIR for mobile, BNK for bank)
    - bank_code: Bank code if network is BNK (e.g., VOD for a specific bank)

    Example:
    POST /api/v1/payment/test/account-inquiry?customer_number=233200018204&network=BNK&bank_code=VOD
    """
    try:
        logger.info(f"[TEST_ACCOUNT_INQUIRY] Testing account inquiry for {customer_number} on {network}")
        payment_service = PaymentService(db)

        from utilities.uniqueidgenerator import UniqueIdGenerator

        # Build account inquiry request
        account_inquiry_request = {
            "service_id": payment_service.service_id,
            "trans_type": "AII",
            "customer_number": customer_number,
            "nw": network,
            "exttrid": str(UniqueIdGenerator.generate()),
            "ts": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

        # Add bank code if provided and network is BNK
        if network == "BNK" and bank_code:
            account_inquiry_request["bank_code"] = bank_code

        logger.info(f"[TEST_ACCOUNT_INQUIRY_REQUEST] Request: {account_inquiry_request}")

        # Call Orchard API
        http_response = payment_service.payment_gateway_client.process_payment(account_inquiry_request)

        logger.info(f"[TEST_ACCOUNT_INQUIRY_RESPONSE] Status: {http_response.status_code}, Body: {http_response.text}")

        if http_response.status_code == 200:
            account_data = http_response.json()
            return {
                "status": "success",
                "http_status": http_response.status_code,
                "customer_number": customer_number,
                "network": network,
                "data": account_data
            }
        else:
            error_data = http_response.json()
            return {
                "status": "error",
                "http_status": http_response.status_code,
                "customer_number": customer_number,
                "network": network,
                "data": error_data
            }

    except Exception as e:
        logger.error(f"[TEST_ACCOUNT_INQUIRY_ERROR] Error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error during account inquiry: {str(e)}")
