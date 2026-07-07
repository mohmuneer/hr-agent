"""تخزين بيانات الموظفين في PostgreSQL عبر SQLAlchemy."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import asc

from app.core.database import SessionLocal
from app.models.employee import Employee


def _row_to_dict(row: Employee) -> dict:
    return {
        "id": row.id,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "full_name": row.full_name,
        "employee_number": row.employee_number,
        "nationality": row.nationality,
        "job_title": row.job_title,
        "phone": row.phone,
        "salary": row.salary,
        "iqama_number": row.iqama_number,
        "iqama_expiry_date": row.iqama_expiry_date,
    }


def save_employee(record: dict) -> str:
    emp_id = uuid.uuid4().hex[:12]
    db = SessionLocal()
    try:
        row = Employee(
            id=emp_id,
            created_at=datetime.now(timezone.utc),
            full_name=record.get("full_name", ""),
            employee_number=record.get("employee_number"),
            nationality=record.get("nationality"),
            job_title=record.get("job_title"),
            phone=record.get("phone"),
            salary=record.get("salary"),
            iqama_number=record.get("iqama_number"),
            iqama_expiry_date=record.get("iqama_expiry_date"),
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


def get_employee(emp_id: str) -> dict | None:
    db = SessionLocal()
    try:
        row = db.query(Employee).filter(Employee.id == emp_id).first()
        if row is None:
            return None
        return _row_to_dict(row)
    finally:
        db.close()
