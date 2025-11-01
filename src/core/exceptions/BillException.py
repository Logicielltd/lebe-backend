from fastapi import HTTPException

class BillNotFoundException(HTTPException):
    def __init__(self, message: str = "Bill not found"):
        super().__init__(status_code=404, detail=message)