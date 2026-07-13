"""سجل الأدوات (Tool Registry) لنظام AI Command Center.
يُعرِّف كل أداة يمكن للوكيل تنفيذها مع معاملاتها ووظائف تنفيذها.
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta

from app.core.database import SessionLocal
from app.models.employee import Employee
from app.models.audit_log import AuditLog
from app.models.application import Application
from app.models.job import Job
from app.services.employee_store import list_employees, get_employee, save_employee, update_employee, delete_employee
from app.services.application_store import list_applications, get_application, update_application
from app.services.job_store import list_jobs, get_job, save_job, update_job, delete_job
from app.services.audit_logger import log_action, list_logs
from app.services.employee_import import generate_template_excel
from app.services.employee_store import list_all_employees_raw
from app.services.saudi_labor_law import (
    calculate_end_of_service,
    calculate_gosi,
    calculate_saudization,
    check_iqama_expiry,
    annual_leave_days,
    probation_info,
)
from app.services.auth import verify_session
from sqlalchemy import func


TOOL_DEFINITIONS = [
    {
        "name": "list_employees",
        "description": "عرض قائمة الموظفين مع إمكانية البحث والتصفية",
        "parameters": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "description": "عدد النتائج (افتراضي 50)", "default": 50},
                "offset": {"type": "integer", "description": "بداية النتائج (افتراضي 0)", "default": 0},
                "search": {"type": "string", "description": "نص للبحث في اسم الموظف", "default": ""},
            },
        },
        "needs_confirmation": False,
    },
    {
        "name": "get_employee_detail",
        "description": "عرض بيانات موظف محدد",
        "parameters": {
            "type": "object",
            "properties": {
                "employee_id": {"type": "string", "description": "معرف الموظف"},
            },
            "required": ["employee_id"],
        },
        "needs_confirmation": False,
    },
    {
        "name": "count_employees",
        "description": "إحصاء عدد الموظفين",
        "parameters": {
            "type": "object",
            "properties": {},
        },
        "needs_confirmation": False,
    },
    {
        "name": "list_applications",
        "description": "عرض طلبات التوظيف مع إمكانية التصفية حسب الحالة والمجال",
        "parameters": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "description": "عدد النتائج", "default": 50},
                "status": {"type": "string", "description": "تصفية حسب الحالة (pending/approved/rejected)", "default": ""},
                "domain": {"type": "string", "description": "تصفية حسب المجال", "default": ""},
            },
        },
        "needs_confirmation": False,
    },
    {
        "name": "get_application_detail",
        "description": "عرض تفاصيل طلب توظيف محدد",
        "parameters": {
            "type": "object",
            "properties": {
                "app_id": {"type": "string", "description": "معرف الطلب"},
            },
            "required": ["app_id"],
        },
        "needs_confirmation": False,
    },
    {
        "name": "list_jobs",
        "description": "عرض المسميات الوظيفية المتاحة",
        "parameters": {
            "type": "object",
            "properties": {
                "status": {"type": "string", "description": "تصفية حسب الحالة (open/closed)", "default": ""},
            },
        },
        "needs_confirmation": False,
    },
    {
        "name": "add_employee",
        "description": "إضافة موظف جديد إلى النظام",
        "parameters": {
            "type": "object",
            "properties": {
                "full_name": {"type": "string", "description": "الاسم الكامل"},
                "employee_number": {"type": "string", "description": "الرقم الوظيفي (اختياري)"},
                "nationality": {"type": "string", "description": "الجنسية"},
                "job_title": {"type": "string", "description": "المسمى الوظيفي"},
                "phone": {"type": "string", "description": "رقم الجوال (اختياري)"},
                "salary": {"type": "number", "description": "الراتب (اختياري)"},
                "iqama_number": {"type": "string", "description": "رقم الإقامة (اختياري)"},
                "iqama_expiry_date": {"type": "string", "description": "تاريخ انتهاء الإقامة (اختياري)"},
                "national_id": {"type": "string", "description": "رقم الهوية الوطنية للسعوديين (اختياري)"},
                "hire_date": {"type": "string", "description": "تاريخ التعيين YYYY-MM-DD (اختياري)"},
                "basic_salary": {"type": "number", "description": "الراتب الأساسي — أساس GOSI ومكافأة نهاية الخدمة (اختياري)"},
                "housing_allowance": {"type": "number", "description": "بدل السكن الشهري (اختياري)"},
                "other_allowances": {"type": "number", "description": "بدلات أخرى شهرية (اختياري)"},
                "contract_type": {"type": "string", "description": "نوع العقد: unlimited أو limited (اختياري)"},
                "contract_end_date": {"type": "string", "description": "تاريخ نهاية العقد للعقود محددة المدة (اختياري)"},
                "gosi_registered_before_2024": {"type": "boolean", "description": "هل الموظف مسجل بالتأمينات قبل 3 يوليو 2024؟ (اختياري)"},
            },
            "required": ["full_name", "job_title"],
        },
        "needs_confirmation": True,
    },
    {
        "name": "update_employee",
        "description": "تعديل بيانات موظف موجود",
        "parameters": {
            "type": "object",
            "properties": {
                "employee_id": {"type": "string", "description": "معرف الموظف"},
                "full_name": {"type": "string", "description": "الاسم الكامل"},
                "nationality": {"type": "string", "description": "الجنسية"},
                "job_title": {"type": "string", "description": "المسمى الوظيفي"},
                "phone": {"type": "string", "description": "رقم الجوال"},
                "salary": {"type": "number", "description": "الراتب"},
                "national_id": {"type": "string", "description": "رقم الهوية الوطنية"},
                "hire_date": {"type": "string", "description": "تاريخ التعيين YYYY-MM-DD"},
                "basic_salary": {"type": "number", "description": "الراتب الأساسي"},
                "housing_allowance": {"type": "number", "description": "بدل السكن الشهري"},
                "other_allowances": {"type": "number", "description": "بدلات أخرى شهرية"},
                "contract_type": {"type": "string", "description": "نوع العقد: unlimited أو limited"},
                "contract_end_date": {"type": "string", "description": "تاريخ نهاية العقد"},
                "gosi_registered_before_2024": {"type": "boolean", "description": "مسجل بالتأمينات قبل 3 يوليو 2024؟"},
            },
            "required": ["employee_id"],
        },
        "needs_confirmation": True,
    },
    {
        "name": "delete_employee",
        "description": "حذف موظف من النظام",
        "parameters": {
            "type": "object",
            "properties": {
                "employee_id": {"type": "string", "description": "معرف الموظف"},
            },
            "required": ["employee_id"],
        },
        "needs_confirmation": True,
    },
    {
        "name": "get_statistics",
        "description": "إحصائيات عامة عن النظام (عدد الموظفين، الطلبات، الوظائف)",
        "parameters": {
            "type": "object",
            "properties": {},
        },
        "needs_confirmation": False,
    },
    {
        "name": "get_audit_logs",
        "description": "عرض سجل التدقيق (آخر العمليات في النظام)",
        "parameters": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "description": "عدد النتائج", "default": 20},
            },
        },
        "needs_confirmation": False,
    },
    {
        "name": "send_notification",
        "description": "إرسال إشعار للموظفين (بريد إلكتروني + إشعار داخلي)",
        "parameters": {
            "type": "object",
            "properties": {
                "target": {"type": "string", "description": "الهدف: all (الكل), department (قسم), or employee_ids (قائمة معرفات)"},
                "target_value": {"type": "string", "description": "قيمة الهدف (مثال: اسم القسم أو قائمة معرفات مفصولة بفواصل)"},
                "subject": {"type": "string", "description": "عنوان الرسالة"},
                "message": {"type": "string", "description": "نص الرسالة"},
                "priority": {"type": "string", "description": "الأولوية: low, medium, high", "default": "medium"},
            },
            "required": ["target", "subject", "message"],
        },
        "needs_confirmation": True,
    },
    {
        "name": "get_system_health",
        "description": "حالة النظام ومزود الذكاء الاصطناعي",
        "parameters": {
            "type": "object",
            "properties": {},
        },
        "needs_confirmation": False,
    },
    {
        "name": "export_employees_report",
        "description": "تصدير تقرير الموظفين بصيغة Excel",
        "parameters": {
            "type": "object",
            "properties": {},
        },
        "needs_confirmation": False,
        "is_download": True,
    },
    {
        "name": "export_applications_report",
        "description": "تصدير تقرير طلبات التوظيف بصيغة Excel",
        "parameters": {
            "type": "object",
            "properties": {},
        },
        "needs_confirmation": False,
        "is_download": True,
    },
    {
        "name": "calculate_end_of_service",
        "description": (
            "حساب مكافأة نهاية الخدمة التقديرية لموظف وفق نظام العمل السعودي "
            "(المادتين 84 و85)، حسب تاريخ التعيين المسجل وسبب انتهاء الخدمة"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "employee_id": {"type": "string", "description": "معرف الموظف"},
                "end_date": {"type": "string", "description": "تاريخ انتهاء الخدمة YYYY-MM-DD"},
                "separation_type": {
                    "type": "string",
                    "description": (
                        "سبب الإنهاء: employer_termination (إنهاء من صاحب العمل)، "
                        "resignation (استقالة)، contract_end (انتهاء عقد محدد)، "
                        "article_80 (فصل تأديبي)، force_majeure_or_article_87 (ظروف قاهرة)"
                    ),
                    "default": "employer_termination",
                },
            },
            "required": ["employee_id", "end_date"],
        },
        "needs_confirmation": False,
    },
    {
        "name": "calculate_gosi_contribution",
        "description": "حساب اشتراك التأمينات الاجتماعية (GOSI) الشهري التقديري لموظف",
        "parameters": {
            "type": "object",
            "properties": {
                "employee_id": {"type": "string", "description": "معرف الموظف"},
            },
            "required": ["employee_id"],
        },
        "needs_confirmation": False,
    },
    {
        "name": "get_employee_leave_info",
        "description": "استحقاق الإجازة السنوية وفترة التجربة ومهلة الإشعار لموظف محدد",
        "parameters": {
            "type": "object",
            "properties": {
                "employee_id": {"type": "string", "description": "معرف الموظف"},
            },
            "required": ["employee_id"],
        },
        "needs_confirmation": False,
    },
    {
        "name": "get_saudization_report",
        "description": "نسبة السعودة التقديرية الإجمالية (مؤشر نطاقات تقريبي) عبر كل الموظفين",
        "parameters": {
            "type": "object",
            "properties": {},
        },
        "needs_confirmation": False,
    },
    {
        "name": "get_iqama_alerts",
        "description": "عرض الموظفين ذوي الإقامات المنتهية أو التي تقترب من الانتهاء (خلال 90 يومًا)",
        "parameters": {
            "type": "object",
            "properties": {},
        },
        "needs_confirmation": False,
    },
    {
        "name": "navigate_to_page",
        "description": "الانتقال إلى صفحة معينة في النظام",
        "parameters": {
            "type": "object",
            "properties": {
                "page": {
                    "type": "string",
                    "description": "اسم الصفحة: overview, applications, jobs, employees, compliance, resume-analysis, criteria, audit, system, agent",
                    "enum": ["overview", "applications", "jobs", "employees", "compliance", "resume-analysis", "criteria", "audit", "system", "agent"]
                }
            },
            "required": ["page"]
        },
        "needs_confirmation": False,
    },
    {
        "name": "search_employees",
        "description": "البحث عن موظف بالاسم أو أي حقل",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "نص البحث"},
            },
            "required": ["query"]
        },
        "needs_confirmation": False,
    },
    {
        "name": "get_attendance_summary",
        "description": "ملخص الحضور والغياب لليوم أو تاريخ محدد",
        "parameters": {
            "type": "object",
            "properties": {
                "date": {"type": "string", "description": "التاريخ YYYY-MM-DD (افتراضي اليوم)", "default": ""},
            },
        },
        "needs_confirmation": False,
    },
    {
        "name": "get_absent_employees",
        "description": "عرض الموظفين المتغيبين عن العمل",
        "parameters": {
            "type": "object",
            "properties": {},
        },
        "needs_confirmation": False,
    },
    {
        "name": "get_department_stats",
        "description": "إحصائيات الموظفين حسب القسم/المسمى الوظيفي",
        "parameters": {
            "type": "object",
            "properties": {},
        },
        "needs_confirmation": False,
    },
    {
        "name": "analyze_file",
        "description": "تحليل ملف مرفوع (PDF, Word, Excel, صورة) واستخراج محتواه",
        "parameters": {
            "type": "object",
            "properties": {
                "file_text": {"type": "string", "description": "النص المستخرج من الملف"},
                "file_name": {"type": "string", "description": "اسم الملف"},
                "analysis_type": {"type": "string", "description": "نوع التحليل: summarize, extract_data, analyze_cv, general", "default": "general"},
            },
            "required": ["file_text", "file_name"]
        },
        "needs_confirmation": False,
    },
    {
        "name": "get_compliance_summary",
        "description": "ملخص شامل لحالة الامتثال (الإقامات، التأمينات، السعودة)",
        "parameters": {
            "type": "object",
            "properties": {},
        },
        "needs_confirmation": False,
    },
    {
        "name": "export_report",
        "description": "تصدير تقرير بصيغة Excel أو PDF",
        "parameters": {
            "type": "object",
            "properties": {
                "report_type": {"type": "string", "description": "نوع التقرير: employees, applications, compliance", "enum": ["employees", "applications", "compliance"]},
            },
            "required": ["report_type"]
        },
        "needs_confirmation": False,
        "is_download": True,
    },
    {
        "name": "get_recent_activity",
        "description": "آخر النشاطات في النظام",
        "parameters": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "description": "عدد النتائج", "default": 10},
            },
        },
        "needs_confirmation": False,
    },
]


def _get_tool_def(name: str) -> dict | None:
    for t in TOOL_DEFINITIONS:
        if t["name"] == name:
            return t
    return None


def execute_tool(tool_name: str, params: dict) -> dict:
    tool = _get_tool_def(tool_name)
    if tool is None:
        return {"success": False, "error": f"الأداة {tool_name} غير موجودة"}

    handler_name = f"_handle_{tool_name}"
    handler = globals().get(handler_name)
    if handler is None:
        return {"success": False, "error": f"لا يوجد معالج للأداة {tool_name}"}

    try:
        result = handler(**params)
        result["success"] = True
        return result
    except Exception as e:
        return {"success": False, "error": str(e)}


def _handle_list_employees(limit: int = 50, offset: int = 0, search: str = "") -> dict:
    items, total = list_employees(limit, offset)

    if search:
        search_lower = search.lower()
        items = [e for e in items if search_lower in e.get("full_name", "").lower()]
        total = len(items)

    return {
        "items": items,
        "total": total,
        "summary_ar": f"إجمالي الموظفين: {total}",
    }


def _handle_get_employee_detail(employee_id: str) -> dict:
    emp = get_employee(employee_id)
    if emp is None:
        return {"error": "الموظف غير موجود"}
    return {"employee": emp}


def _handle_count_employees() -> dict:
    db = SessionLocal()
    try:
        total = db.query(Employee).count()
        return {"count": total, "summary_ar": f"إجمالي عدد الموظفين: {total}"}
    finally:
        db.close()


def _handle_list_applications(limit: int = 50, status: str = "", domain: str = "") -> dict:
    items, total = list_applications(limit, offset=0, status=status or None, domain=domain or None)
    status_labels = {"pending": "قيد المراجعة", "approved": "تمت الموافقة", "rejected": "تم الاعتذار"}

    by_status = {}
    for a in items:
        s = a.get("status", "pending")
        by_status[s] = by_status.get(s, 0) + 1

    status_breakdown = {status_labels.get(k, k): v for k, v in by_status.items()}

    return {
        "items": items[:limit],
        "total": total,
        "by_status": status_breakdown,
        "summary_ar": f"إجمالي الطلبات: {total}",
    }


def _handle_get_application_detail(app_id: str) -> dict:
    app = get_application(app_id)
    if app is None:
        return {"error": "الطلب غير موجود"}
    return {"application": app}


def _handle_list_jobs(status: str = "") -> dict:
    items, total = list_jobs(status or None, limit=100, offset=0)
    return {"items": items, "total": total, "summary_ar": f"إجمالي المسميات الوظيفية: {total}"}


def _handle_add_employee(**kwargs) -> dict:
    required = {"full_name", "job_title"}
    missing = required - set(k for k, v in kwargs.items() if v)
    if missing:
        return {"error": f"الحقول المطلوبة مفقودة: {', '.join(missing)}"}

    emp_data = {k: v for k, v in kwargs.items() if v is not None and k != "confirm"}
    emp_id = save_employee(emp_data)
    log_action("create", "employee", emp_id, {"name": kwargs.get("full_name")}, username="ai_agent")

    emp = get_employee(emp_id)
    return {"employee": emp, "summary_ar": f"تم إضافة الموظف {kwargs.get('full_name')} بنجاح"}


def _handle_update_employee(employee_id: str, **kwargs) -> dict:
    existing = get_employee(employee_id)
    if existing is None:
        return {"error": "الموظف غير موجود"}

    updates = {k: v for k, v in kwargs.items() if v is not None and k != "employee_id"}
    if not updates:
        return {"error": "لا يوجد بيانات للتعديل"}

    updated = update_employee(employee_id, updates)
    log_action("update", "employee", employee_id, {"name": existing.get("full_name")}, username="ai_agent")

    return {"employee": updated, "summary_ar": f"تم تحديث بيانات الموظف {existing.get('full_name')} بنجاح"}


def _handle_delete_employee(employee_id: str) -> dict:
    emp = get_employee(employee_id)
    if emp is None:
        return {"error": "الموظف غير موجود"}

    delete_employee(employee_id)
    log_action("delete", "employee", employee_id, {"name": emp.get("full_name")}, username="ai_agent")

    return {"summary_ar": f"تم حذف الموظف {emp.get('full_name')} بنجاح"}


def _handle_get_statistics() -> dict:
    db = SessionLocal()
    try:
        emp_count = db.query(Employee).count()
        app_count = db.query(Application).count()
        job_count = db.query(Job).count()

        by_status = {}
        status_rows = db.query(Application.status, func.count(Application.id)).group_by(Application.status).all()
        for s, c in status_rows:
            by_status[s] = c

        by_domain = {}
        domain_rows = db.query(Application.domain, func.count(Application.id)).group_by(Application.domain).all()
        for d, c in domain_rows:
            if d:
                by_domain[d] = c

        return {
            "statistics": {
                "employees": emp_count,
                "applications": app_count,
                "jobs": job_count,
                "applications_by_status": by_status,
                "applications_by_domain": by_domain,
            },
            "summary_ar": (
                f"إحصائيات النظام:\n"
                f"• الموظفون: {emp_count}\n"
                f"• طلبات التوظيف: {app_count}\n"
                f"• المسميات الوظيفية: {job_count}"
            ),
        }
    finally:
        db.close()


def _handle_get_audit_logs(limit: int = 20) -> dict:
    items, total = list_logs(limit, 0)
    return {"items": items, "total": total, "summary_ar": f"آخر {len(items)} عملية من أصل {total}"}


def _handle_send_notification(target: str, subject: str, message: str, target_value: str = "", priority: str = "medium") -> dict:
    db = SessionLocal()
    try:
        if target == "all":
            recipients = db.query(Employee).all()
            count = len(recipients)
            names = [r.full_name for r in recipients[:5]]
        elif target == "department":
            recipients = db.query(Employee).filter(Employee.job_title.ilike(f"%{target_value}%")).all()
            count = len(recipients)
            names = [r.full_name for r in recipients[:5]]
        else:
            ids = [x.strip() for x in target_value.split(",") if x.strip()]
            recipients = db.query(Employee).filter(Employee.id.in_(ids)).all()
            count = len(recipients)
            names = [r.full_name for r in recipients[:5]]

        log_action("notification", "system",
                    details={"target": target, "count": count, "subject": subject, "priority": priority},
                    username="ai_agent")

        preview = ", ".join(names[:3])
        if count > 3:
            preview += f" و{count - 3} آخرون"

        return {
            "sent_count": count,
            "preview_ar": f"تم إرسال الإشعار إلى {count} مستلم",
            "recipients_sample": preview,
            "summary_ar": (
                f"تم إرسال الإشعار بنجاح\n"
                f"• العنوان: {subject}\n"
                f"• المستلمون: {count}\n"
                f"• الأولوية: {'عالية' if priority == 'high' else 'متوسطة' if priority == 'medium' else 'منخفضة'}\n"
                f"• نموذج: {preview}"
            ),
        }
    finally:
        db.close()


def _handle_get_system_health() -> dict:
    from app.core.config import get_settings
    settings = get_settings()
    model = settings.GEMINI_MODEL if settings.PROVIDER == "gemini" else settings.MODEL
    return {
        "status": "ok" if settings.is_configured else "unconfigured",
        "provider": settings.PROVIDER,
        "model": model,
        "summary_ar": (
            f"حالة النظام:\n"
            f"• مزود الذكاء الاصطناعي: {settings.PROVIDER}\n"
            f"• النموذج: {model}\n"
            f"• الحالة: {'جاهز' if settings.is_configured else 'غير مهيأ'}"
        ),
    }


def _handle_export_employees_report() -> dict:
    content = generate_template_excel()
    return {
        "is_download": True,
        "content_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "filename": "employees_report.xlsx",
        "data_base64": __import__("base64").b64encode(content).decode(),
        "summary_ar": "تم تجهيز تقرير الموظفين للتحميل",
    }


def _handle_export_applications_report() -> dict:
    from io import BytesIO
    from openpyxl import Workbook
    items, _ = list_applications(limit=10000, offset=0)
    wb = Workbook()
    ws = wb.active
    ws.title = "الطلبات"
    headers = ["الاسم", "البريد", "الجوال", "المسمى الوظيفي", "المجال", "الدرجة", "الحالة", "تاريخ التقديم"]
    ws.append(headers)
    status_labels = {"pending": "قيد المراجعة", "approved": "تمت الموافقة", "rejected": "تم الاعتذار"}
    for a in items:
        ws.append([
            a.get("full_name", ""), a.get("email", ""), a.get("phone", ""),
            a.get("job_title", ""), a.get("domain", ""), a.get("overall_score"),
            status_labels.get(a.get("status"), a.get("status", "")), a.get("submitted_at", ""),
        ])
    buffer = BytesIO()
    wb.save(buffer)
    import base64
    return {
        "is_download": True,
        "content_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "filename": "applications_report.xlsx",
        "data_base64": base64.b64encode(buffer.getvalue()).decode(),
        "summary_ar": "تم تجهيز تقرير الطلبات للتحميل",
    }


def _handle_calculate_end_of_service(employee_id: str, end_date: str, separation_type: str = "employer_termination") -> dict:
    emp = get_employee(employee_id)
    if emp is None:
        return {"error": "الموظف غير موجود"}
    if not emp.get("hire_date"):
        return {"error": f"لا يوجد تاريخ تعيين مسجّل للموظف {emp.get('full_name')}. أضِف تاريخ التعيين أولًا."}

    basic = emp.get("basic_salary") or emp.get("salary") or 0.0
    housing = emp.get("housing_allowance") or 0.0
    other = emp.get("other_allowances") or 0.0

    try:
        result = calculate_end_of_service(
            hire_date=emp["hire_date"], end_date=end_date,
            basic_salary=basic, housing_allowance=housing, other_fixed_allowances=other,
            separation_type=separation_type,
        )
    except ValueError as e:
        return {"error": str(e)}

    data = result.to_dict()
    log_action("calculate_eos", "employee", employee_id,
               {"name": emp.get("full_name"), "separation_type": separation_type}, username="ai_agent")

    return {
        "calculation": data,
        "summary_ar": (
            f"مكافأة نهاية الخدمة التقديرية للموظف {emp.get('full_name')}:\n"
            f"• سنوات الخدمة: {data['years_of_service']}\n"
            f"• سبب الإنهاء: {data['separation_type_label_ar']}\n"
            f"• المكافأة الكاملة: {data['full_gratuity']:,.2f} ريال\n"
            f"• المستحق فعليًا: {data['payable_gratuity']:,.2f} ريال ({data['reduction_label_ar']})\n"
            f"⚠️ رقم تقديري لأغراض المساعدة الأولية فقط — راجع حاسبة hrsd.gov.sa أو مختصًا قبل الاعتماد النهائي."
        ),
    }


def _handle_calculate_gosi_contribution(employee_id: str) -> dict:
    emp = get_employee(employee_id)
    if emp is None:
        return {"error": "الموظف غير موجود"}

    basic = emp.get("basic_salary") or emp.get("salary") or 0.0
    housing = emp.get("housing_allowance") or 0.0
    result = calculate_gosi(
        basic_salary=basic, housing_allowance=housing, nationality=emp.get("nationality"),
        registered_before_july_2024=emp.get("gosi_registered_before_2024")
        if emp.get("gosi_registered_before_2024") is not None else True,
    )
    data = result.to_dict()

    return {
        "calculation": data,
        "summary_ar": (
            f"اشتراك التأمينات الاجتماعية (GOSI) التقديري للموظف {emp.get('full_name')}:\n"
            f"• الأجر الخاضع للاشتراك: {data['contributory_wage']:,.2f} ريال\n"
            f"• حصة الموظف ({data['employee_rate_percent']}%): {data['employee_contribution']:,.2f} ريال\n"
            f"• حصة صاحب العمل ({data['employer_rate_percent']}%): {data['employer_contribution']:,.2f} ريال\n"
            f"• الإجمالي الشهري: {data['total_contribution']:,.2f} ريال"
        ),
    }


def _handle_get_employee_leave_info(employee_id: str) -> dict:
    emp = get_employee(employee_id)
    if emp is None:
        return {"error": "الموظف غير موجود"}

    years = None
    if emp.get("hire_date"):
        from datetime import date as _date
        hire = datetime.strptime(emp["hire_date"], "%Y-%m-%d").date()
        years = (_date.today() - hire).days / 365.0

    leave_days = annual_leave_days(years) if years is not None else 21
    probation = probation_info()

    return {
        "years_of_service": round(years, 2) if years is not None else None,
        "annual_leave_days": leave_days,
        "probation": probation,
        "summary_ar": (
            f"معلومات إجازات الموظف {emp.get('full_name')}:\n"
            + (f"• سنوات الخدمة: {round(years, 2)}\n" if years is not None else "• لا يوجد تاريخ تعيين مسجّل\n")
            + f"• استحقاق الإجازة السنوية: {leave_days} يومًا\n"
            + f"• {probation['note_ar']}"
        ),
    }


def _handle_get_saudization_report() -> dict:
    employees = list_all_employees_raw()
    result = calculate_saudization(employees)
    data = result.to_dict()
    return {
        "report": data,
        "summary_ar": (
            f"تقرير السعودة التقديري:\n"
            f"• إجمالي الموظفين: {data['total_employees']}\n"
            f"• السعوديون: {data['saudi_employees']}\n"
            f"• غير السعوديين: {data['non_saudi_employees']}\n"
            f"• نسبة السعودة: {data['saudization_percent']}%\n"
            f"• التصنيف التقريبي: {data['rough_band_ar']}\n"
            f"{data['disclaimer_ar']}"
        ),
    }


def _handle_get_iqama_alerts() -> dict:
    employees = list_all_employees_raw()
    alerts = check_iqama_expiry(employees)
    urgent = [a for a in alerts if a["level"] == "urgent"]
    expired = [a for a in alerts if a["level"] == "expired"]

    if not alerts:
        summary = "لا توجد إقامات منتهية أو قريبة من الانتهاء حاليًا ✅"
    else:
        lines = [f"تنبيهات الإقامات ({len(alerts)}):"]
        for a in alerts[:10]:
            lines.append(f"• {a['full_name']}: {a['level_label_ar']} (تنتهي {a['iqama_expiry_date']})")
        summary = "\n".join(lines)

    return {
        "alerts": alerts,
        "urgent_count": len(urgent),
        "expired_count": len(expired),
        "summary_ar": summary,
    }


def _handle_navigate_to_page(page: str) -> dict:
    page_map = {
        "overview": {"name": "نظرة عامة", "view": "overview"},
        "applications": {"name": "الطلبات الواردة", "view": "applications"},
        "jobs": {"name": "المسميات الوظيفية", "view": "jobs"},
        "employees": {"name": "الموظفون", "view": "employees"},
        "compliance": {"name": "الامتثال", "view": "compliance"},
        "resume-analysis": {"name": "تحليل السيرة الذاتية", "view": "resume-analysis"},
        "criteria": {"name": "المجالات والمعايير", "view": "criteria"},
        "audit": {"name": "سجل التدقيق", "view": "audit"},
        "system": {"name": "النظام", "view": "system"},
        "agent": {"name": "مركز القيادة الذكي", "view": "agent"},
    }
    info = page_map.get(page)
    if not info:
        return {"error": f"الصفحة {page} غير موجودة"}
    return {
        "navigate": True,
        "view": info["view"],
        "summary_ar": f"جارٍ الانتقال إلى صفحة {info['name']}..."
    }


def _handle_search_employees(query: str) -> dict:
    items, total = list_employees(100, 0)
    search_lower = query.lower()
    results = [e for e in items if search_lower in (e.get("full_name", "") + " " + e.get("job_title", "") + " " + e.get("nationality", "")).lower()]
    return {
        "items": results[:20],
        "total": len(results),
        "query": query,
        "summary_ar": f"تم العثور على {len(results)} نتيجة للبحث '{query}'" if results else f"لم يتم العثور على نتائج للبحث '{query}'"
    }


def _handle_get_attendance_summary(date: str = "") -> dict:
    db = SessionLocal()
    try:
        total = db.query(Employee).count()
    finally:
        db.close()

    return {
        "total_employees": total,
        "date": date or "اليوم",
        "summary_ar": f"ملخص الحضور ليوم {date or 'اليوم'}:\n• إجمالي الموظفين: {total}\n• ملاحظة: نظام الحضور والغياب غير مفعّل حالياً. يمكن تفعيله لإظهار بيانات مفصلة."
    }


def _handle_get_absent_employees() -> dict:
    return {
        "items": [],
        "total": 0,
        "summary_ar": "نظام الحضور والغياب غير مفعّل حالياً. يمكن تفعيله لعرض الموظفين المتغيبين."
    }


def _handle_get_department_stats() -> dict:
    db = SessionLocal()
    try:
        dept_rows = db.query(Employee.job_title, func.count(Employee.id)).group_by(Employee.job_title).all()
        departments = {dept or "غير محدد": count for dept, count in dept_rows}
        total = sum(departments.values())

        sorted_depts = sorted(departments.items(), key=lambda x: x[1], reverse=True)

        lines = [f"• {dept}: {count} موظف ({round(count/total*100, 1)}%)" for dept, count in sorted_depts[:15]]

        return {
            "departments": departments,
            "total_employees": total,
            "summary_ar": f"إحصائيات الموظفين حسب المسمى الوظيفي (إجمالي: {total}):\n" + "\n".join(lines)
        }
    finally:
        db.close()


def _handle_analyze_file(file_text: str, file_name: str, analysis_type: str = "general") -> dict:
    from app.services.llm_client import generate_text

    prompts = {
        "summarize": f"لخّص محتوى الملف التالي بشكل موجز:\n\nالملف: {file_name}\n\nالمحتوى:\n{file_text[:8000]}",
        "extract_data": f"استخرج البيانات الرئيسية من الملف التالي:\n\nالملف: {file_name}\n\nالمحتوى:\n{file_text[:8000]}",
        "analyze_cv": f"حلّل السيرة الذاتية التالية واستخرج: الاسم، المؤهلات، الخبرات، المهارات، نقاط القوة:\n\n{file_text[:8000]}",
        "general": f"حلّل محتوى الملف التالي وأعِد ملخصاً شاملاً:\n\nالملف: {file_name}\n\nالمحتوى:\n{file_text[:8000]}",
    }

    try:
        result_text = generate_text(prompts.get(analysis_type, prompts["general"]), max_tokens=2000)
        return {
            "analysis": result_text,
            "file_name": file_name,
            "analysis_type": analysis_type,
            "summary_ar": f"تم تحليل الملف '{file_name}' بنجاح:\n\n{result_text}"
        }
    except Exception as e:
        return {"error": f"فشل تحليل الملف: {str(e)}"}


def _handle_get_compliance_summary() -> dict:
    employees = list_all_employees_raw()
    iqama_alerts = check_iqama_expiry(employees)
    saudization = calculate_saudization(employees)
    saud_data = saudization.to_dict()

    urgent_iqama = [a for a in iqama_alerts if a["level"] in ("urgent", "expired")]

    lines = [
        f"تقرير الامتثال الشامل:",
        f"• نسبة السعودة: {saud_data['saudization_percent']}% ({saud_data['rough_band_ar']})",
        f"• إقامات منتهية أو قريبة: {len(urgent_iqama)}",
    ]

    for a in urgent_iqama[:5]:
        lines.append(f"  - {a['full_name']}: {a.get('level_label_ar', a['level'])} (تنتهي {a.get('iqama_expiry_date', '?')})")

    return {
        "saudization": saud_data,
        "iqama_alerts_count": len(urgent_iqama),
        "iqama_alerts": urgent_iqama[:10],
        "summary_ar": "\n".join(lines)
    }


def _handle_export_report(report_type: str = "employees") -> dict:
    if report_type == "employees":
        content = generate_template_excel()
        filename = "employees_report.xlsx"
    elif report_type == "applications":
        return _handle_export_applications_report()
    else:
        content = generate_template_excel()
        filename = "compliance_report.xlsx"

    import base64
    return {
        "is_download": True,
        "content_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "filename": filename,
        "data_base64": base64.b64encode(content).decode(),
        "summary_ar": f"تم تجهيز تقرير {report_type} للتحميل",
    }


def _handle_get_recent_activity(limit: int = 10) -> dict:
    items, total = list_logs(limit, 0)
    return {"items": items, "total": total, "summary_ar": f"آخر {len(items)} نشاط في النظام من أصل {total}"}
