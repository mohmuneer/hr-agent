"""نموذج سجل التدقيق — يسجل كل عملية مهمة في النظام."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Integer, JSON, String, Text

from app.core.database import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    username = Column(String(64), nullable=True, default="system")
    action = Column(String(32), nullable=False, index=True)
    resource_type = Column(String(32), nullable=False)
    resource_id = Column(String(32), nullable=True)
    details = Column(JSON, nullable=True)
    ip_address = Column(String(45), nullable=True)
