"""تخزين الوظائف في PostgreSQL عبر SQLAlchemy."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import desc

from app.core.database import SessionLocal
from app.models.job import Job


def _row_to_dict(row: Job) -> dict:
    return {
        "id": row.id,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "title": row.title,
        "domain": row.domain,
        "description": row.description,
        "location": row.location,
        "status": row.status,
    }


def save_job(record: dict) -> str:
    job_id = uuid.uuid4().hex[:12]
    db = SessionLocal()
    try:
        row = Job(
            id=job_id,
            created_at=datetime.now(timezone.utc),
            title=record.get("title", ""),
            domain=record.get("domain"),
            description=record.get("description"),
            location=record.get("location"),
            status=record.get("status", "open"),
        )
        db.add(row)
        db.commit()
        return job_id
    finally:
        db.close()


def update_job(job_id: str, updates: dict) -> dict | None:
    db = SessionLocal()
    try:
        row = db.query(Job).filter(Job.id == job_id).first()
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


def delete_job(job_id: str) -> bool:
    db = SessionLocal()
    try:
        row = db.query(Job).filter(Job.id == job_id).first()
        if row is None:
            return False
        db.delete(row)
        db.commit()
        return True
    finally:
        db.close()


def list_jobs(status: str | None = None, limit: int = 50, offset: int = 0) -> tuple[list[dict], int]:
    db = SessionLocal()
    try:
        q = db.query(Job)
        if status:
            q = q.filter(Job.status == status)
        total = q.count()
        rows = q.order_by(desc(Job.created_at)).offset(offset).limit(limit).all()
        return [_row_to_dict(r) for r in rows], total
    finally:
        db.close()


def get_job(job_id: str) -> dict | None:
    db = SessionLocal()
    try:
        row = db.query(Job).filter(Job.id == job_id).first()
        if row is None:
            return None
        return _row_to_dict(row)
    finally:
        db.close()
