"""تخزين طلبات التقديم في PostgreSQL عبر SQLAlchemy."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import desc

from app.core.database import SessionLocal
from app.models.application import Application


def _row_to_dict(row: Application) -> dict:
    return {
        "id": row.id,
        "submitted_at": row.submitted_at.isoformat() if row.submitted_at else None,
        "status": row.status,
        "interview_datetime": row.interview_datetime,
        "note_ar": row.note_ar,
        "full_name": row.full_name,
        "email": row.email,
        "phone": row.phone,
        "job_title": row.job_title,
        "domain": row.domain,
        "cv_text": row.cv_text,
        "overall_score": row.overall_score,
        "recommendation_ar": row.recommendation_ar,
        "analysis_error": row.analysis_error,
        "result": row.result,
        "questions": row.questions or [],
        "voice_transcript": row.voice_transcript or [],
        "voice_interview_result": row.voice_interview_result,
        "written_test_result": row.written_test_result,
        "final_recommendation": row.final_recommendation,
        "hiring_decision": row.hiring_decision,
        "hiring_feedback_ar": row.hiring_feedback_ar,
    }


def save_application(record: dict) -> str:
    app_id = uuid.uuid4().hex[:12]
    db = SessionLocal()
    try:
        row = Application(
            id=app_id,
            submitted_at=datetime.now(timezone.utc),
            status=record.get("status", "pending"),
            interview_datetime=record.get("interview_datetime"),
            note_ar=record.get("note_ar"),
            full_name=record.get("full_name", ""),
            email=record.get("email", ""),
            phone=record.get("phone"),
            job_title=record.get("job_title", ""),
            domain=record.get("domain"),
            cv_text=record.get("cv_text", ""),
            overall_score=record.get("overall_score"),
            recommendation_ar=record.get("recommendation_ar"),
            analysis_error=record.get("analysis_error"),
            result=record.get("result"),
            questions=record.get("questions", []),
            voice_transcript=record.get("voice_transcript", []),
            voice_interview_result=record.get("voice_interview_result"),
            written_test_result=record.get("written_test_result"),
            final_recommendation=record.get("final_recommendation"),
            hiring_decision=record.get("hiring_decision"),
            hiring_feedback_ar=record.get("hiring_feedback_ar"),
        )
        db.add(row)
        db.commit()
        return app_id
    finally:
        db.close()


def update_application(app_id: str, updates: dict) -> dict | None:
    db = SessionLocal()
    try:
        row = db.query(Application).filter(Application.id == app_id).first()
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


def list_applications(
    limit: int = 50,
    offset: int = 0,
    search: str | None = None,
    status: str | None = None,
    domain: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
) -> tuple[list[dict], int]:
    db = SessionLocal()
    try:
        q = db.query(Application)

        if search:
            q = q.filter(
                Application.full_name.ilike(f"%{search}%")
                | Application.email.ilike(f"%{search}%")
            )
        if status:
            q = q.filter(Application.status == status)
        if domain:
            q = q.filter(Application.domain == domain)
        if date_from:
            q = q.filter(Application.submitted_at >= date_from)
        if date_to:
            q = q.filter(Application.submitted_at <= date_to)

        total = q.count()
        rows = q.order_by(desc(Application.submitted_at)).offset(offset).limit(limit).all()
        return [_row_to_dict(r) for r in rows], total
    finally:
        db.close()


def get_application(app_id: str) -> dict | None:
    db = SessionLocal()
    try:
        row = db.query(Application).filter(Application.id == app_id).first()
        if row is None:
            return None
        return _row_to_dict(row)
    finally:
        db.close()


def delete_application(app_id: str) -> bool:
    db = SessionLocal()
    try:
        row = db.query(Application).filter(Application.id == app_id).first()
        if row is None:
            return False
        db.delete(row)
        db.commit()
        return True
    finally:
        db.close()


def delete_applications_batch(app_ids: list[str]) -> int:
    db = SessionLocal()
    try:
        deleted = db.query(Application).filter(Application.id.in_(app_ids)).delete(synchronize_session=False)
        db.commit()
        return deleted
    finally:
        db.close()
