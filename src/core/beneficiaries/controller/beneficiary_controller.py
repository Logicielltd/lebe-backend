from fastapi import APIRouter, Depends, HTTPException, status, Path
from sqlalchemy.orm import Session
from typing import List
import logging

from core.beneficiaries.service.beneficiary_service import BeneficiaryService
from core.beneficiaries.dto.beneficiary_dto import BeneficiaryCreateRequest, BeneficiaryResponse
from core.user.controller.usercontroller import validate_token, get_db
from fastapi_jwt_auth import AuthJWT

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

beneficiary_routes = APIRouter()


@beneficiary_routes.post("/add", response_model=BeneficiaryResponse)
def add_beneficiary(
    request: BeneficiaryCreateRequest,
    db: Session = Depends(get_db),
    authjwt: AuthJWT = Depends(validate_token)
):
    """Add a new beneficiary for the authenticated user."""
    try:
        user_id = authjwt.get_jwt_subject()
        logger.info(f"[BENEFICIARY_CONTROLLER] Adding beneficiary for user: {user_id}")

        beneficiary_service = BeneficiaryService(db)
        success, beneficiary, message = beneficiary_service.add_beneficiary(
            user_id=user_id,
            name=request.name,
            customer_number=request.customer_number,
            network=request.network,
            bank_code=request.bank_code
        )

        if not success:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message)

        logger.info(f"[BENEFICIARY_CONTROLLER] Beneficiary added successfully: {beneficiary.id}")
        return BeneficiaryResponse.from_beneficiary(beneficiary)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[BENEFICIARY_CONTROLLER] Error adding beneficiary: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error adding beneficiary: {str(e)}"
        )


@beneficiary_routes.get("/list", response_model=List[BeneficiaryResponse])
def list_beneficiaries(
    db: Session = Depends(get_db),
    authjwt: AuthJWT = Depends(validate_token)
):
    """Get all beneficiaries for the authenticated user."""
    try:
        user_id = authjwt.get_jwt_subject()
        logger.info(f"[BENEFICIARY_CONTROLLER] Listing beneficiaries for user: {user_id}")

        beneficiary_service = BeneficiaryService(db)
        beneficiaries = beneficiary_service.get_beneficiaries(user_id)

        logger.info(f"[BENEFICIARY_CONTROLLER] Found {len(beneficiaries)} beneficiaries")
        return [BeneficiaryResponse.from_beneficiary(b) for b in beneficiaries]

    except Exception as e:
        logger.error(f"[BENEFICIARY_CONTROLLER] Error listing beneficiaries: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving beneficiaries: {str(e)}"
        )


@beneficiary_routes.get("/get/{beneficiary_id}", response_model=BeneficiaryResponse)
def get_beneficiary(
    beneficiary_id: int = Path(..., description="Beneficiary ID"),
    db: Session = Depends(get_db),
    authjwt: AuthJWT = Depends(validate_token)
):
    """Get a specific beneficiary by ID."""
    try:
        user_id = authjwt.get_jwt_subject()
        logger.info(f"[BENEFICIARY_CONTROLLER] Getting beneficiary: {beneficiary_id}")

        beneficiary_service = BeneficiaryService(db)
        beneficiary = beneficiary_service.get_beneficiary(beneficiary_id, user_id)

        if not beneficiary:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Beneficiary not found"
            )

        return BeneficiaryResponse.from_beneficiary(beneficiary)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[BENEFICIARY_CONTROLLER] Error getting beneficiary: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving beneficiary: {str(e)}"
        )


@beneficiary_routes.delete("/delete/{beneficiary_id}")
def delete_beneficiary(
    beneficiary_id: int = Path(..., description="Beneficiary ID"),
    db: Session = Depends(get_db),
    authjwt: AuthJWT = Depends(validate_token)
):
    """Delete a beneficiary."""
    try:
        user_id = authjwt.get_jwt_subject()
        logger.info(f"[BENEFICIARY_CONTROLLER] Deleting beneficiary: {beneficiary_id}")

        beneficiary_service = BeneficiaryService(db)
        success, message = beneficiary_service.delete_beneficiary(beneficiary_id, user_id)

        if not success:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=message)

        logger.info(f"[BENEFICIARY_CONTROLLER] Beneficiary deleted: {beneficiary_id}")
        return {"message": message}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[BENEFICIARY_CONTROLLER] Error deleting beneficiary: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting beneficiary: {str(e)}"
        )


@beneficiary_routes.put("/update/{beneficiary_id}", response_model=BeneficiaryResponse)
def update_beneficiary(
    beneficiary_id: int = Path(..., description="Beneficiary ID"),
    request: BeneficiaryCreateRequest = None,
    db: Session = Depends(get_db),
    authjwt: AuthJWT = Depends(validate_token)
):
    """Update beneficiary details."""
    try:
        user_id = authjwt.get_jwt_subject()
        logger.info(f"[BENEFICIARY_CONTROLLER] Updating beneficiary: {beneficiary_id}")

        beneficiary_service = BeneficiaryService(db)
        success, beneficiary, message = beneficiary_service.update_beneficiary(
            beneficiary_id=beneficiary_id,
            user_id=user_id,
            name=request.name if request else None,
            customer_number=request.customer_number if request else None,
            bank_code=request.bank_code if request else None
        )

        if not success:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message)

        logger.info(f"[BENEFICIARY_CONTROLLER] Beneficiary updated: {beneficiary_id}")
        return BeneficiaryResponse.from_beneficiary(beneficiary)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[BENEFICIARY_CONTROLLER] Error updating beneficiary: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating beneficiary: {str(e)}"
        )
