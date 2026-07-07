#!/usr/bin/env python
"""ترحيل البيانات من ملفات JSON إلى PostgreSQL.

يشغّل بعد تهيئة قاعدة البيانات:
    python scripts/migrate_json_to_pg.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

# نضيف مسار backend إلى sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.config import get_settings
from app.core.database import init_db, SessionLocal
from app.models.application import Application
from app.models.employee import Employee
from app.models.job import Job


def _normalize_questions(questions: list) -> list:
    """نفس الدالة من application_store.py القديمة — للمحافظة على التوافق."""
    import uuid

    normalized = []
    for q in questions:
        if "id" not in q:
            q = {**q, "id": uuid.uuid4().hex[:8]}
        if "type" not in q:
            q = {**q, "type": "mcq" if q.get("options") else "open"}
        q.setdefault("options", None)
        q.setdefault("correct_answer", None)
        normalized.append(q)
    return normalized


def migrate_applications(settings) -> int:
    count = 0
    apps_dir = settings.APPLICATIONS_DIR
    if not apps_dir.exists():
        return 0

    db = SessionLocal()
    try:
        for path in sorted(apps_dir.glob("*.json")):
            with path.open(encoding="utf-8") as f:
                data = json.load(f)

            # التحقق من وجود السجل مسبقاً
            existing = db.query(Application).filter(Application.id == data.get("id")).first()
            if existing:
                continue

            questions = data.get("questions", [])
            if questions:
                questions = _normalize_questions(questions)

            from datetime import datetime, timezone

            submitted_str = data.get("submitted_at")
            submitted_at = None
            if submitted_str:
                try:
                    submitted_at = datetime.fromisoformat(submitted_str)
                except ValueError:
                    submitted_at = datetime.now(timezone.utc)

            row = Application(
                id=data.get("id", ""),
                submitted_at=submitted_at or datetime.now(timezone.utc),
                status=data.get("status", "pending"),
                full_name=data.get("full_name", ""),
                email=data.get("email", ""),
                phone=data.get("phone"),
                job_title=data.get("job_title", ""),
                domain=data.get("domain"),
                cv_text=data.get("cv_text", ""),
                overall_score=data.get("overall_score"),
                recommendation_ar=data.get("recommendation_ar"),
                analysis_error=data.get("analysis_error"),
                result=data.get("result"),
                questions=questions,
                voice_transcript=data.get("voice_transcript", []),
                voice_interview_result=data.get("voice_interview_result"),
                written_test_result=data.get("written_test_result"),
                final_recommendation=data.get("final_recommendation"),
                interview_datetime=data.get("interview_datetime"),
                note_ar=data.get("note_ar"),
                hiring_decision=data.get("hiring_decision"),
                hiring_feedback_ar=data.get("hiring_feedback_ar"),
            )
            db.add(row)
            count += 1

        db.commit()
    finally:
        db.close()

    return count


def migrate_jobs(settings) -> int:
    count = 0
    jobs_dir = settings.JOBS_DIR
    if not jobs_dir.exists():
        return 0

    db = SessionLocal()
    try:
        for path in sorted(jobs_dir.glob("*.json")):
            with path.open(encoding="utf-8") as f:
                data = json.load(f)

            existing = db.query(Job).filter(Job.id == data.get("id")).first()
            if existing:
                continue

            from datetime import datetime, timezone

            created_str = data.get("created_at")
            created_at = None
            if created_str:
                try:
                    created_at = datetime.fromisoformat(created_str)
                except ValueError:
                    created_at = datetime.now(timezone.utc)

            row = Job(
                id=data.get("id", ""),
                created_at=created_at or datetime.now(timezone.utc),
                title=data.get("title", ""),
                domain=data.get("domain"),
                description=data.get("description"),
                location=data.get("location"),
                status=data.get("status", "open"),
            )
            db.add(row)
            count += 1

        db.commit()
    finally:
        db.close()

    return count


def migrate_employees(settings) -> int:
    count = 0
    emp_dir = settings.EMPLOYEES_DIR
    if not emp_dir.exists():
        return 0

    db = SessionLocal()
    try:
        for path in sorted(emp_dir.glob("*.json")):
            with path.open(encoding="utf-8") as f:
                data = json.load(f)

            existing = db.query(Employee).filter(Employee.id == data.get("id")).first()
            if existing:
                continue

            from datetime import datetime, timezone

            created_str = data.get("created_at")
            created_at = None
            if created_str:
                try:
                    created_at = datetime.fromisoformat(created_str)
                except ValueError:
                    created_at = datetime.now(timezone.utc)

            row = Employee(
                id=data.get("id", ""),
                created_at=created_at or datetime.now(timezone.utc),
                full_name=data.get("full_name", ""),
                employee_number=data.get("employee_number"),
                nationality=data.get("nationality"),
                job_title=data.get("job_title"),
                phone=data.get("phone"),
                salary=data.get("salary"),
                iqama_number=data.get("iqama_number"),
                iqama_expiry_date=data.get("iqama_expiry_date"),
            )
            db.add(row)
            count += 1

        db.commit()
    finally:
        db.close()

    return count


def main():
    init_db()
    settings = get_settings()

    print("بدء ترحيل البيانات من JSON إلى PostgreSQL...")

    apps = migrate_applications(settings)
    print(f"  الطلبات: {apps}")

    jobs = migrate_jobs(settings)
    print(f"  الوظائف: {jobs}")

    employees = migrate_employees(settings)
    print(f"  الموظفون: {employees}")

    total = apps + jobs + employees
    print(f"\nتم بنجاح! إجمالي السجلات المُرحّلة: {total}")


if __name__ == "__main__":
    main()
