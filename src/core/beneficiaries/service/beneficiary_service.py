from typing import List, Optional, Tuple
from sqlalchemy.orm import Session
from datetime import datetime
import logging

from core.beneficiaries.model.beneficiary import Beneficiary, AccountType as BeneficiaryAccountType
from core.beneficiaries.utility.network_detector import NetworkDetector, Network, AccountType
from core.user.model.User import User

logger = logging.getLogger(__name__)


class BeneficiaryService:
    """
    Service for managing user beneficiaries (saved payment recipients).
    Handles CRUD operations and network validation.
    """

    def __init__(self, db: Session):
        self.db = db

    def _normalize_phone_like(self, value: str) -> str:
        cleaned = "".join(ch for ch in (value or "") if ch.isdigit())
        if cleaned.startswith("233") and len(cleaned) > 3:
            cleaned = "0" + cleaned[3:]
        elif cleaned and not cleaned.startswith("0") and len(cleaned) == 9:
            cleaned = "0" + cleaned
        return cleaned

    def _resolve_user_db_id(self, user_identifier: str) -> Optional[str]:
        """
        Resolve a user identifier (db id, email, or phone) to the internal `users.id`.
        Beneficiaries uses a FK to `users.id`, so we must persist that value.
        """
        if not user_identifier:
            return None

        # 1) Direct match on primary key
        user = self.db.query(User).filter(User.id == user_identifier).first()
        if user:
            return user.id

        # 2) Email match (common JWT subject choice)
        user = self.db.query(User).filter(User.email == user_identifier).first()
        if user:
            return user.id

        # 3) Phone match (common WhatsApp/user_id choice)
        normalized_phone = self._normalize_phone_like(user_identifier)
        phone_candidates = {user_identifier}
        if normalized_phone:
            phone_candidates.add(normalized_phone)

        user = self.db.query(User).filter(User.phone.in_(list(phone_candidates))).first()
        if user:
            return user.id

        return None

    def add_beneficiary(
        self,
        user_id: str,
        name: str,
        customer_number: str,
        network: Optional[str] = None,
        bank_code: Optional[str] = None
    ) -> Tuple[bool, Beneficiary, str]:
        """
        Add a new beneficiary for the user.

        Args:
            user_id: User ID
            name: Beneficiary name
            customer_number: Mobile money wallet, bank account, or card number
            network: Network (MTN, VOD, AIR, BNK, MAS, VIS). Auto-detected if None
            bank_code: Bank code (required if network is BNK)

        Returns:
            Tuple of (success, beneficiary_object, message)
        """
        try:
            resolved_user_id = self._resolve_user_db_id(user_id)
            if not resolved_user_id:
                return False, None, "User not found. Please log in again."

            logger.info(f"[BENEFICIARY_SERVICE] Adding beneficiary for user: {resolved_user_id}, name: {name}")

            # If network not provided, try to detect it
            if not network:
                detected_network, network_msg = NetworkDetector.detect_network_from_phone(customer_number)
                if not detected_network:
                    return False, None, f"Could not auto-detect network: {network_msg}"
                network = detected_network.value if hasattr(detected_network, "value") else str(detected_network)
                logger.info(f"[BENEFICIARY_SERVICE] Auto-detected network: {network}")
            else:
                network = network.upper()

            # Validate network
            network_enum = getattr(Network, network, None)
            if not network_enum:
                valid_networks = [
                    Network.MTN, Network.VOD, Network.AIR,
                    Network.BNK, Network.MAS, Network.VIS
                ]
                return False, None, f"Invalid network: {network}. Must be one of: {', '.join(valid_networks)}"

            # Validate customer number for this network
            is_valid, validation_msg = NetworkDetector.validate_customer_number(customer_number, network_enum)
            if not is_valid:
                return False, None, f"Invalid customer number for {network}: {validation_msg}"

            # If bank network, validate bank code
            if network_enum == Network.BNK:
                if not bank_code:
                    return False, None, "Bank code is required for bank account beneficiaries"
                is_valid, bank_msg = NetworkDetector.validate_bank_code(bank_code)
                if not is_valid:
                    return False, None, bank_msg
                bank_code = bank_code.upper()

            # Check for duplicates
            existing = self.db.query(Beneficiary).filter(
                Beneficiary.user_id == resolved_user_id,
                Beneficiary.customer_number == customer_number,
                Beneficiary.network == network,
                Beneficiary.is_active == True
            ).first()

            if existing:
                return False, None, f"Beneficiary '{existing.name}' with this {network} account already exists"

            # Determine account type and map to the DB enum values
            detected_account_type = NetworkDetector.determine_account_type(network_enum)
            if isinstance(detected_account_type, str):
                account_type_key = detected_account_type.lower()
            else:
                account_type_key = str(detected_account_type).lower()
            account_type = BeneficiaryAccountType(account_type_key)

            # Create beneficiary
            beneficiary = Beneficiary(
                user_id=resolved_user_id,
                name=name.strip(),
                customer_number=customer_number.strip(),
                network=network,
                bank_code=bank_code.upper() if bank_code else None,
                account_type=account_type
            )

            self.db.add(beneficiary)
            self.db.commit()
            self.db.refresh(beneficiary)

            logger.info(f"[BENEFICIARY_SERVICE] Beneficiary added successfully: ID={beneficiary.id}")
            return True, beneficiary, f"Beneficiary '{name}' ({network}: {customer_number}) saved successfully!"

        except Exception as e:
            self.db.rollback()
            logger.error(f"[BENEFICIARY_SERVICE] Error adding beneficiary: {str(e)}", exc_info=True)
            return False, None, f"Error saving beneficiary: {str(e)}"

    def get_beneficiaries(self, user_id: str) -> List[Beneficiary]:
        """Get all active beneficiaries for a user."""
        try:
            resolved_user_id = self._resolve_user_db_id(user_id)
            if not resolved_user_id:
                return []

            logger.info(f"[BENEFICIARY_SERVICE] Fetching beneficiaries for user: {resolved_user_id}")
            beneficiaries = self.db.query(Beneficiary).filter(
                Beneficiary.user_id == resolved_user_id,
                Beneficiary.is_active == True
            ).all()
            logger.info(f"[BENEFICIARY_SERVICE] Found {len(beneficiaries)} beneficiaries")
            return beneficiaries
        except Exception as e:
            logger.error(f"[BENEFICIARY_SERVICE] Error fetching beneficiaries: {str(e)}", exc_info=True)
            return []

    def get_beneficiary(self, beneficiary_id: int, user_id: str) -> Optional[Beneficiary]:
        """Get a specific beneficiary by ID (with user ownership check)."""
        try:
            resolved_user_id = self._resolve_user_db_id(user_id)
            if not resolved_user_id:
                return None

            logger.info(f"[BENEFICIARY_SERVICE] Fetching beneficiary: {beneficiary_id}")
            beneficiary = self.db.query(Beneficiary).filter(
                Beneficiary.id == beneficiary_id,
                Beneficiary.user_id == resolved_user_id,
                Beneficiary.is_active == True
            ).first()
            return beneficiary
        except Exception as e:
            logger.error(f"[BENEFICIARY_SERVICE] Error fetching beneficiary: {str(e)}", exc_info=True)
            return None

    def delete_beneficiary(self, beneficiary_id: int, user_id: str) -> Tuple[bool, str]:
        """Soft-delete a beneficiary (mark as inactive)."""
        try:
            resolved_user_id = self._resolve_user_db_id(user_id)
            if not resolved_user_id:
                return False, "User not found. Please log in again."

            logger.info(f"[BENEFICIARY_SERVICE] Deleting beneficiary: {beneficiary_id}")
            beneficiary = self.db.query(Beneficiary).filter(
                Beneficiary.id == beneficiary_id,
                Beneficiary.user_id == resolved_user_id
            ).first()

            if not beneficiary:
                return False, "Beneficiary not found"

            beneficiary.is_active = False
            beneficiary.updated_at = datetime.now()
            self.db.commit()

            logger.info(f"[BENEFICIARY_SERVICE] Beneficiary deleted: {beneficiary_id}")
            return True, f"Beneficiary '{beneficiary.name}' removed successfully"

        except Exception as e:
            self.db.rollback()
            logger.error(f"[BENEFICIARY_SERVICE] Error deleting beneficiary: {str(e)}", exc_info=True)
            return False, f"Error removing beneficiary: {str(e)}"

    def update_beneficiary(
        self,
        beneficiary_id: int,
        user_id: str,
        name: Optional[str] = None,
        customer_number: Optional[str] = None,
        bank_code: Optional[str] = None
    ) -> Tuple[bool, Beneficiary, str]:
        """Update beneficiary details."""
        try:
            resolved_user_id = self._resolve_user_db_id(user_id)
            if not resolved_user_id:
                return False, None, "User not found. Please log in again."

            logger.info(f"[BENEFICIARY_SERVICE] Updating beneficiary: {beneficiary_id}")
            beneficiary = self.db.query(Beneficiary).filter(
                Beneficiary.id == beneficiary_id,
                Beneficiary.user_id == resolved_user_id
            ).first()

            if not beneficiary:
                return False, None, "Beneficiary not found"

            # Update name if provided
            if name:
                beneficiary.name = name.strip()

            # Update customer number if provided
            if customer_number:
                network_enum = getattr(Network, beneficiary.network, None)
                if not network_enum:
                    return False, None, f"Invalid stored network on beneficiary: {beneficiary.network}"
                is_valid, validation_msg = NetworkDetector.validate_customer_number(
                    customer_number,
                    network_enum
                )
                if not is_valid:
                    return False, None, f"Invalid customer number: {validation_msg}"
                beneficiary.customer_number = customer_number.strip()

            # Update bank code if provided
            if bank_code and beneficiary.network == "BNK":
                is_valid, bank_msg = NetworkDetector.validate_bank_code(bank_code)
                if not is_valid:
                    return False, None, bank_msg
                beneficiary.bank_code = bank_code.upper()

            beneficiary.updated_at = datetime.now()
            self.db.commit()
            self.db.refresh(beneficiary)

            logger.info(f"[BENEFICIARY_SERVICE] Beneficiary updated: {beneficiary_id}")
            return True, beneficiary, "Beneficiary updated successfully"

        except Exception as e:
            self.db.rollback()
            logger.error(f"[BENEFICIARY_SERVICE] Error updating beneficiary: {str(e)}", exc_info=True)
            return False, None, f"Error updating beneficiary: {str(e)}"

    def format_beneficiary_list(self, beneficiaries: List[Beneficiary]) -> str:
        """Format beneficiary list for WhatsApp display."""
        if not beneficiaries:
            return "You have no saved beneficiaries."

        lines = ["Your beneficiaries:\n"]
        for idx, b in enumerate(beneficiaries, 1):
            account_display = f"{b.network}: {b.customer_number}"
            if b.bank_code:
                account_display += f" ({b.bank_code})"
            lines.append(f"{idx}. {b.name} - {account_display}")

        return "\n".join(lines)
