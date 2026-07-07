"""مصادقة آمنة مع bcrypt وجلسات PostgreSQL."""
from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path

import bcrypt
from sqlalchemy import delete

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.models.admin import AdminSetting
from app.models.session import Session as SessionModel

SESSION_DURATION = timedelta(hours=12)
ENV_PATH = Path(__file__).resolve().parents[2] / ".env"


def _init_admin_password() -> None:
    """تشفير كلمة المرور من .env عند أول تشغيل وتخزينها في قاعدة البيانات."""
    db = SessionLocal()
    try:
        setting = db.query(AdminSetting).filter(AdminSetting.id == 1).first()
        if setting is not None:
            return

        settings = get_settings()
        hashed = bcrypt.hashpw(settings.ADMIN_PASSWORD.encode("utf-8"), bcrypt.gensalt())
        setting = AdminSetting(
            id=1,
            password_hash=hashed.decode("utf-8"),
            default_password_changed=False,
        )
        db.add(setting)
        db.commit()
    finally:
        db.close()


def is_default_password_changed() -> bool:
    """التحقق هل غيّر المشرف كلمة المرور الافتراضية."""
    db = SessionLocal()
    try:
        setting = db.query(AdminSetting).filter(AdminSetting.id == 1).first()
        if setting is None:
            return False
        return setting.default_password_changed
    finally:
        db.close()


def authenticate(username: str, password: str) -> bool:
    settings = get_settings()
    if not secrets.compare_digest(username, settings.ADMIN_USERNAME):
        return False

    db = SessionLocal()
    try:
        setting = db.query(AdminSetting).filter(AdminSetting.id == 1).first()
        if setting is None:
            return False
        return bcrypt.checkpw(
            password.encode("utf-8"),
            setting.password_hash.encode("utf-8"),
        )
    finally:
        db.close()


def _persist_password_to_env(new_password: str) -> None:
    lines = ENV_PATH.read_text(encoding="utf-8").splitlines() if ENV_PATH.exists() else []
    found = False
    new_lines = []
    for line in lines:
        if line.strip().startswith("HR_ADMIN_PASSWORD="):
            new_lines.append(f"HR_ADMIN_PASSWORD={new_password}")
            found = True
        else:
            new_lines.append(line)
    if not found:
        new_lines.append(f"HR_ADMIN_PASSWORD={new_password}")
    ENV_PATH.write_text("\n".join(new_lines) + "\n", encoding="utf-8")


def change_password(current_password: str, new_password: str) -> None:
    settings = get_settings()
    if not authenticate(settings.ADMIN_USERNAME, current_password):
        raise PermissionError("كلمة المرور الحالية غير صحيحة.")
    if len(new_password) < 6:
        raise ValueError("كلمة المرور الجديدة يجب أن تكون 6 أحرف على الأقل.")

    hashed = bcrypt.hashpw(new_password.encode("utf-8"), bcrypt.gensalt())

    db = SessionLocal()
    try:
        setting = db.query(AdminSetting).filter(AdminSetting.id == 1).first()
        if setting is None:
            raise RuntimeError("لم يتم تهيئة إعدادات المشرف.")

        setting.password_hash = hashed.decode("utf-8")
        setting.default_password_changed = True
        db.commit()
    finally:
        db.close()

    _persist_password_to_env(new_password)
    settings.ADMIN_PASSWORD = new_password


def create_session() -> str:
    token = secrets.token_urlsafe(32)
    db = SessionLocal()
    try:
        row = SessionModel(
            token=token,
            expires_at=datetime.now(timezone.utc) + SESSION_DURATION,
        )
        db.add(row)
        db.commit()
        return token
    finally:
        db.close()


def verify_session(token: str | None) -> bool:
    if not token:
        return False
    db = SessionLocal()
    try:
        row = db.query(SessionModel).filter(SessionModel.token == token).first()
        if row is None:
            return False
        if datetime.now(timezone.utc) > row.expires_at:
            db.delete(row)
            db.commit()
            return False
        return True
    finally:
        db.close()


def destroy_session(token: str | None) -> None:
    if not token:
        return
    db = SessionLocal()
    try:
        db.execute(delete(SessionModel).where(SessionModel.token == token))
        db.commit()
    finally:
        db.close()
