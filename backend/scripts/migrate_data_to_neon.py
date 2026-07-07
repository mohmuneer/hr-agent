"""Migrate JSON data to Neon PostgreSQL."""
import sys
import json
from datetime import datetime, timezone
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.core.database import init_db, SessionLocal
from app.models.application import Application

init_db()
data_dir = Path(__file__).resolve().parent.parent / "app" / "data" / "applications"
if not data_dir.exists():
    print("data dir not found")
else:
    db = SessionLocal()
    try:
        count = 0
        for f in sorted(data_dir.iterdir()):
            if f.suffix == ".json":
                with open(f) as fh:
                    rec = json.load(fh)
                row = Application(
                    id=rec.get("id", f.stem),
                    submitted_at=datetime.fromisoformat(rec.get("submitted_at", datetime.now(timezone.utc).isoformat())) if isinstance(rec.get("submitted_at"), str) else datetime.now(timezone.utc),
                    status=rec.get("status", "pending"),
                    interview_datetime=rec.get("interview_datetime"),
                    note_ar=rec.get("note_ar"),
                    full_name=rec.get("full_name", ""),
                    email=rec.get("email", ""),
                    phone=rec.get("phone"),
                    job_title=rec.get("job_title", ""),
                    domain=rec.get("domain"),
                    cv_text=rec.get("cv_text", ""),
                    overall_score=rec.get("overall_score"),
                    recommendation_ar=rec.get("recommendation_ar"),
                    analysis_error=rec.get("analysis_error"),
                    result=rec.get("result"),
                    questions=rec.get("questions", []),
                    voice_transcript=rec.get("voice_transcript", []),
                    voice_interview_result=rec.get("voice_interview_result"),
                    written_test_result=rec.get("written_test_result"),
                    final_recommendation=rec.get("final_recommendation"),
                    hiring_decision=rec.get("hiring_decision"),
                    hiring_feedback_ar=rec.get("hiring_feedback_ar"),
                )
                db.add(row)
                count += 1
                name = rec.get("full_name", f.stem)
                print(f"Migrated: {name}")
        db.commit()
        print(f"Migrated {count} applications to Neon")
    finally:
        db.close()
