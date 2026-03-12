from typing import List, Optional, Tuple, Dict, Any
from sqlalchemy.orm import Session
from datetime import datetime
import logging
import re
from difflib import SequenceMatcher

from core.payflows.model.payflow import Payflow
from core.user.model.User import User

logger = logging.getLogger(__name__)


class PayflowService:
    """
    Service for managing user payflows (saved payment templates/snapshots).
    A payflow captures successful payment intent sessions with all slots populated.
    Handles CRUD operations and payflow execution.
    """

    def __init__(self, db: Session):
        self.db = db

    def _normalize_name(self, value: str) -> str:
        """Normalize names for comparison"""
        normalized = re.sub(r"\s+", " ", (value or "").strip().lower())
        normalized = re.sub(r"[^a-z0-9 ]", "", normalized)
        return normalized

    def _is_similar_name(self, left: str, right: str) -> bool:
        """Check if two names are similar"""
        left_n = self._normalize_name(left)
        right_n = self._normalize_name(right)
        if not left_n or not right_n:
            return False

        if left_n == right_n:
            return True

        if len(left_n) >= 4 and len(right_n) >= 4 and (left_n in right_n or right_n in left_n):
            return True

        return SequenceMatcher(None, left_n, right_n).ratio() >= 0.86

    def save_payflow(
        self,
        user_id: str,
        name: str,
        intent_name: str,
        slot_values: Dict[str, Any],
        payment_method: Optional[str] = None,
        recipient_phone: Optional[str] = None,
        recipient_name: Optional[str] = None,
        account_number: Optional[str] = None,
        bill_provider: Optional[str] = None,
        last_amount: Optional[str] = None,
        description: Optional[str] = None,
        requires_confirmation: bool = True
    ) -> Tuple[bool, Optional[Payflow], str]:
        """
        Save a new payflow for the user.
        Only called after a successful transaction with complete intent slots.

        Args:
            user_id: User ID
            name: Payflow name
            intent_name: The intent this payflow is for (send_money, buy_airtime, etc.)
            slot_values: Dictionary of all slot values from the intent
            payment_method: Network/method (MTN, VOD, AIR, BNK, etc.)
            recipient_phone: Recipient phone number
            recipient_name: Recipient display name
            account_number: For bill payments
            bill_provider: Provider name for bills
            last_amount: Last amount used
            description: Optional description
            requires_confirmation: Whether confirmation is needed before use

        Returns:
            Tuple of (success, payflow_object, message)
        """
        try:
            # Validate user exists
            user = self.db.query(User).filter(User.id == user_id).first()
            if not user:
                return False, None, f"User {user_id} not found"

            # Check if payflow with same name already exists
            existing = self.db.query(Payflow).filter(
                Payflow.user_id == user_id,
                Payflow.name == name
            ).first()
            
            if existing:
                return False, None, f"Payflow '{name}' already exists for this user"

            # Create new payflow
            payflow = Payflow(
                user_id=user_id,
                name=name,
                description=description,
                intent_name=intent_name,
                slot_values=slot_values,
                payment_method=payment_method,
                recipient_phone=recipient_phone,
                recipient_name=recipient_name,
                account_number=account_number,
                bill_provider=bill_provider,
                last_amount=last_amount,
                requires_confirmation=requires_confirmation,
                is_active=True,
                transaction_count=0
            )

            self.db.add(payflow)
            self.db.commit()
            self.db.refresh(payflow)

            logger.info(f"[PAYFLOW_SERVICE] Payflow saved: {payflow.id} for user {user_id}")
            return True, payflow, f"Payflow '{name}' saved successfully"

        except Exception as e:
            self.db.rollback()
            logger.error(f"[PAYFLOW_SERVICE] Error saving payflow: {str(e)}", exc_info=True)
            return False, None, f"Error saving payflow: {str(e)}"

    def get_payflow_by_id(self, user_id: str, payflow_id: int) -> Optional[Payflow]:
        """Get a specific payflow by ID"""
        return self.db.query(Payflow).filter(
            Payflow.id == payflow_id,
            Payflow.user_id == user_id,
            Payflow.is_active == True
        ).first()

    def get_payflow_by_name(self, user_id: str, payflow_name: str) -> Optional[Payflow]:
        """
        Get payflow by name (exact or similar match).
        
        Args:
            user_id: User ID
            payflow_name: Name to search for
            
        Returns:
            Payflow object or None if not found
        """
        # Try exact match first
        payflow = self.db.query(Payflow).filter(
            Payflow.user_id == user_id,
            Payflow.name == payflow_name,
            Payflow.is_active == True
        ).first()
        
        if payflow:
            return payflow

        # Try similar name match
        all_payflows = self.db.query(Payflow).filter(
            Payflow.user_id == user_id,
            Payflow.is_active == True
        ).all()

        for payflow in all_payflows:
            if self._is_similar_name(payflow.name, payflow_name):
                return payflow

        return None

    def list_payflows(self, user_id: str, intent_filter: Optional[str] = None) -> List[Payflow]:
        """
        List all active payflows for a user.
        
        Args:
            user_id: User ID
            intent_filter: Optional intent to filter by (send_money, buy_airtime, etc.)
            
        Returns:
            List of payflows
        """
        query = self.db.query(Payflow).filter(
            Payflow.user_id == user_id,
            Payflow.is_active == True
        )

        if intent_filter:
            query = query.filter(Payflow.intent_name == intent_filter)

        return query.all()

    def update_payflow(
        self,
        user_id: str,
        payflow_id: int,
        **updates
    ) -> Tuple[bool, Optional[Payflow], str]:
        """
        Update an existing payflow.
        
        Args:
            user_id: User ID
            payflow_id: Payflow ID to update
            **updates: Fields to update
            
        Returns:
            Tuple of (success, payflow_object, message)
        """
        try:
            payflow = self.db.query(Payflow).filter(
                Payflow.id == payflow_id,
                Payflow.user_id == user_id
            ).first()

            if not payflow:
                return False, None, "Payflow not found"

            # Update allowed fields
            allowed_fields = {
                'name', 'description', 'recipient_phone', 'recipient_name',
                'last_amount', 'requires_confirmation', 'is_active'
            }

            for field, value in updates.items():
                if field in allowed_fields:
                    setattr(payflow, field, value)

            payflow.updated_at = datetime.now()
            self.db.commit()
            self.db.refresh(payflow)

            logger.info(f"[PAYFLOW_SERVICE] Payflow updated: {payflow_id}")
            return True, payflow, "Payflow updated successfully"

        except Exception as e:
            self.db.rollback()
            logger.error(f"[PAYFLOW_SERVICE] Error updating payflow: {str(e)}", exc_info=True)
            return False, None, f"Error updating payflow: {str(e)}"

    def delete_payflow(self, user_id: str, payflow_id: int) -> Tuple[bool, str]:
        """
        Soft delete a payflow (mark as inactive).
        
        Args:
            user_id: User ID
            payflow_id: Payflow ID to delete
            
        Returns:
            Tuple of (success, message)
        """
        try:
            payflow = self.db.query(Payflow).filter(
                Payflow.id == payflow_id,
                Payflow.user_id == user_id
            ).first()

            if not payflow:
                return False, "Payflow not found"

            payflow.is_active = False
            payflow.updated_at = datetime.now()
            self.db.commit()

            logger.info(f"[PAYFLOW_SERVICE] Payflow deleted: {payflow_id}")
            return True, "Payflow deleted successfully"

        except Exception as e:
            self.db.rollback()
            logger.error(f"[PAYFLOW_SERVICE] Error deleting payflow: {str(e)}", exc_info=True)
            return False, f"Error deleting payflow: {str(e)}"

    def execute_payflow(
        self,
        user_id: str,
        payflow_id: int,
        override_amount: Optional[str] = None
    ) -> Tuple[bool, Dict[str, Any], str]:
        """
        Prepare a payflow for execution (get slot values ready).
        
        Args:
            user_id: User ID
            payflow_id: Payflow ID to execute
            override_amount: Optional amount to override the saved amount
            
        Returns:
            Tuple of (success, prepared_slots, message)
        """
        try:
            payflow = self.db.query(Payflow).filter(
                Payflow.id == payflow_id,
                Payflow.user_id == user_id,
                Payflow.is_active == True
            ).first()

            if not payflow:
                return False, {}, "Payflow not found or inactive"

            # Prepare slots for execution
            slots = dict(payflow.slot_values)  # Copy saved slots
            
            # Override amount if provided
            if override_amount:
                slots['amount'] = override_amount

            # Update execution stats
            payflow.transaction_count += 1
            payflow.last_used_at = datetime.now()
            self.db.commit()

            logger.info(f"[PAYFLOW_SERVICE] Payflow executed: {payflow_id}")
            return True, slots, "Payflow prepared for execution"

        except Exception as e:
            self.db.rollback()
            logger.error(f"[PAYFLOW_SERVICE] Error executing payflow: {str(e)}", exc_info=True)
            return False, {}, f"Error executing payflow: {str(e)}"
