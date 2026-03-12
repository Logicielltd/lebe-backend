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

    def match_payflow_by_regex(self, user_id: str, user_message: str) -> Optional[Payflow]:
        """
        Match a payflow by checking if the user message contains or matches a payflow name.
        Uses case-insensitive regex pattern matching with two strategies:
        1. Strict: Word boundary matching (preferred for exact payflow names)
        2. Loose: Substring matching (fallback for partial/context-based matches)
        
        The matching strategy:
        1. Get all active payflows for the user
        2. For each payflow name, try strict word-boundary regex match first
        3. If no strict matches, try loose substring matches
        4. Return the longest match to avoid false positives
        
        Args:
            user_id: User ID
            user_message: User's message to check
            
        Returns:
            Matching Payflow object or None if no match found
        """
        if not user_message or not user_message.strip():
            return None
        
        try:
            # Get all active payflows for the user
            payflows = self.db.query(Payflow).filter(
                Payflow.user_id == user_id,
                Payflow.is_active == True
            ).all()
            
            if not payflows:
                logger.debug(f"[PAYFLOW_REGEX_MATCH] No active payflows found for user {user_id}")
                return None
            
            message_lower = user_message.lower()
            strict_matches = []  # Word boundary matches
            loose_matches = []   # Substring matches (fallback)
            
            for payflow in payflows:
                payflow_name = (payflow.name or "").strip()
                if not payflow_name:
                    continue
                
                escaped_name = re.escape(payflow_name)
                payflow_name_lower = payflow_name.lower()
                
                # Strategy 1: Try strict word boundary matching first
                strict_pattern = r"\b" + escaped_name + r"\b"
                try:
                    if re.search(strict_pattern, message_lower, re.IGNORECASE):
                        strict_matches.append((payflow, len(payflow_name)))
                        logger.info(
                            f"[PAYFLOW_REGEX_MATCH] Found STRICT match: payflow_id={payflow.id}, "
                            f"name='{payflow_name}' in message: {user_message[:100]}"
                        )
                        continue
                except re.error as e:
                    logger.warning(f"[PAYFLOW_REGEX_MATCH] Invalid regex pattern for payflow name '{payflow_name}': {e}")
                
                # Strategy 2: If no strict match, try loose substring matching (fallback)
                if payflow_name_lower in message_lower:
                    loose_matches.append((payflow, len(payflow_name)))
                    logger.info(
                        f"[PAYFLOW_REGEX_MATCH] Found LOOSE match: payflow_id={payflow.id}, "
                        f"name='{payflow_name}' (substring) in message: {user_message[:100]}"
                    )
            
            # Prefer strict matches, fall back to loose matches
            matches = strict_matches if strict_matches else loose_matches
            
            if not matches:
                logger.debug(f"[PAYFLOW_REGEX_MATCH] No payflow matched for message: {user_message[:100]}")
                return None
            
            # If multiple matches, prefer the one with the longest name to avoid false positives
            selected_payflow = max(matches, key=lambda x: x[1])[0]
            match_type = "STRICT" if matches == strict_matches else "LOOSE"
            logger.info(
                f"[PAYFLOW_REGEX_MATCH] Selected payflow ({match_type}): {selected_payflow.id} "
                f"(name='{selected_payflow.name}') from {len(matches)} matches"
            )
            return selected_payflow
            
        except Exception as e:
            logger.error(
                f"[PAYFLOW_REGEX_MATCH] Error matching payflow by regex for user {user_id}: {str(e)}",
                exc_info=True
            )
            return None

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
        requires_confirmation: bool = False
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

            # Prepare slots for execution - safely handle slot_values
            slots = {}
            if isinstance(payflow.slot_values, dict):
                slots = payflow.slot_values.copy()
            elif payflow.slot_values is None:
                slots = {}
            elif isinstance(payflow.slot_values, str):
                # Handle case where slot_values was stored as a string (corrupted data)
                logger.warning(f"[PAYFLOW_SERVICE] slot_values is a string for payflow {payflow_id}, attempting recovery...")
                try:
                    import ast
                    slots = ast.literal_eval(payflow.slot_values) if payflow.slot_values else {}
                    logger.info(f"[PAYFLOW_SERVICE] Successfully recovered slot_values from string for payflow {payflow_id}")
                except (ValueError, SyntaxError):
                    logger.error(f"[PAYFLOW_SERVICE] Failed to recover slot_values from string for payflow {payflow_id}")
                    return False, {}, f"Payflow has corrupted slot data. Please recreate it."
            else:
                logger.warning(f"[PAYFLOW_SERVICE] Invalid slot_values type for payflow {payflow_id}: {type(payflow.slot_values)}")
                return False, {}, f"Payflow has corrupted slot data. Please recreate it."
            
            # Ensure slots is a valid dictionary
            if not isinstance(slots, dict):
                logger.error(f"[PAYFLOW_SERVICE] slot_values conversion failed for payflow {payflow_id}")
                return False, {}, "Error preparing payflow data"
            
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
