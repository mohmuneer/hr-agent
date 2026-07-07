"""نقطة دخول التطبيق."""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles

from app.api.routes import router
from app.core.config import get_settings
from app.core.database import init_db
from app.services.auth import _init_admin_password

settings = get_settings()

app = FastAPI(title=settings.APP_NAME, version=settings.APP_VERSION)


@app.on_event("startup")
def on_startup():
    """إنشاء جداول قاعدة البيانات وتشفير كلمة المرور إن لم تكن مشفّرة بعد."""
    init_db()
    _init_admin_password()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # للتطوير فقط — قيّدها في الإنتاج
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)

FRONTEND_DIR = Path(__file__).resolve().parent.parent.parent / "frontend"
app.mount("/app", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")


@app.get("/", include_in_schema=False)
def root() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "login.html")


@app.get("/apply", include_in_schema=False)
def apply_page() -> FileResponse:
    """صفحة تقديم خارجية للمرشحين — منفصلة عن لوحة HR الداخلية."""
    return FileResponse(FRONTEND_DIR / "apply.html")


@app.get("/interview", include_in_schema=False)
def interview_page() -> FileResponse:
    """صفحة المقابلة الصوتية للمرشح — تُفتح من رابط التحقق من الحالة بعد الموافقة."""
    return FileResponse(FRONTEND_DIR / "interview.html")


@app.get("/login", include_in_schema=False)
def login_page() -> FileResponse:
    """صفحة تسجيل دخول فريق HR للوحة الداخلية."""
    return FileResponse(FRONTEND_DIR / "login.html")


@app.get("/health")
def health() -> dict:
    model = settings.GEMINI_MODEL if settings.PROVIDER == "gemini" else settings.MODEL
    return {
        "status": "ok",
        "configured": settings.is_configured,
        "provider": settings.PROVIDER,
        "model": model,
        "active_domain": settings.ACTIVE_DOMAIN,
    }


@app.get("/favicon.ico", include_in_schema=False)
def favicon() -> Response:
    return Response(status_code=204)
