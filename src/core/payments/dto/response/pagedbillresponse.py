from pydantic import BaseModel
from typing import List
from core.payments.dto.response.billresponse import BillResponse

class PaginatedBillsResponse(BaseModel):
    bills: List[BillResponse]
    total: int
    page: int
    size: int
    has_next: bool
    has_prev: bool