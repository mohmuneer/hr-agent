"""نموذج طلب التقديم في قاعدة البيانات."""
from __future__ import annotations

from sqlalchemy import Column, DateTime, Float, JSON, String, Text
from sqlalchemy.sql import func

from app.core.database import Base


class Application(Base):
    __tablename__ = "applications"

    id = Column(String(16), primary_key=True)
    submitted_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    status = Column(String(16), default="pending", nullable=False, index=True)

    full_name = Column(String(255), nullable=False)
    email = Column(String(255), nullable=False, index=True)
    phone = Column(String(32), nullable=True)
    job_title = Column(String(255), nullable=False)
    domain = Column(String(64), nullable=True, index=True)

    cv_text = Column(Text, nullable=False)
    overall_score = Column(Float, nullable=True)
    recommendation_ar = Column(Text, nullable=True)
    analysis_error = Column(Text, nullable=True)

    result = Column(JSON, nullable=True)
    questions = Column(JSON, nullable=True, default=list)
    voice_transcript = Column(JSON, nullable=True, default=list)
    voice_interview_result = Column(JSON, nullable=True)
    written_test_result = Column(JSON, nullable=True)
    final_recommendation = Column(JSON, nullable=True)

    interview_datetime = Column(String(64), nullable=True)
    note_ar = Column(Text, nullable=True)
    hiring_decision = Column(String(16), nullable=True)
    hiring_feedback_ar = Column(Text, nullable=True)
