"""إعدادات التطبيق المركزية."""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


class Settings:
    """إعدادات محمّلة من متغيرات البيئة مع قيم افتراضية آمنة."""

    APP_NAME: str = "HR Agent"
    APP_VERSION: str = "0.1.0"

    # مزوّد النموذج المستخدم: "anthropic" أو "gemini"
    PROVIDER: str = os.getenv("HR_AGENT_PROVIDER", "anthropic")

    # مفتاح Anthropic — يُقرأ من البيئة، لا يُكتب في الكود أبداً
    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
    MODEL: str = os.getenv("HR_AGENT_MODEL", "claude-sonnet-4-5")

    # مفتاح Gemini (مجاني عبر Google AI Studio) — بديل عن Anthropic
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL: str = os.getenv("HR_AGENT_GEMINI_MODEL", "gemini-2.5-flash")

    # مسار ملفات معايير التقييم (يعدّلها خبير HR)
    CRITERIA_DIR: Path = Path(__file__).resolve().parent.parent / "criteria"

    # مسار تخزين طلبات التقديم الواردة من صفحة التقديم الخارجية
    APPLICATIONS_DIR: Path = Path(__file__).resolve().parent.parent / "data" / "applications"

    # مسار تخزين الوظائف المتاحة (يديرها فريق HR من لوحة التحكم)
    JOBS_DIR: Path = Path(__file__).resolve().parent.parent / "data" / "jobs"

    # مسار تخزين بيانات الموظفين (رواتب وإقامات — بيانات حساسة، محمية بالكامل)
    EMPLOYEES_DIR: Path = Path(__file__).resolve().parent.parent / "data" / "employees"

    # المجال المفعّل في هذه النسخة (نبدأ بواحد فقط)
    ACTIVE_DOMAIN: str = os.getenv("HR_AGENT_DOMAIN", "accounting")

    # PostgreSQL — استخدم متغير البيئة DATABASE_URL أو القيمة الافتراضية للتطوير
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql://hr_agent:hr_agent@localhost:5432/hr_agent",
    )

    # بيانات دخول لوحة HR الداخلية — غيّرها في .env قبل أي استخدام فعلي
    ADMIN_USERNAME: str = os.getenv("HR_ADMIN_USERNAME", "admin")
    ADMIN_PASSWORD: str = os.getenv("HR_ADMIN_PASSWORD", "changeme123")

    # CORS — النطاقات المسموح بها (افصل بينها بفاصلة)
    CORS_ORIGINS: list[str] = [
        o.strip() for o in os.getenv("CORS_ORIGINS", "*").split(",") if o.strip()
    ]

    # OpenAI — دعم مباشر لنماذج OpenAI ومنصات متوافقة
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o")
    OPENAI_BASE_URL: str = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")

    # SMTP — إشعارات البريد الإلكتروني للمرشحين (اختياري — إذا تركت فارغة، لن ترسل الإيميلات)
    SMTP_HOST: str = os.getenv("SMTP_HOST", "")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USER: str = os.getenv("SMTP_USER", "")
    SMTP_PASSWORD: str = os.getenv("SMTP_PASSWORD", "")
    SMTP_FROM: str = os.getenv("SMTP_FROM", "")

    @property
    def is_configured(self) -> bool:
        if self.PROVIDER == "gemini":
            return bool(self.GEMINI_API_KEY)
        if self.PROVIDER == "openai":
            return bool(self.OPENAI_API_KEY)
        return bool(self.ANTHROPIC_API_KEY)


@lru_cache
def get_settings() -> Settings:
    return Settings()
