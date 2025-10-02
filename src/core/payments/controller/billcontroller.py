from fastapi import APIRouter, Depends, HTTPException
from fastapi_jwt_auth import AuthJWT
import jwt
from sqlalchemy.orm import Session
import logging
from fastapi_jwt_auth.exceptions import MissingTokenError

from sqlalchemy.orm import Session
from core.payments.service.billservice import BillService
from core.payments.model.bill import BillStatus, BillingType
from core.payments.model.timeline import Timeline
from core.payments.dto.request.billcreate import BillCreate
from core.payments.dto.request.billupdate import BillUpdate
from utilities.dbconfig import SessionLocal
from core.payments.dto.response.pagedbillresponse import PaginatedBillsResponse
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

bill_routes = APIRouter()

@bill_routes.post("/")
def create_bill(bill_data: BillCreate, authjwt: AuthJWT = Depends(validate_token), db: Session = Depends(get_db)):
    bill_service = BillService(db)
    try:
        bill_id = bill_service.create_bill(bill_data)
        return {"id": bill_id}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@bill_routes.get("/{bill_id}")
def get_bill_by_id(bill_id: int, authjwt: AuthJWT = Depends(validate_token), db: Session = Depends(get_db)):
    bill_service = BillService(db)
    try:
        return bill_service.get_bill_by_id(bill_id)
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))

@bill_routes.delete("/{bill_id}")
def delete_bill(bill_id: int, authjwt: AuthJWT = Depends(validate_token), db: Session = Depends(get_db)):
    bill_service = BillService(db)
    try:
        bill_service.delete_bill(bill_id)
        return {"message": "Bill deleted successfully"}
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))

@bill_routes.put("/update-bill")
def update_bill(bill_data: BillUpdate, authjwt: AuthJWT = Depends(validate_token), db: Session = Depends(get_db)):
    bill_service = BillService(db)
    try:
        return bill_service.update_bill(bill_data.id, bill_data)
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))

@bill_routes.get("/all/{page}/{size}/{timeline}")
def get_all_bills(
    page: int,
    size: int,
    timeline: Timeline,
    authjwt: AuthJWT = Depends(validate_token),
    db: Session = Depends(get_db)
):
    bill_service = BillService(db)
    result = bill_service.get_all_bills_paginated(page, size, timeline)
    
    return PaginatedBillsResponse(
        bills=result["bills"],
        total=result["total"],
        page=result["page"],
        size=result["size"],
        has_next=result["has_next"],
        has_prev=result["has_prev"]
    )

@bill_routes.get("/find-by/{service_name}")
def get_bills_by_service_name(service_name: str, authjwt: AuthJWT = Depends(validate_token), db: Session = Depends(get_db)):
    bill_service = BillService(db)
    return bill_service.find_bill_by_service_name(service_name)

@bill_routes.get("/by-status/{status}")
def get_bills_by_status(status: BillStatus, authjwt: AuthJWT = Depends(validate_token), db: Session = Depends(get_db)):
    bill_service = BillService(db)
    return bill_service.find_bills_by_status(status)

@bill_routes.get("/by-type/{billing_type}")
def get_bills_by_billing_type(billing_type: BillingType, authjwt: AuthJWT = Depends(validate_token), db: Session = Depends(get_db)):
    bill_service = BillService(db)
    return bill_service.find_bills_by_billing_type(billing_type)

@bill_routes.get("/find-by-form_id/{form_id}")
def get_bill_by_form_id(form_id: int, authjwt: AuthJWT = Depends(validate_token), db: Session = Depends(get_db)):
    bill_service = BillService(db)
    try:
        return bill_service.find_bill_by_form_id(form_id)
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))

@bill_routes.delete("/delete-by-form_id/{form_id}")
def delete_bill_by_form_id(form_id: int, authjwt: AuthJWT = Depends(validate_token), db: Session = Depends(get_db)):
    bill_service = BillService(db)
    try:
        bill_service.delete_bill_by_form_id(form_id)
        return {"message": "Bill deleted successfully"}
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))