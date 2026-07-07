"""اتصال قاعدة البيانات PostgreSQL عبر SQLAlchemy."""
from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import get_settings


class Base(DeclarativeBase):
    pass


engine = create_engine(get_settings().DATABASE_URL, pool_pre_ping=True)
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
