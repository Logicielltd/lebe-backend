import re
import logging

logger = logging.getLogger(__name__)


class Network:
    """Network type enumeration"""
    # Mobile Networks
    MTN = "MTN"
    VOD = "VOD"  # Vodafone/Telecel
    AIR = "AIR"  # AirtelTigo (includes former Glo)

    # Payment Networks
    BNK = "BNK"  # Bank
    MAS = "MAS"  # Mastercard
    VIS = "VIS"  # Visa

    # Telco Billers (telecommunications services)
    GOT = "GOT"  # GoTV
    DST = "DST"  # DStv
    MPP = "MPP"  # MTN Prepaid Data
    VPP = "VPP"  # Vodafone Prepaid Data
    STT = "STT"  # Startimes
    VBB = "VBB"  # Vodafone Broadband (ADSL)

    # External Biller System (non-telco bills)
    ABS = "ABS"  # Abstract Biller System (ECG, schools, institutions, etc.)


class AccountType:
    """Account type enumeration"""
    MOBILE_MONEY = "MOBILE_MONEY"
    BANK_ACCOUNT = "BANK_ACCOUNT"
    CARD = "CARD"


# Ghana Bank Codes and Mobile Money Wallets
BANK_CODES = {
    # Banks
    'GCB': 'GCB Bank',
    'CBG': 'Consolidated Bank Ghana',
    'FIB': 'Fidelity Bank',
    'ECO': 'Ecobank Ghana',
    'SCB': 'Standard Chartered',
    'ADB': 'ADB',
    'NIB': 'NIB',
    'CAL': 'CAL Bank',
    'UBA': 'UBA',
    'GTB': 'GT Bank',
    'PRB': 'PBL',  # Prudential Bank Limited
    'ZEB': 'Zenith Bank',
    'STB': 'Stanbic Bank',
    'ABS': 'ABSA Bank',
    'FNB': 'FNB',
    'RPB': 'Republic Bank',
    'BOA': 'BOA',
    'OMN': 'Omni Bank',
    'ARB': 'Apex Bank',
    'ACB': 'Access Bank',
    'SIS': 'Services Integrity Savings & Loans',
    'FAB': 'FAB',
    'BOG': 'Bank of Ghana',
    'UMB': 'UMB',
    'SGB': 'SG',
    'GHL': 'GHL Bank',
    'FBN': 'FBN Bank',
    # Mobile Money Wallets
    'MTN': 'MTN Mobile Money',
    'VOD': 'Vodafone Cash',
    'AIR': 'AirtelTigo Money',
    'ZEE': 'Zeepay Ghana',
    'GMO': 'G-Money',
}


class NetworkDetector:
    """
    Utility class for detecting networks from phone numbers and validating customer numbers.
    Handles Ghana-specific mobile money networks.
    """

    # Network prefix mappings for Ghana
    NETWORK_PREFIXES = {
        Network.MTN: ['024', '025', '053', '054', '055', '059'],
        Network.VOD: ['020', '050'],
        Network.AIR: ['023', '026', '027', '056', '057', '058'],  # Includes former Glo (023, 058)
    }

    @staticmethod
    def detect_network_from_phone(phone_number: str) -> tuple:
        """
        Detect network from Ghana phone number.

        Args:
            phone_number: Phone number to detect network from

        Returns:
            Tuple of (detected_network, message)

        Example:
            - 024x, 025x, 053x, 054x, 055x, 059x -> MTN
            - 020x, 050x -> VOD (Vodafone/Telecel)
            - 023x, 026x, 027x, 056x, 057x, 058x -> AIR (AirtelTigo, includes former Glo)
        """
        # Input validation
        if not phone_number:
            logger.warning("[NETWORK_DETECTOR] Empty phone number provided")
            return None, "Phone number cannot be empty"

        # Remove any non-digit characters
        cleaned = re.sub(r'\D', '', phone_number)

        if not cleaned:
            logger.warning(f"[NETWORK_DETECTOR] No valid digits in phone number: {phone_number}")
            return None, "No valid digits in phone number"

        # Handle country code (if present)
        if cleaned.startswith('233') and len(cleaned) > 3:
            cleaned = '0' + cleaned[3:]
        elif not cleaned.startswith('0'):
            cleaned = '0' + cleaned

        # Validate length before extracting prefix
        if len(cleaned) < 3:
            logger.warning(f"[NETWORK_DETECTOR] Phone number too short: {phone_number}")
            return None, f"Phone number too short: {phone_number}"

        # Extract first 3 digits (0XX)
        prefix = cleaned[:3]

        logger.info(f"[NETWORK_DETECTOR] Detecting network from phone: {phone_number} -> prefix: {prefix}")

        # Check against all network prefixes
        for network, prefixes in NetworkDetector.NETWORK_PREFIXES.items():
            if prefix in prefixes:
                network_name = {
                    Network.MTN: "MTN",
                    Network.VOD: "Vodafone",
                    Network.AIR: "AirtelTigo",
                }.get(network, network)
                
                logger.info(f"[NETWORK_DETECTOR] Detected network: {network_name}")
                return network, network_name

        # Unknown prefix
        logger.warning(f"[NETWORK_DETECTOR] Unknown network prefix: {prefix}")
        return None, f"Unknown network for phone: {phone_number} (prefix: {prefix})"

    @staticmethod
    def validate_customer_number(customer_number: str, network: Network) -> tuple:
        """
        Validate customer number format based on network.

        Args:
            customer_number: Customer account/phone number
            network: Network type

        Returns:
            Tuple of (is_valid, message)
        """
        if not customer_number:
            return False, "Customer number cannot be empty"

        if not network:
            return False, "Network must be specified"

        cleaned = re.sub(r'\D', '', customer_number)

        if not cleaned:
            return False, "No valid digits in customer number"

        # Handle country code
        if cleaned.startswith('233') and len(cleaned) > 3:
            cleaned = '0' + cleaned[3:]
        elif not cleaned.startswith('0') and network in [Network.MTN, Network.VOD, Network.AIR]:
            cleaned = '0' + cleaned

        logger.info(f"[NETWORK_DETECTOR] Validating customer_number: {customer_number} for network: {network}")

        # For mobile money networks, validate phone format
        if network in [Network.MTN, Network.VOD, Network.AIR]:
            # Ghana mobile numbers are 10 digits (0 + 9 digits)
            if len(cleaned) != 10:
                return False, "Invalid phone number format (must be 10 digits starting with 0)"

            if not cleaned.startswith('0'):
                return False, "Phone number must start with 0"

            # Verify the prefix matches the network
            prefix = cleaned[:3]

            # Check if prefix matches the specified network
            if network in NetworkDetector.NETWORK_PREFIXES:
                if prefix in NetworkDetector.NETWORK_PREFIXES[network]:
                    network_names = {
                        Network.MTN: "MTN",
                        Network.VOD: "Vodafone",
                        Network.AIR: "AirtelTigo",
                    }
                    return True, f"Valid {network_names.get(network, network)} number"
                else:
                    return False, f"Phone number prefix doesn't match {network} network"
            else:
                return False, f"Unknown mobile network: {network}"

        elif network == Network.BNK:
            # Bank account numbers - minimal validation
            if len(cleaned) >= 10 and len(cleaned) <= 20:
                return True, "Valid bank account number format"
            else:
                return False, "Bank account number must be between 10-20 digits"

        elif network in [Network.MAS, Network.VIS]:
            # Card numbers - basic validation (16 digits)
            if len(cleaned) == 16:
                return True, "Valid card number format"
            else:
                return False, "Card number must be 16 digits"

        else:
            return False, f"Unknown network: {network}"

    @staticmethod
    def validate_bank_code(bank_code: str) -> tuple:
        """
        Validate bank code against known banks in Ghana.

        Args:
            bank_code: Bank code to validate

        Returns:
            Tuple of (is_valid, bank_name_or_error)
        """
        if not bank_code:
            return False, "Bank code cannot be empty"

        code_upper = bank_code.upper().strip()

        if code_upper in BANK_CODES:
            logger.info(f"[NETWORK_DETECTOR] Bank code {code_upper} validated: {BANK_CODES[code_upper]}")
            return True, BANK_CODES[code_upper]
        else:
            logger.warning(f"[NETWORK_DETECTOR] Unknown bank code: {code_upper}")
            return False, f"Unknown bank code: {code_upper}"

    @staticmethod
    def determine_account_type(network: Network) -> AccountType:
        """
        Determine account type based on network.

        Args:
            network: Network type

        Returns:
            AccountType enum value
        """
        if network in [Network.MTN, Network.VOD, Network.AIR]:
            return AccountType.MOBILE_MONEY
        elif network == Network.BNK:
            return AccountType.BANK_ACCOUNT
        elif network in [Network.MAS, Network.VIS]:
            return AccountType.CARD
        else:
            logger.warning(f"[NETWORK_DETECTOR] Unknown network type: {network}, defaulting to MOBILE_MONEY")
            return AccountType.MOBILE_MONEY  # Default

    @staticmethod
    def get_all_supported_prefixes() -> dict:
        """
        Get all supported network prefixes.

        Returns:
            Dictionary mapping network to list of prefixes
        """
        return NetworkDetector.NETWORK_PREFIXES.copy()

    @staticmethod
    def is_valid_ghana_phone(phone_number: str) -> bool:
        """
        Quick check if a phone number is a valid Ghana mobile number.

        Args:
            phone_number: Phone number to validate

        Returns:
            True if valid Ghana mobile number, False otherwise
        """
        network, _ = NetworkDetector.detect_network_from_phone(phone_number)
        return network is not None