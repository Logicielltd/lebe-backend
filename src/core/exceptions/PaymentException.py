from fastapi import HTTPException


class BillNotFoundException(HTTPException):
    def __init__(self, message: str = "Bill not found"):
        super().__init__(status_code=404, detail=message)


class InvoiceNotFoundException(HTTPException):
    def __init__(self, message: str = "Invoice not found"):
        super().__init__(status_code=404, detail=message)


class PaymentGatewayException(HTTPException):
    def __init__(self, message: str = "Payment gateway error"):
        super().__init__(status_code=502, detail=message)


class PaymentNotFoundException(HTTPException):
    def __init__(self, message: str = "Payment not found"):
        super().__init__(status_code=404, detail=message)


class PaymentValidationException(HTTPException):
    def __init__(self, message: str = "Payment validation failed"):
        super().__init__(status_code=400, detail=message)