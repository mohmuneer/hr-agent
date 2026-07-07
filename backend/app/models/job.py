"""نموذج الوظيفة في قاعدة البيانات."""
from __future__ import annotations

from sqlalchemy import Column, DateTime, String, Text
from sqlalchemy.sql import func

from app.core.database import Base


class Job(Base):
    __tablename__ = "jobs"

    id = Column(String(16), primary_key=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    title = Column(String(255), nullable=False)
    domain = Column(String(64), nullable=True)
    description = Column(Text, nullable=True)
    location = Column(String(128), nullable=True)
    status = Column(String(16), default="open", nullable=False, index=True)
