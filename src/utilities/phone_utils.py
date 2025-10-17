import re
import logging

logger = logging.getLogger(__name__)

def normalize_ghana_phone_number(phone: str) -> str:
    """
    Normalize Ghanaian phone numbers to international format (233XXXXXXXXX).

    Rules:
    - If 10 digits starting with 0: Remove 0, add 233 prefix
      Example: 0550748724 -> 233550748724
    - If already starts with 233: Keep as is
      Example: 233550748724 -> 233550748724
    - If has + prefix: Remove it
      Example: +233550748724 -> 233550748724

    Args:
        phone: Phone number string (may have spaces, dashes, etc.)

    Returns:
        Normalized phone number in format 233XXXXXXXXX
    """
    if not phone:
        return phone

    # Remove all non-digit characters (spaces, dashes, parentheses, etc.)
    cleaned_phone = re.sub(r'\D', '', phone)

    # If empty after cleaning, return original
    if not cleaned_phone:
        logger.warning(f"Phone number has no digits: {phone}")
        return phone

    # Case 1: 10-digit number starting with 0 (local format)
    # Example: 0550748724 -> 233550748724
    if len(cleaned_phone) == 10 and cleaned_phone.startswith('0'):
        normalized = '233' + cleaned_phone[1:]
        logger.info(f"Normalized phone: {phone} -> {normalized}")
        return normalized

    # Case 2: Already in international format with 233
    # Example: 233550748724 -> 233550748724
    elif cleaned_phone.startswith('233') and len(cleaned_phone) == 12:
        logger.info(f"Phone already normalized: {phone} -> {cleaned_phone}")
        return cleaned_phone

    # Case 3: 9-digit number without leading 0 (partial local format)
    # Example: 550748724 -> 233550748724
    elif len(cleaned_phone) == 9:
        normalized = '233' + cleaned_phone
        logger.info(f"Normalized phone: {phone} -> {normalized}")
        return normalized

    # Case 4: Invalid format - log warning and return cleaned version
    else:
        logger.warning(f"Unexpected phone format: {phone} (cleaned: {cleaned_phone})")
        return cleaned_phone
