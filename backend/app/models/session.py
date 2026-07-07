"""نموذج جلسة المصادقة في قاعدة البيانات — بديل عن التخزين في الذاكرة."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Column, DateTime, String, delete
from sqlalchemy.sql import func

from app.core.database import Base, SessionLocal


class Session(Base):
    __tablename__ = "sessions"

    token = Column(String(64), primary_key=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)


def cleanup_expired_sessions():
    """تنظيف الجلسات المنتهية — يمكن استدعاؤها دورياً."""
    db = SessionLocal()
    try:
        db.execute(delete(Session).where(Session.expires_at < datetime.now()))
        db.commit()
    finally:
        db.close()
