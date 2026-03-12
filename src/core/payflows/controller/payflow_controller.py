from fastapi import APIRouter, Depends, HTTPException, status, Path
from sqlalchemy.orm import Session
from typing import List
import logging

from core.payflows.service.payflow_service import PayflowService
from core.payflows.dto.payflow_dto import (
    PayflowCreateRequest,
    PayflowUpdateRequest,
    PayflowExecuteRequest,
    PayflowResponse,
    PayflowListResponse
)
from core.user.controller.usercontroller import validate_token, get_db
from fastapi_jwt_auth import AuthJWT

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

payflow_routes = APIRouter()


@payflow_routes.post("/save", response_model=PayflowResponse)
def save_payflow(
    request: PayflowCreateRequest,
    db: Session = Depends(get_db),
    authjwt: AuthJWT = Depends(validate_token)
):
    """
    Save a new payflow after a successful transaction.
    A payflow can only be saved when all required intent slots are available.
    """
    try:
        user_id = authjwt.get_jwt_subject()
        logger.info(f"[PAYFLOW_CONTROLLER] Saving payflow for user: {user_id}, name: {request.name}")

        payflow_service = PayflowService(db)
        success, payflow, message = payflow_service.save_payflow(
            user_id=user_id,
            name=request.name,
            description=request.description,
            intent_name=request.intent_name,
            slot_values=request.slot_values,
            payment_method=request.payment_method,
            recipient_phone=request.recipient_phone,
            recipient_name=request.recipient_name,
            account_number=request.account_number,
            bill_provider=request.bill_provider,
            last_amount=request.last_amount,
            requires_confirmation=request.requires_confirmation
        )

        if not success:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message)

        logger.info(f"[PAYFLOW_CONTROLLER] Payflow saved successfully: {payflow.id}")
        return PayflowResponse.from_payflow(payflow)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[PAYFLOW_CONTROLLER] Error saving payflow: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error saving payflow: {str(e)}"
        )


@payflow_routes.get("/list", response_model=PayflowListResponse)
def list_payflows(
    intent: str = None,
    db: Session = Depends(get_db),
    authjwt: AuthJWT = Depends(validate_token)
):
    """List all payflows for the authenticated user, optionally filtered by intent."""
    try:
        user_id = authjwt.get_jwt_subject()
        logger.info(f"[PAYFLOW_CONTROLLER] Listing payflows for user: {user_id}")

        payflow_service = PayflowService(db)
        payflows = payflow_service.list_payflows(user_id, intent_filter=intent)

        return PayflowListResponse(
            total=len(payflows),
            payflows=[PayflowResponse.from_payflow(pf) for pf in payflows]
        )

    except Exception as e:
        logger.error(f"[PAYFLOW_CONTROLLER] Error listing payflows: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error listing payflows: {str(e)}"
        )


@payflow_routes.get("/{payflow_id}", response_model=PayflowResponse)
def get_payflow(
    payflow_id: int = Path(..., gt=0),
    db: Session = Depends(get_db),
    authjwt: AuthJWT = Depends(validate_token)
):
    """Get details of a specific payflow."""
    try:
        user_id = authjwt.get_jwt_subject()
        logger.info(f"[PAYFLOW_CONTROLLER] Getting payflow: {payflow_id} for user: {user_id}")

        payflow_service = PayflowService(db)
        payflow = payflow_service.get_payflow_by_id(user_id, payflow_id)

        if not payflow:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Payflow not found"
            )

        return PayflowResponse.from_payflow(payflow)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[PAYFLOW_CONTROLLER] Error getting payflow: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error getting payflow: {str(e)}"
        )


@payflow_routes.put("/{payflow_id}", response_model=PayflowResponse)
def update_payflow(
    payflow_id: int = Path(..., gt=0),
    request: PayflowUpdateRequest = None,
    db: Session = Depends(get_db),
    authjwt: AuthJWT = Depends(validate_token)
):
    """Update a payflow's details."""
    try:
        user_id = authjwt.get_jwt_subject()
        logger.info(f"[PAYFLOW_CONTROLLER] Updating payflow: {payflow_id}")

        payflow_service = PayflowService(db)
        
        # Build updates dictionary from non-None fields
        updates = {k: v for k, v in request.dict().items() if v is not None}
        
        success, payflow, message = payflow_service.update_payflow(
            user_id=user_id,
            payflow_id=payflow_id,
            **updates
        )

        if not success:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message)

        return PayflowResponse.from_payflow(payflow)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[PAYFLOW_CONTROLLER] Error updating payflow: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating payflow: {str(e)}"
        )


@payflow_routes.delete("/{payflow_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_payflow(
    payflow_id: int = Path(..., gt=0),
    db: Session = Depends(get_db),
    authjwt: AuthJWT = Depends(validate_token)
):
    """Delete (deactivate) a payflow."""
    try:
        user_id = authjwt.get_jwt_subject()
        logger.info(f"[PAYFLOW_CONTROLLER] Deleting payflow: {payflow_id}")

        payflow_service = PayflowService(db)
        success, message = payflow_service.delete_payflow(user_id, payflow_id)

        if not success:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=message)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[PAYFLOW_CONTROLLER] Error deleting payflow: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting payflow: {str(e)}"
        )


@payflow_routes.post("/{payflow_id}/execute", response_model=dict)
def execute_payflow(
    payflow_id: int = Path(..., gt=0),
    request: PayflowExecuteRequest = None,
    db: Session = Depends(get_db),
    authjwt: AuthJWT = Depends(validate_token)
):
    """
    Execute a payflow and prepare it for payment.
    Returns the prepared slot values for the payment flow.
    """
    try:
        user_id = authjwt.get_jwt_subject()
        logger.info(f"[PAYFLOW_CONTROLLER] Executing payflow: {payflow_id}")

        payflow_service = PayflowService(db)
        success, slots, message = payflow_service.execute_payflow(
            user_id=user_id,
            payflow_id=payflow_id,
            override_amount=request.amount if request else None
        )

        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=message
            )

        return {
            "success": True,
            "message": message,
            "slots": slots
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[PAYFLOW_CONTROLLER] Error executing payflow: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error executing payflow: {str(e)}"
        )
