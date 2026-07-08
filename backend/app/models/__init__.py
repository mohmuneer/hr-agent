"""تجميع النماذج لضمان تسجيلها في SQLAlchemy metadata."""
from app.models.admin import AdminSetting
from app.models.application import Application
from app.models.audit_log import AuditLog
from app.models.criteria import Criterion, Domain
from app.models.employee import Employee
from app.models.job import Job
from app.models.session import Session

__all__ = ["AdminSetting", "Application", "AuditLog", "Criterion", "Domain", "Employee", "Job", "Session"]
