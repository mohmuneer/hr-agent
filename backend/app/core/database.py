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


def _ensure_saudi_compliance_columns():
    """إضافة أعمدة الامتثال السعودي إن لم تكن موجودة (للتوافق مع قواعد البيانات القديمة)."""
    from sqlalchemy import inspect, text
    inspector = inspect(engine)
    cols = {c["name"] for c in inspector.get_columns("employees")}
    new_cols = [
        ("national_id", "VARCHAR(16)"),
        ("hire_date", "VARCHAR(16)"),
        ("basic_salary", "DOUBLE PRECISION"),
        ("housing_allowance", "DOUBLE PRECISION DEFAULT 0"),
        ("other_allowances", "DOUBLE PRECISION DEFAULT 0"),
        ("contract_type", "VARCHAR(16) DEFAULT 'unlimited'"),
        ("contract_end_date", "VARCHAR(16)"),
        ("probation_end_date", "VARCHAR(16)"),
        ("gosi_registered_before_2024", "BOOLEAN DEFAULT TRUE"),
    ]
    with engine.begin() as conn:
        for name, dtype in new_cols:
            if name not in cols:
                conn.execute(text(f"ALTER TABLE employees ADD COLUMN {name} {dtype}"))


def init_db():
    """إنشاء الجداول (للتطوير — في الإنتاج استخدم alembic)."""
    # استيراد النماذج لضمان تسجيلها في metadata قبل create_all
    import app.models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    _ensure_saudi_compliance_columns()

    # ترحيل بيانات المعايير من ملفات JSON إلى DB إذا كانت فارغة
    from app.services.criteria_service import seed_from_json  # noqa: F811

    seed_from_json()
