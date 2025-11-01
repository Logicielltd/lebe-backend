from fastapi import HTTPException

class InvoiceNotFoundException(HTTPException):
    def __init__(self, message: str = "Invoice not found"):
        super().__init__(status_code=404, detail=message)