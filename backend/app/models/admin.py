"""نموذج إعدادات المشرف — كلمة المرور المشفّرة وحالة التغيير."""
from __future__ import annotations

from sqlalchemy import Boolean, Column, Integer, String

from app.core.database import Base


class AdminSetting(Base):
    __tablename__ = "admin_settings"

    id = Column(Integer, primary_key=True, default=1)
    password_hash = Column(String(128), nullable=False)
    default_password_changed = Column(Boolean, default=False, nullable=False)
