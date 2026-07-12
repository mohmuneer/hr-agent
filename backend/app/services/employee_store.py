"""تخزين بيانات الموظفين في PostgreSQL عبر SQLAlchemy."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import asc

from app.core.database import SessionLocal
from app.models.employee import Employee

# الحقول القابلة للتخزين/التعديل على نموذج الموظف
_EMPLOYEE_FIELDS = [
    "full_name", "employee_number", "nationality", "job_title", "phone", "salary",
    "iqama_number", "iqama_expiry_date", "national_id", "hire_date", "basic_salary",
    "housing_allowance", "other_allowances", "contract_type", "contract_end_date",
    "probation_end_date", "gosi_registered_before_2024",
]


def _row_to_dict(row: Employee) -> dict:
    data = {"id": row.id, "created_at": row.created_at.isoformat() if row.created_at else None}
    for f in _EMPLOYEE_FIELDS:
        data[f] = getattr(row, f, None)
    return data


def save_employee(record: dict) -> str:
    emp_id = uuid.uuid4().hex[:12]
    db = SessionLocal()
    try:
        row = Employee(
            id=emp_id,
            created_at=datetime.now(timezone.utc),
            **{f: record.get(f) for f in _EMPLOYEE_FIELDS},
        )
        db.add(row)
        db.commit()
        return emp_id
    finally:
        db.close()


def update_employee(emp_id: str, updates: dict) -> dict | None:
    db = SessionLocal()
    try:
        row = db.query(Employee).filter(Employee.id == emp_id).first()
        if row is None:
            return None

        for key, value in updates.items():
            if hasattr(row, key):
                setattr(row, key, value)

        db.commit()
        db.refresh(row)
        return _row_to_dict(row)
    finally:
        db.close()


def delete_employee(emp_id: str) -> bool:
    db = SessionLocal()
    try:
        row = db.query(Employee).filter(Employee.id == emp_id).first()
        if row is None:
            return False
        db.delete(row)
        db.commit()
        return True
    finally:
        db.close()


def list_employees(limit: int = 50, offset: int = 0) -> tuple[list[dict], int]:
    db = SessionLocal()
    try:
        q = db.query(Employee)
        total = q.count()
        rows = q.order_by(asc(Employee.full_name)).offset(offset).limit(limit).all()
        return [_row_to_dict(r) for r in rows], total
    finally:
        db.close()


def list_all_employees_raw() -> list[dict]:
    """يعيد كل الموظفين بلا حدود — يُستخدم لحسابات النطاقات وتنبيهات الإقامة."""
    db = SessionLocal()
    try:
        rows = db.query(Employee).all()
        return [_row_to_dict(r) for r in rows]
    finally:
        db.close()


def get_employee(emp_id: str) -> dict | None:
    db = SessionLocal()
    try:
        row = db.query(Employee).filter(Employee.id == emp_id).first()
        if row is None:
            return None
        return _row_to_dict(row)
    finally:
        db.close()
