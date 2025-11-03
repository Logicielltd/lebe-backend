from datetime import datetime, timedelta
from typing import Optional, List
from decimal import Decimal
from sqlalchemy.orm import Session
from sqlalchemy import desc
from fastapi import HTTPException
from core.payments.model.bill import Bill, BillStatus, BillingType
from core.payments.dto.request.billcreate import BillCreate
from core.payments.dto.request.billupdate import BillUpdate
from core.exceptions.BillException import BillNotFoundException
from core.payments.model.timeline import Timeline

class BillService:
    def __init__(self, db: Session):
        self.db = db
    
    def create_bill(self, bill_data: BillCreate) -> int:
        if not bill_data.payment_method:
            raise BillNotFoundException("Payment methods cannot be empty.")
        
        # Check if a bill already exists for the given form_id
        existing_bill = self.db.query(Bill).filter(Bill.form_id == bill_data.form_id).first()
        if existing_bill:
            raise ValueError(f"A bill already exists for the provided formId: {bill_data.form_id}")
        
        db_bill = Bill(**bill_data.dict())
        self.db.add(db_bill)
        self.db.commit()
        self.db.refresh(db_bill)
        return db_bill.id
    
    def get_bill_by_id(self, bill_id: int) -> Bill:
        bill = self.db.query(Bill).filter(Bill.id == bill_id).first()
        if not bill:
            raise BillNotFoundException(f"Bill not found with ID: {bill_id}")
        return bill
    
    def update_bill(self, bill_id: int, bill_data: BillUpdate) -> Bill:
        bill = self.get_bill_by_id(bill_id)
        
        # Update bill properties
        for key, value in bill_data.dict(exclude_unset=True).items():
            setattr(bill, key, value)
        
        self.db.commit()
        self.db.refresh(bill)
        return bill
    
    def delete_bill(self, bill_id: int) -> None:
        bill = self.get_bill_by_id(bill_id)
        self.db.delete(bill)
        self.db.commit()
    
    def get_all_bills(self, page: int, size: int, timeline: Optional[Timeline] = None) -> List[Bill]:
        query = self.db.query(Bill)
        
        if timeline and timeline != Timeline.ALL:
            start_date = self.calculate_start_date(timeline)
            query = query.filter(Bill.created_on >= start_date)
        
        return query.order_by(desc(Bill.created_on)).offset(page * size).limit(size).all()
    
    def get_all_bills_paginated(self, page: int, size: int, timeline: Optional[Timeline] = None) -> dict:
        query = self.db.query(Bill)
        
        if timeline and timeline != Timeline.ALL:
            start_date = self.calculate_start_date(timeline)
            query = query.filter(Bill.created_on >= start_date)
        
        total = query.count()
        bills = query.order_by(desc(Bill.created_on)).offset(page * size).limit(size).all()
        
        return {
            "bills": bills,
            "total": total,
            "page": page,
            "size": size,
            "has_next": (page + 1) * size < total,
            "has_prev": page > 0
        }
    
    def find_bill_by_service_name(self, service_name: str) -> List[Bill]:
        return self.db.query(Bill).filter(Bill.service_name.ilike(f"%{service_name}%")).all()
    
    def find_bills_by_status(self, status: BillStatus) -> List[Bill]:
        return self.db.query(Bill).filter(Bill.status == status).all()
    
    def find_bills_by_billing_type(self, billing_type: BillingType) -> List[Bill]:
        return self.db.query(Bill).filter(Bill.billing_type == billing_type).all()
    
    def find_bill_by_form_id(self, form_id: int) -> Bill:
        bill = self.db.query(Bill).filter(Bill.form_id == form_id).first()
        if not bill:
            raise BillNotFoundException(f"Bill not found with formId: {form_id}")
        return bill
    
    def delete_bill_by_form_id(self, form_id: int) -> None:
        bill = self.find_bill_by_form_id(form_id)
        self.db.delete(bill)
        self.db.commit()
    
    def calculate_start_date(self, timeline: Timeline) -> datetime:
        now = datetime.now()
        if timeline == Timeline.TODAY:
            return now.replace(hour=0, minute=0, second=0, microsecond=0)
        elif timeline == Timeline.THIS_WEEK:
            return now.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=now.weekday())
        elif timeline == Timeline.THIS_MONTH:
            return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        elif timeline == Timeline.THIS_YEAR:
            return now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
        else:
            raise ValueError("Invalid timeline")