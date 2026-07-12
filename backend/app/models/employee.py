"""نموذج الموظف في قاعدة البيانات."""
from __future__ import annotations

from sqlalchemy import Boolean, Column, DateTime, Float, String

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
    salary = Column(Float, nullable=True)  # إجمالي الراتب (قديم — للتوافق العكسي)
    iqama_number = Column(String(32), nullable=True)
    iqama_expiry_date = Column(String(16), nullable=True)

    # --- حقول الامتثال لنظام العمل السعودي ---
    national_id = Column(String(16), nullable=True)  # لمواطن سعودي (رقم الهوية الوطنية)
    hire_date = Column(String(16), nullable=True)  # YYYY-MM-DD — تاريخ التعيين
    basic_salary = Column(Float, nullable=True)  # الراتب الأساسي (لحساب GOSI ومكافأة نهاية الخدمة)
    housing_allowance = Column(Float, nullable=True, default=0.0)
    other_allowances = Column(Float, nullable=True, default=0.0)
    contract_type = Column(String(16), nullable=True, default="unlimited")  # unlimited | limited
    contract_end_date = Column(String(16), nullable=True)  # للعقود محددة المدة فقط
    probation_end_date = Column(String(16), nullable=True)
    gosi_registered_before_2024 = Column(Boolean, nullable=True, default=True)

