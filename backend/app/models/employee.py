"""نموذج الموظف في قاعدة البيانات."""
from __future__ import annotations

from sqlalchemy import Column, DateTime, Float, String

from app.core.database import Base


class Employee(Base):
    __tablename__ = "employees"

    id = Column(String(16), primary_key=True)
    created_at = Column(DateTime(timezone=True), server_default="now()", nullable=False)
    full_name = Column(String(255), nullable=False)
    employee_number = Column(String(32), nullable=True)
    nationality = Column(String(64), nullable=True)
    job_title = Column(String(255), nullable=True)
    phone = Column(String(32), nullable=True)
    salary = Column(Float, nullable=True)
    iqama_number = Column(String(32), nullable=True)
    iqama_expiry_date = Column(String(16), nullable=True)
