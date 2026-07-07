"""سجل تدقيق — يسجل العمليات المهمة في قاعدة البيانات."""
from __future__ import annotations

from datetime import datetime, timezone

from app.core.database import SessionLocal
from app.models.audit_log import AuditLog


def log_action(
    action: str,
    resource_type: str,
    resource_id: str | None = None,
    details: dict | None = None,
    username: str | None = None,
    ip_address: str | None = None,
) -> None:
    """تسجيل حدث في سجل التدقيق."""
    db = SessionLocal()
    try:
        row = AuditLog(
            username=username or "system",
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details,
            ip_address=ip_address,
            created_at=datetime.now(timezone.utc),
        )
        db.add(row)
        db.commit()
    finally:
        db.close()


def list_logs(limit: int = 100, offset: int = 0) -> tuple[list[dict], int]:
    """جلب آخر سجلات التدقيق."""
    db = SessionLocal()
    try:
        q = db.query(AuditLog)
        total = q.count()
        rows = q.order_by(AuditLog.created_at.desc()).offset(offset).limit(limit).all()
        items = [
            {
                "id": r.id,
                "created_at": r.created_at.isoformat(),
                "username": r.username,
                "action": r.action,
                "resource_type": r.resource_type,
                "resource_id": r.resource_id,
                "details": r.details,
                "ip_address": r.ip_address,
            }
            for r in rows
        ]
        return items, total
    finally:
        db.close()
