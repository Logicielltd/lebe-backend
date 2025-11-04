from enum import Enum
import re
import logging

logger = logging.getLogger(__name__)


class Network(str, Enum):
    """Network enumeration matching Orchard API spec"""
    MTN = "MTN"
    VOD = "VOD"
    AIR = "AIR"
    BNK = "BNK"
    MAS = "MAS"
    VIS = "VIS"


class AccountType(str, Enum):
    """Account type enumeration"""
    MOBILE_MONEY = "mobile_money"
    BANK_ACCOUNT = "bank_account"
    CARD = "card"


# Valid bank codes in Ghana
BANK_CODES = {
    "RPB": "REPUBLIC BANK",
    "ADB": "ADB",
    "VOD": "VODAFONE CASH",
    "ZEE": "ZEEPAY GHANA",
    "ABS": "ABSA BANK",
    "FNB": "FNB",
    "CBG": "CBG",
    "GHL": "GHL BANK",
    "AIR": "AIRTELTIGO MONEY",
    "UMB": "UMB",
    "SIS": "SERVICES INTEGRITY SAVINGS & LOANS",
    "FBN": "FBN BANK",
    "UBA": "UBA",
    "CAL": "CAL BANK",
    "SGB": "SG",
    "ARB": "APEX BANK",
    "BOG": "BANK OF GHANA",
    "OMN": "OMNI BANK",
    "STB": "STANBIC BANK",
    "FAB": "FAB",
    "NIB": "NIB",
    "GMO": "G-MONEY",
    "BOA": "BOA",
    "ECO": "ECOBANK GHANA",
    "GTB": "GT BANK",
    "MTN": "MTN MOBILE MONEY",
    "FIB": "FIDELITY BANK",
    "ZEB": "ZENITH BANK",
    "SCB": "STANDARD CHARTERED",
    "PRB": "PBL",
    "ACB": "ACCESS BANK",
    "GCB": "GCB BANK",
}


class NetworkDetector:
    """
    Utility class for detecting networks from phone numbers and validating customer numbers.
    Handles Ghana-specific mobile money networks.
    """

    @staticmethod
    def detect_network_from_phone(phone_number: str) -> tuple[Network, str]:
        """
        Detect network from Ghana phone number.

        Returns:
            Tuple of (detected_network, message)

        Example:
            - 024x, 025x, 055x, 056x -> MTN
            - 020x, 050x -> VOD (Vodafone)
            - 027x, 057x -> AIR (AirtelTigo)
        """
        # Remove any non-digit characters
        cleaned = re.sub(r'\D', '', phone_number)

        # Handle country code (if present)
        if cleaned.startswith('233'):
            cleaned = '0' + cleaned[3:]
        elif cleaned.startswith('233'):
            cleaned = '0' + cleaned[3:]

        # Ensure it starts with 0
        if not cleaned.startswith('0'):
            cleaned = '0' + cleaned

        # Extract first 3 digits (0XX)
        prefix = cleaned[:3]

        logger.info(f"[NETWORK_DETECTOR] Detecting network from phone: {phone_number} -> prefix: {prefix}")

        # MTN prefixes
        if prefix in ['024', '025', '055', '056']:
            return Network.MTN, "MTN"

        # Vodafone prefixes
        elif prefix in ['020', '050']:
            return Network.VOD, "Vodafone"

        # AirtelTigo prefixes
        elif prefix in ['027', '057']:
            return Network.AIR, "AirtelTigo"

        else:
            logger.warn(f"[NETWORK_DETECTOR] Unknown network prefix: {prefix}")
            return None, f"Unknown network for phone: {phone_number}"

    @staticmethod
    def validate_customer_number(customer_number: str, network: Network) -> tuple[bool, str]:
        """
        Validate customer number format based on network.

        Returns:
            Tuple of (is_valid, message)
        """
        cleaned = re.sub(r'\D', '', customer_number)

        # Handle country code
        if cleaned.startswith('233'):
            cleaned = '0' + cleaned[3:]
        elif not cleaned.startswith('0'):
            cleaned = '0' + cleaned

        logger.info(f"[NETWORK_DETECTOR] Validating customer_number: {customer_number} for network: {network}")

        # For mobile money networks, validate phone format
        if network in [Network.MTN, Network.VOD, Network.AIR]:
            # Ghana mobile numbers are 10 digits (0 + 9 digits)
            if len(cleaned) == 10 and cleaned.startswith('0'):
                # Verify the prefix matches the network
                prefix = cleaned[:3]

                if network == Network.MTN and prefix in ['024', '025', '055', '056']:
                    return True, "Valid MTN number"
                elif network == Network.VOD and prefix in ['020', '050']:
                    return True, "Valid Vodafone number"
                elif network == Network.AIR and prefix in ['027', '057']:
                    return True, "Valid AirtelTigo number"
                else:
                    return False, f"Phone number prefix doesn't match {network} network"
            else:
                return False, "Invalid phone number format (must be 10 digits starting with 0)"

        elif network == Network.BNK:
            # Bank account numbers - minimal validation
            if len(cleaned) >= 10:
                return True, "Valid bank account number format"
            else:
                return False, "Bank account number too short"

        elif network in [Network.MAS, Network.VIS]:
            # Card numbers - basic validation (16 digits)
            if len(cleaned) == 16:
                return True, "Valid card number format"
            else:
                return False, "Card number must be 16 digits"

        else:
            return False, f"Unknown network: {network}"

    @staticmethod
    def validate_bank_code(bank_code: str) -> tuple[bool, str]:
        """
        Validate bank code against known banks in Ghana.

        Returns:
            Tuple of (is_valid, bank_name_or_error)
        """
        code_upper = bank_code.upper().strip()

        if code_upper in BANK_CODES:
            logger.info(f"[NETWORK_DETECTOR] Bank code {code_upper} validated: {BANK_CODES[code_upper]}")
            return True, BANK_CODES[code_upper]
        else:
            logger.warn(f"[NETWORK_DETECTOR] Unknown bank code: {code_upper}")
            return False, f"Unknown bank code: {code_upper}"

    @staticmethod
    def determine_account_type(network: Network) -> AccountType:
        """
        Determine account type based on network.
        """
        if network in [Network.MTN, Network.VOD, Network.AIR]:
            return AccountType.MOBILE_MONEY
        elif network == Network.BNK:
            return AccountType.BANK_ACCOUNT
        elif network in [Network.MAS, Network.VIS]:
            return AccountType.CARD
        else:
            return AccountType.MOBILE_MONEY  # Default
