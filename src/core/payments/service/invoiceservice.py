from datetime import datetime
from typing import Optional, List
from decimal import Decimal
from sqlalchemy.orm import Session
from sqlalchemy import desc
from fastapi import HTTPException, status
from core.payments.model.invoice import Invoice
from core.payments.dto.request.invoicecreate import InvoiceCreate
from core.payments.model.timeline import Timeline
from core.payments.service.billservice import BillService
from core.exceptions.InvoiceException import InvoiceNotFoundException

class InvoiceService:
    def __init__(self, db: Session):
        self.db = db
        self.bill_service = BillService(db)
    
    def create_invoice(self, invoice_data: InvoiceCreate) -> Invoice:
        db_invoice = Invoice(**invoice_data.dict())
        self.db.add(db_invoice)
        self.db.commit()
        self.db.refresh(db_invoice)
        return db_invoice
    
    def get_invoice_by_id(self, id: int) -> Invoice:
        invoice = self.db.query(Invoice).filter(Invoice.id == id).first()
        if not invoice:
            raise InvoiceNotFoundException(f"Invoice not found with id: {id}")
        return invoice
    
    def get_invoice_by_invoice_number(self, invoice_number: str) -> Invoice:
        invoice = self.db.query(Invoice).filter(Invoice.invoice_number == invoice_number).first()
        if not invoice:
            raise InvoiceNotFoundException(f"Invoice not found with invoice number: {invoice_number}")
        return invoice
    
    def get_all_invoices(self, page: int, size: int, timeline: Optional[Timeline] = None) -> List[Invoice]:
        query = self.db.query(Invoice)
        
        if timeline and timeline != Timeline.ALL:
            start_date = self.bill_service.calculate_start_date(timeline)
            query = query.filter(Invoice.created_on >= start_date)
        
        return query.order_by(desc(Invoice.created_on)).offset(page * size).limit(size).all()
    
    def get_all_invoices_paginated(self, page: int, size: int, timeline: Optional[Timeline] = None) -> dict:
        query = self.db.query(Invoice)
        
        if timeline and timeline != Timeline.ALL:
            start_date = self.bill_service.calculate_start_date(timeline)
            query = query.filter(Invoice.created_on >= start_date)
        
        total = query.count()
        invoices = query.order_by(desc(Invoice.created_on)).offset(page * size).limit(size).all()
        
        return {
            "invoices": invoices,
            "total": total,
            "page": page,
            "size": size,
            "has_next": (page + 1) * size < total,
            "has_prev": page > 0
        }