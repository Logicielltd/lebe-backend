from sqlalchemy import Integer, String, DateTime, Numeric
from sqlalchemy.sql import func
from utilities.dbconfig import Base
from datetime import datetime
from typing import Optional

from sqlalchemy import Integer, String, DateTime
from sqlalchemy.sql import func
from utilities.dbconfig import Base
from datetime import datetime
from typing import Optional

from sqlalchemy import String, DateTime, Integer
from sqlalchemy.orm import Mapped, mapped_column

class Invoice(Base):
    __tablename__ = "invoice"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    bill_id: Mapped[Optional[int]] = mapped_column(Integer)
    invoice_number: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    customer_name: Mapped[Optional[str]] = mapped_column(String)
    customer_email: Mapped[Optional[str]] = mapped_column(String)
    service_name: Mapped[str] = mapped_column(String, nullable=False)
    amount: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    created_on: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_on: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    def __repr__(self):
        return f"<Invoice(id={self.id}, invoice_number={self.invoice_number}, amount={self.amount})>"