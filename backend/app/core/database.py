"""اتصال قاعدة البيانات PostgreSQL عبر SQLAlchemy."""
from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import get_settings


class Base(DeclarativeBase):
    pass


_db_url = get_settings().DATABASE_URL
if "?" not in _db_url:
    _db_url += "?client_encoding=utf8"
elif "client_encoding" not in _db_url:
    _db_url += "&client_encoding=utf8"

engine = create_engine(_db_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """إنشاء الجداول (للتطوير — في الإنتاج استخدم alembic)."""
    # استيراد النماذج لضمان تسجيلها في metadata قبل create_all
    import app.models  # noqa: F401

    Base.metadata.create_all(bind=engine)

    # ترحيل بيانات المعايير من ملفات JSON إلى DB إذا كانت فارغة
    from app.services.criteria_service import seed_from_json  # noqa: F811

    seed_from_json()
