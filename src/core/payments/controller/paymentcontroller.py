from fastapi import APIRouter, Depends, HTTPException, Path, Request
from fastapi_jwt_auth import AuthJWT
import jwt
from sqlalchemy.orm import Session
from typing import List
from decimal import Decimal
import logging
from fastapi_jwt_auth.exceptions import MissingTokenError

from src.core.exceptions.PaymentException import PaymentNotFoundException
from src.core.payments.dto.paymentdto import PaymentDto
from src.core.payments.dto.response.pagedpaymentresponse import PagedPaymentResponse
from src.core.payments.dto.response.paymentcallbackresponse import PaymentCallbackResponse
from src.core.payments.dto.response.paymentresultresponse import PaymentResultResponse
from src.core.payments.model.paymentmethod import PaymentMethod
from src.core.payments.model.timeline import Timeline
from src.core.payments.service.paymentservice import PaymentService
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