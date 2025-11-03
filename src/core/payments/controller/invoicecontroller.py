import logging
from fastapi import APIRouter, Depends, HTTPException
from fastapi_jwt_auth import AuthJWT
import jwt
from sqlalchemy.orm import Session
import logging
from fastapi_jwt_auth.exceptions import MissingTokenError

from sqlalchemy.orm import Session
from core.payments.service.invoiceservice import InvoiceService
from core.payments.model.timeline import Timeline
from utilities.dbconfig import SessionLocal
from core.payments.dto.response.pagedinvoiceresponse import PaginatedInvoicesResponse
from fastapi_jwt_auth.exceptions import MissingTokenError

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

invoice_routes = APIRouter()

@invoice_routes.get("/{invoice_id}")
def get_invoice_by_id(invoice_id: int, authjwt: AuthJWT = Depends(validate_token), db: Session = Depends(get_db)):
    invoice_service = InvoiceService(db)
    try:
        return invoice_service.get_invoice_by_id(invoice_id)
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))

@invoice_routes.get("/number/{invoice_number}")
def get_by_invoice_number(invoice_number: str, authjwt: AuthJWT = Depends(validate_token), db: Session = Depends(get_db)):
    invoice_service = InvoiceService(db)
    try:
        return invoice_service.get_invoice_by_invoice_number(invoice_number)
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))

@invoice_routes.get("/all/{page}/{size}/{timeline}")
def get_all_invoices(
    page: int,
    size: int,
    timeline: Timeline,
    authjwt: AuthJWT = Depends(validate_token),
    db: Session = Depends(get_db)
):
    invoice_service = InvoiceService(db)
    result = invoice_service.get_all_invoices_paginated(page, size, timeline)
    
    return PaginatedInvoicesResponse(
        invoices=result["invoices"],
        total=result["total"],
        page=result["page"],
        size=result["size"],
        has_next=result["has_next"],
        has_prev=result["has_prev"]
    )