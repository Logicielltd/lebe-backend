from pydantic import BaseModel
from typing import List, Optional
from core.payments.dto.response.invoiceresponse import InvoiceResponse
from core.payments.model.invoice import Invoice

class PaginatedInvoicesResponse(BaseModel):
    invoices: List[InvoiceResponse]
    total: int
    page: int
    size: int
    has_next: bool
    has_prev: bool