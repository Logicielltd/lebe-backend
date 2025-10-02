import uuid
from datetime import datetime


class UniqueIdGenerator:
    @staticmethod
    def generate_short_timestamp() -> str:
        """
        Generate a short timestamp formatted as yyMMddHHmmssSSS
        (year, month, day, hour, minute, second, millisecond)
        """
        now = datetime.now()
        return now.strftime("%y%m%d%H%M%S") + f"{int(now.microsecond / 1000):03d}"

    @staticmethod
    def generate_invoice_id(bill_id: int) -> str:
        """
        Generate an invoice ID with format: INV-{billId}-{timestamp}
        """
        return f"INV-{bill_id}-{UniqueIdGenerator.generate_short_timestamp()}"

    @staticmethod
    def generate_transaction_id(bill_id: int) -> str:
        """
        Generate a transaction ID with format: TID-{billId}-{timestamp}
        """
        return f"TID-{bill_id}-{UniqueIdGenerator.generate_short_timestamp()}"

    @staticmethod
    def extract_transaction_id(transaction_id: str) -> int:
        """
        Extract numeric timestamp part from a transaction ID.
        Format must be: TID-{billId}-{timestamp}
        """
        parts = transaction_id.split("-")
        if len(parts) == 3:
            return int(parts[2])
        else:
            raise ValueError("Invalid Transaction ID format.")

    @staticmethod
    def generate() -> int:
        """
        Generate a positive random long integer using UUID.
        """
        return uuid.uuid4().int & ((1 << 63) - 1)
