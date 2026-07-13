"""نقاط النهاية (API endpoints)."""
from __future__ import annotations

import uuid
from datetime import datetime
from io import BytesIO

from fastapi import APIRouter, Cookie, Depends, File, Form, HTTPException, Request, Response, UploadFile
from openpyxl import Workbook

from app.core.config import get_settings
from app.schemas.analysis import (
    AddQuestionRequest,
    ApplicationDetail,
    ApplicationStatusResponse,
    ApplicationSubmitResponse,
    ApplicationSummary,
    CVAnalysisRequest,
    CVAnalysisResult,
    EditQuestionRequest,
    ExtractedText,
    ExtractUrlRequest,
    FinalRecommendation,
    HiringDecisionRequest,
    InterviewApproveRequest,
    InterviewRejectRequest,
    QuestionsResponse,
    VoiceEvaluateRequest,
    VoiceInterviewQuestionsResponse,
    VoiceInterviewResult,
    VoiceTurnRequest,
    WrittenTestResult,
    WrittenTestSubmitRequest,
)
from app.schemas.auth import AuthStatusResponse, ChangePasswordRequest, LoginRequest
from app.schemas.employees import (
    Employee,
    EmployeeCreateRequest,
    EmployeeUpdateRequest,
    EndOfServiceRequest,
    GosiCalcRequest,
    ImportResult,
)
from app.schemas.criteria import (
    CriterionCreate,
    CriterionResponse,
    CriterionUpdate,
    DomainCreate,
    DomainResponse,
    DomainUpdate,
)
from app.schemas.jobs import Job, JobCreateRequest, JobUpdateRequest
from app.services.application_store import (
    delete_application,
    delete_applications_batch,
    get_application,
    list_applications,
    save_application,
    update_application,
)
from app.services.audit_logger import list_logs, log_action
from app.services.auth import (
    authenticate,
    change_password,
    create_session,
    destroy_session,
    is_default_password_changed,
    verify_session,
)
from app.services.criteria_loader import (
    CriteriaError,
    list_available_domains,
    load_criteria,
)
from app.services.criteria_service import (
    add_criterion,
    create_domain,
    delete_criterion,
    delete_domain,
    get_domain,
    get_domain_by_key,
    list_domains,
    update_criterion,
    update_domain,
)
from app.services.cv_analyzer import AnalysisError, analyze_cv
from app.services.document_extractor import (
    ExtractionError,
    extract_text_from_file,
    extract_text_from_url,
)
from app.services.email_service import send_status_notification
from app.services.employee_import import EmployeeImportError, generate_template_excel, parse_employees_excel
from app.services.employee_store import (
    delete_employee,
    get_employee,
    list_all_employees_raw,
    list_employees,
    save_employee,
    update_employee,
)
from app.services.saudi_labor_law import (
    calculate_end_of_service,
    calculate_gosi,
    calculate_saudization,
    check_iqama_expiry,
    annual_leave_days,
    probation_info,
    sick_leave_schedule,
    NOTICE_PERIOD_INFO_AR,
    SEPARATION_TYPES,
)
from app.services.interview_questions import (
    QuestionGenerationError,
    generate_interview_questions,
)
from app.services.job_store import delete_job, get_job, list_jobs, save_job, update_job
from app.services.recommendation import RecommendationError, generate_final_recommendation
from app.services.voice_interview import VoiceEvaluationError, evaluate_voice_interview
from app.services.written_test import WrittenTestError, score_written_test
from app.schemas.agent import AgentChatRequest, AgentChatResponse, AgentConfirmRequest
from app.services.agent_engine import process_message, confirm_and_execute, clear_conversation

router = APIRouter(prefix="/api/v1")

SESSION_COOKIE = "hr_session"


def require_admin(hr_session: str | None = Cookie(default=None)) -> None:
    """حماية نقاط النهاية الخاصة بفريق HR — تُستخدم كـ Depends في كل endpoint إداري."""
    if not verify_session(hr_session):
        raise HTTPException(status_code=401, detail="يجب تسجيل الدخول للوصول لهذه البيانات")


@router.post("/auth/login")
def login(req: LoginRequest, response: Response, request: Request) -> dict:
    """تسجيل دخول فريق HR للوحة الداخلية."""
    if not authenticate(req.username, req.password):
        log_action("login_failed", "auth", username=req.username, ip_address=request.client.host if request.client else None)
        raise HTTPException(status_code=401, detail="اسم المستخدم أو كلمة المرور غير صحيحة")

    token = create_session()
    response.set_cookie(
        key=SESSION_COOKIE,
        value=token,
        httponly=True,
        samesite="lax",
        max_age=12 * 3600,
    )

    log_action("login", "auth", username=req.username, ip_address=request.client.host if request.client else None)

    return {
        "ok": True,
        "must_change_password": not is_default_password_changed(),
    }


@router.post("/auth/logout")
def logout(response: Response, hr_session: str | None = Cookie(default=None)) -> dict:
    """تسجيل خروج فريق HR."""
    destroy_session(hr_session)
    response.delete_cookie(SESSION_COOKIE)
    return {"ok": True}


@router.get("/auth/status", response_model=AuthStatusResponse)
def auth_status(hr_session: str | None = Cookie(default=None)) -> dict:
    """يستخدمها الفرونت إند للتحقق هل الجلسة الحالية مسجّلة دخول."""
    authenticated = verify_session(hr_session)
    return {
        "authenticated": authenticated,
        "must_change_password": not is_default_password_changed() if authenticated else False,
    }


@router.post("/auth/change-password")
def change_password_endpoint(
    req: ChangePasswordRequest, _admin: None = Depends(require_admin), request: Request = None
) -> dict:
    """تغيير كلمة مرور حساب HR — يُحدّث ملف .env مباشرة ليصمد بعد إعادة التشغيل."""
    try:
        change_password(req.current_password, req.new_password)
        log_action("change_password", "auth",
                   ip_address=request.client.host if request and request.client else None)
    except PermissionError as e:
        log_action("change_password_failed", "auth",
                   details={"reason": str(e)},
                   ip_address=request.client.host if request and request.client else None)
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"ok": True}


def _check_voice_eligibility(record: dict, email: str) -> None:
    if record.get("email", "").strip().lower() != email.strip().lower():
        raise HTTPException(status_code=404, detail="لم يتم العثور على طلب مطابق لهذا البريد.")

    if record.get("status") != "approved":
        raise HTTPException(status_code=403, detail="لم تتم الموافقة على المقابلة بعد.")

    dt_str = record.get("interview_datetime")
    if not dt_str:
        raise HTTPException(status_code=403, detail="لم يُحدد موعد للمقابلة بعد.")

    try:
        interview_dt = datetime.fromisoformat(dt_str)
    except ValueError:
        raise HTTPException(status_code=500, detail="صيغة موعد المقابلة غير صالحة.")

    if datetime.now() < interview_dt:
        raise HTTPException(
            status_code=403,
            detail=f"المقابلة لم يحن موعدها بعد. الموعد المحدد: {dt_str}",
        )


@router.post("/extract/file", response_model=ExtractedText)
async def extract_file(file: UploadFile, _admin: None = Depends(require_admin)) -> ExtractedText:
    """استخراج نص السيرة الذاتية من ملف مرفق (PDF/DOCX/TXT)."""
    content = await file.read()
    try:
        text = extract_text_from_file(file.filename or "", content)
    except ExtractionError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return ExtractedText(text=text)


@router.post("/extract/url", response_model=ExtractedText)
def extract_url(req: ExtractUrlRequest, _admin: None = Depends(require_admin)) -> ExtractedText:
    """استخراج نص السيرة الذاتية من رابط موقع."""
    try:
        text = extract_text_from_url(str(req.url))
    except ExtractionError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return ExtractedText(text=text)


# --- المجالات ومعايير التقييم (CRUD كامل) ---


@router.get("/domains")
def get_domains() -> dict:
    """المجالات المتاحة حالياً."""
    domains = list_domains()
    return {
        "domains": [d["key"] for d in domains],
        "items": domains,
    }


@router.get("/criteria/{domain}")
def get_criteria(domain: str) -> dict:
    """عرض معايير مجال معيّن — يفيد لوحة الإدارة."""
    try:
        return load_criteria(domain)
    except CriteriaError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/domains", response_model=DomainResponse)
def create_domain_endpoint(
    req: DomainCreate,
    _admin: None = Depends(require_admin),
    request: Request = None,
) -> dict:
    """إضافة مجال جديد مع معاييره."""
    try:
        result = create_domain(req.model_dump())
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    log_action("create", "domain", result["id"], {"key": req.key, "domain_ar": req.domain_ar},
               ip_address=request.client.host if request and request.client else None)
    return result


@router.put("/domains/{domain_id}", response_model=DomainResponse)
def update_domain_endpoint(
    domain_id: str,
    req: DomainUpdate,
    _admin: None = Depends(require_admin),
    request: Request = None,
) -> dict:
    """تعديل مجال (الاسم، الملاحظات، المعايير)."""
    updates = {k: v for k, v in req.model_dump().items() if v is not None}
    result = update_domain(domain_id, updates)
    if result is None:
        raise HTTPException(status_code=404, detail="المجال غير موجود")
    log_action("update", "domain", domain_id, {"key": result["key"]},
               ip_address=request.client.host if request and request.client else None)
    return result


@router.delete("/domains/{domain_id}")
def delete_domain_endpoint(
    domain_id: str,
    _admin: None = Depends(require_admin),
    request: Request = None,
) -> dict:
    """حذف مجال وجميع معاييره."""
    if not delete_domain(domain_id):
        raise HTTPException(status_code=404, detail="المجال غير موجود")
    log_action("delete", "domain", domain_id,
               ip_address=request.client.host if request and request.client else None)
    return {"ok": True}


@router.post("/domains/{domain_id}/criteria", response_model=CriterionResponse)
def add_criterion_endpoint(
    domain_id: str,
    req: CriterionCreate,
    _admin: None = Depends(require_admin),
    request: Request = None,
) -> dict:
    """إضافة معيار جديد إلى مجال."""
    try:
        result = add_criterion(domain_id, req.model_dump())
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    log_action("create", "criterion", result["id"], {"key": req.key, "domain_id": domain_id},
               ip_address=request.client.host if request and request.client else None)
    return result


@router.put("/criteria/{criterion_id}", response_model=CriterionResponse)
def update_criterion_endpoint(
    criterion_id: str,
    req: CriterionUpdate,
    _admin: None = Depends(require_admin),
    request: Request = None,
) -> dict:
    """تعديل معيار."""
    updates = {k: v for k, v in req.model_dump().items() if v is not None}
    result = update_criterion(criterion_id, updates)
    if result is None:
        raise HTTPException(status_code=404, detail="المعيار غير موجود")
    log_action("update", "criterion", criterion_id,
               ip_address=request.client.host if request and request.client else None)
    return result


@router.delete("/criteria/{criterion_id}")
def delete_criterion_endpoint(
    criterion_id: str,
    _admin: None = Depends(require_admin),
    request: Request = None,
) -> dict:
    """حذف معيار."""
    if not delete_criterion(criterion_id):
        raise HTTPException(status_code=404, detail="المعيار غير موجود")
    log_action("delete", "criterion", criterion_id,
               ip_address=request.client.host if request and request.client else None)
    return {"ok": True}


@router.get("/jobs")
def get_jobs(status: str | None = None, limit: int = 50, offset: int = 0) -> dict:
    """قائمة الوظائف — عامة (تستخدمها صفحة التقديم لعرض الوظائف المفتوحة)."""
    items, total = list_jobs(status, limit, offset)
    return {"items": items, "total": total}


@router.post("/jobs", response_model=Job)
def create_job(req: JobCreateRequest, _admin: None = Depends(require_admin), request: Request = None) -> dict:
    """إضافة وظيفة جديدة."""
    job_id = save_job(req.model_dump())
    log_action("create", "job", job_id, {"title": req.title},
               ip_address=request.client.host if request and request.client else None)
    return get_job(job_id)


@router.put("/jobs/{job_id}", response_model=Job)
def edit_job(
    job_id: str, req: JobUpdateRequest, _admin: None = Depends(require_admin), request: Request = None
) -> dict:
    """تعديل بيانات وظيفة أو حالتها (فتح/إغلاق)."""
    updates = {k: v for k, v in req.model_dump().items() if v is not None}
    updated = update_job(job_id, updates)
    if updated is None:
        raise HTTPException(status_code=404, detail="المسمى الوظيفي غير موجود")
    log_action("update", "job", job_id, {"title": updated.get("title")},
               ip_address=request.client.host if request and request.client else None)
    return updated


@router.delete("/jobs/{job_id}")
def remove_job(job_id: str, _admin: None = Depends(require_admin), request: Request = None) -> dict:
    """حذف وظيفة."""
    job = get_job(job_id)
    if not delete_job(job_id):
        raise HTTPException(status_code=404, detail="المسمى الوظيفي غير موجود")
    log_action("delete", "job", job_id, {"title": job.get("title") if job else None},
               ip_address=request.client.host if request and request.client else None)
    return {"ok": True}


# --- بيانات الموظفين: رواتب، جنسيات، إقامات — بيانات حساسة، كل النقاط هنا محمية بالكامل ---


@router.get("/employees")
def get_employees(
    limit: int = 50, offset: int = 0, _admin: None = Depends(require_admin)
) -> dict:
    """قائمة الموظفين."""
    items, total = list_employees(limit, offset)
    return {"items": items, "total": total}


@router.post("/employees", response_model=Employee)
def create_employee(req: EmployeeCreateRequest, _admin: None = Depends(require_admin), request: Request = None) -> dict:
    """إضافة موظف يدويًا."""
    emp_id = save_employee(req.model_dump())
    log_action("create", "employee", emp_id, {"name": req.full_name},
               ip_address=request.client.host if request and request.client else None)
    return get_employee(emp_id)


@router.put("/employees/{employee_id}", response_model=Employee)
def edit_employee(
    employee_id: str, req: EmployeeUpdateRequest, _admin: None = Depends(require_admin), request: Request = None
) -> dict:
    """تعديل بيانات موظف."""
    updates = {k: v for k, v in req.model_dump().items() if v is not None}
    updated = update_employee(employee_id, updates)
    if updated is None:
        raise HTTPException(status_code=404, detail="الموظف غير موجود")
    log_action("update", "employee", employee_id, {"name": updated.get("full_name")},
               ip_address=request.client.host if request and request.client else None)
    return updated


@router.delete("/employees/{employee_id}")
def remove_employee(employee_id: str, _admin: None = Depends(require_admin), request: Request = None) -> dict:
    """حذف موظف."""
    emp = get_employee(employee_id)
    if not delete_employee(employee_id):
        raise HTTPException(status_code=404, detail="الموظف غير موجود")
    log_action("delete", "employee", employee_id, {"name": emp.get("full_name") if emp else None},
               ip_address=request.client.host if request and request.client else None)
    return {"ok": True}


@router.get("/employees/export/excel")
def export_employees_excel(_admin: None = Depends(require_admin)) -> Response:
    """تصدير بيانات الموظفين إلى ملف Excel."""
    items, _ = list_employees(limit=10000, offset=0)
    wb = Workbook()
    ws = wb.active
    ws.title = "الموظفون"
    headers = [
        "الاسم", "الرقم الوظيفي", "الجنسية", "المسمى الوظيفي", "الجوال", "الراتب",
        "رقم الإقامة", "تاريخ انتهاء الإقامة", "رقم الهوية", "تاريخ التعيين",
        "الراتب الأساسي", "بدل السكن", "بدلات أخرى", "نوع العقد", "تاريخ نهاية العقد",
    ]
    ws.append(headers)
    for e in items:
        ws.append([
            e.get("full_name", ""),
            e.get("employee_number", ""),
            e.get("nationality", ""),
            e.get("job_title", ""),
            e.get("phone", ""),
            e.get("salary"),
            e.get("iqama_number", ""),
            e.get("iqama_expiry_date", ""),
            e.get("national_id", ""),
            e.get("hire_date", ""),
            e.get("basic_salary"),
            e.get("housing_allowance"),
            e.get("other_allowances"),
            e.get("contract_type", ""),
            e.get("contract_end_date", ""),
        ])
    buffer = BytesIO()
    wb.save(buffer)
    return Response(
        content=buffer.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=employees.xlsx"},
    )


@router.get("/employees/import/template", include_in_schema=False)
def download_employee_template(_admin: None = Depends(require_admin)) -> Response:
    """تنزيل نموذج Excel فارغ بالأعمدة الصحيحة لاستيراد الموظفين."""
    content = generate_template_excel()
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=employee_template.xlsx"},
    )


@router.post("/employees/import", response_model=ImportResult)
async def import_employees(
    file: UploadFile, _admin: None = Depends(require_admin), request: Request = None
) -> dict:
    """استيراد بيانات الموظفين دفعة واحدة من ملف Excel."""
    content = await file.read()
    try:
        employees, errors = parse_employees_excel(content)
    except EmployeeImportError as e:
        raise HTTPException(status_code=400, detail=str(e))

    for emp in employees:
        save_employee(emp)

    log_action("import", "employee", details={"count": len(employees), "errors": len(errors)},
               ip_address=request.client.host if request and request.client else None)

    return {"imported": len(employees), "errors": errors}


# ============================================================================
# الامتثال لنظام العمل السعودي — GOSI، مكافأة نهاية الخدمة، نطاقات، الإقامات
# ============================================================================

@router.get("/compliance/employees/{employee_id}/gosi")
def get_employee_gosi(
    employee_id: str, _admin: None = Depends(require_admin),
) -> dict:
    """يحسب اشتراك التأمينات الاجتماعية (GOSI) الشهري التقديري لموظف محدد."""
    emp = get_employee(employee_id)
    if emp is None:
        raise HTTPException(status_code=404, detail="الموظف غير موجود")

    basic = emp.get("basic_salary") or emp.get("salary") or 0.0
    housing = emp.get("housing_allowance") or 0.0
    result = calculate_gosi(
        basic_salary=basic,
        housing_allowance=housing,
        nationality=emp.get("nationality"),
        registered_before_july_2024=emp.get("gosi_registered_before_2024")
        if emp.get("gosi_registered_before_2024") is not None else True,
    )
    return result.to_dict()


@router.post("/compliance/employees/{employee_id}/gosi")
def post_employee_gosi(
    employee_id: str, req: GosiCalcRequest, _admin: None = Depends(require_admin),
) -> dict:
    """نفس حساب GOSI لكن مع إمكانية تجاوز الراتب/نوع التسجيل لغرض المحاكاة."""
    emp = get_employee(employee_id)
    if emp is None:
        raise HTTPException(status_code=404, detail="الموظف غير موجود")

    basic = req.basic_salary_override if req.basic_salary_override is not None else (
        emp.get("basic_salary") or emp.get("salary") or 0.0
    )
    housing = req.housing_allowance_override if req.housing_allowance_override is not None else (
        emp.get("housing_allowance") or 0.0
    )
    registered_before = (
        req.registered_before_july_2024 if req.registered_before_july_2024 is not None
        else (emp.get("gosi_registered_before_2024") if emp.get("gosi_registered_before_2024") is not None else True)
    )
    result = calculate_gosi(
        basic_salary=basic, housing_allowance=housing,
        nationality=emp.get("nationality"), registered_before_july_2024=registered_before,
    )
    return result.to_dict()


@router.post("/compliance/employees/{employee_id}/end-of-service")
def post_end_of_service(
    employee_id: str, req: EndOfServiceRequest, _admin: None = Depends(require_admin), request: Request = None,
) -> dict:
    """يحسب مكافأة نهاية الخدمة التقديرية لموظف عند إنهاء خدمته."""
    emp = get_employee(employee_id)
    if emp is None:
        raise HTTPException(status_code=404, detail="الموظف غير موجود")
    if not emp.get("hire_date"):
        raise HTTPException(status_code=400, detail="لا يوجد تاريخ تعيين مسجّل لهذا الموظف")

    basic = req.basic_salary_override if req.basic_salary_override is not None else (
        emp.get("basic_salary") or emp.get("salary") or 0.0
    )
    housing = req.housing_allowance_override if req.housing_allowance_override is not None else (
        emp.get("housing_allowance") or 0.0
    )
    other = req.other_allowances_override if req.other_allowances_override is not None else (
        emp.get("other_allowances") or 0.0
    )

    try:
        result = calculate_end_of_service(
            hire_date=emp["hire_date"], end_date=req.end_date,
            basic_salary=basic, housing_allowance=housing, other_fixed_allowances=other,
            separation_type=req.separation_type,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    log_action("calculate_eos", "employee", employee_id,
               {"name": emp.get("full_name"), "separation_type": req.separation_type},
               ip_address=request.client.host if request and request.client else None)
    return result.to_dict()


@router.get("/compliance/employees/{employee_id}/leave")
def get_employee_leave_info(
    employee_id: str, _admin: None = Depends(require_admin),
) -> dict:
    """معلومات استحقاق الإجازة السنوية وفترة التجربة لموظف محدد."""
    emp = get_employee(employee_id)
    if emp is None:
        raise HTTPException(status_code=404, detail="الموظف غير موجود")

    years = None
    if emp.get("hire_date"):
        from datetime import date, datetime as dt
        hire = dt.strptime(emp["hire_date"], "%Y-%m-%d").date()
        years = (date.today() - hire).days / 365.0

    return {
        "years_of_service": round(years, 2) if years is not None else None,
        "annual_leave_days": annual_leave_days(years) if years is not None else None,
        "probation": probation_info(),
        "notice_period": NOTICE_PERIOD_INFO_AR,
        "sick_leave": sick_leave_schedule(),
    }


@router.get("/compliance/saudization")
def get_saudization_report(_admin: None = Depends(require_admin)) -> dict:
    """نسبة السعودة الإجمالية (تقديرية) عبر كل الموظفين المسجّلين."""
    employees = list_all_employees_raw()
    result = calculate_saudization(employees)
    return result.to_dict()


@router.get("/compliance/iqama-alerts")
def get_iqama_alerts(_admin: None = Depends(require_admin)) -> dict:
    """قائمة الموظفين ذوي الإقامات المنتهية أو التي تقترب من الانتهاء."""
    employees = list_all_employees_raw()
    alerts = check_iqama_expiry(employees)
    return {
        "alerts": alerts,
        "urgent_count": sum(1 for a in alerts if a["level"] == "urgent"),
        "expired_count": sum(1 for a in alerts if a["level"] == "expired"),
        "warning_count": sum(1 for a in alerts if a["level"] == "warning"),
    }


@router.get("/compliance/separation-types")
def get_separation_types(_admin: None = Depends(require_admin)) -> dict:
    """قائمة أنواع إنهاء الخدمة المدعومة لحساب مكافأة نهاية الخدمة."""
    return {"types": [{"key": k, "label_ar": v} for k, v in SEPARATION_TYPES.items()]}


@router.post("/analyze", response_model=CVAnalysisResult)
def post_analyze(req: CVAnalysisRequest, _admin: None = Depends(require_admin)) -> CVAnalysisResult:
    """تحليل سيرة ذاتية مقابل معايير المجال."""
    try:
        return analyze_cv(req.cv_text, req.job_title, req.domain)
    except (AnalysisError, CriteriaError) as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/apply", response_model=ApplicationSubmitResponse)
async def submit_application(
    full_name: str = Form(...),
    email: str = Form(...),
    phone: str | None = Form(None),
    job_title: str = Form(...),
    domain: str | None = Form(None),
    file: UploadFile = File(...),
) -> ApplicationSubmitResponse:
    """استقبال طلب تقديم من صفحة التقديم الخارجية، مع استخراج وتحليل السيرة الذاتية."""
    content = await file.read()
    try:
        cv_text = extract_text_from_file(file.filename or "", content)
    except ExtractionError as e:
        raise HTTPException(status_code=400, detail=str(e))

    record = {
        "full_name": full_name,
        "email": email,
        "phone": phone,
        "job_title": job_title,
        "domain": domain,
        "cv_text": cv_text,
    }

    try:
        result = analyze_cv(cv_text, job_title, domain)
        record["overall_score"] = result.overall_score
        record["recommendation_ar"] = result.recommendation_ar
        record["result"] = result.model_dump()
    except (AnalysisError, CriteriaError) as e:
        # لا نفشل استقبال الطلب بسبب خطأ في التحليل الآلي — يبقى متاحاً لمراجعة يدوية
        record["analysis_error"] = str(e)

    app_id = save_application(record)
    return ApplicationSubmitResponse(id=app_id)


@router.get("/applications")
def get_applications(
    limit: int = 50,
    offset: int = 0,
    search: str | None = None,
    status: str | None = None,
    domain: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    _admin: None = Depends(require_admin),
) -> dict:
    """قائمة الطلبات الواردة — لاستخدام فريق HR فقط. تدعم البحث والفلترة."""
    items, total = list_applications(limit, offset, search, status, domain, date_from, date_to)
    return {"items": items, "total": total}


@router.get("/applications/export/excel")
def export_applications_excel(_admin: None = Depends(require_admin)) -> Response:
    """تصدير جدول الطلبات إلى ملف Excel."""
    items, _ = list_applications(limit=10000, offset=0)
    wb = Workbook()
    ws = wb.active
    ws.title = "الطلبات"
    headers = ["الاسم", "البريد", "الجوال", "المسمى الوظيفي", "المجال", "الدرجة", "الحالة", "تاريخ التقديم",
               "موعد المقابلة", "القرار النهائي"]
    ws.append(headers)
    status_labels = {"pending": "قيد المراجعة", "approved": "تمت الموافقة", "rejected": "تم الاعتذار"}
    decision_labels = {"accepted": "تم القبول", "rejected": "تم الرفض"}
    for a in items:
        ws.append([
            a.get("full_name", ""),
            a.get("email", ""),
            a.get("phone", ""),
            a.get("job_title", ""),
            a.get("domain", ""),
            a.get("overall_score"),
            status_labels.get(a.get("status"), a.get("status", "")),
            a.get("submitted_at", ""),
            a.get("interview_datetime", ""),
            decision_labels.get(a.get("hiring_decision"), a.get("hiring_decision", "")),
        ])
    buffer = BytesIO()
    wb.save(buffer)
    return Response(
        content=buffer.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=applications.xlsx"},
    )


@router.get("/applications/status", response_model=ApplicationStatusResponse)
def check_application_status(id: str, email: str) -> dict:
    """يستخدمها المرشح للتحقق من حالة طلبه (بريده + رقم مرجعي الطلب)."""
    record = get_application(id)
    if record is None or record.get("email", "").strip().lower() != email.strip().lower():
        raise HTTPException(
            status_code=404,
            detail="لم يتم العثور على طلب مطابق لهذا البريد ورقم الطلب.",
        )
    return record


@router.get("/applications/{app_id}", response_model=ApplicationDetail)
def get_application_detail(app_id: str, _admin: None = Depends(require_admin)) -> dict:
    """تفاصيل طلب تقديم واحد — لاستخدام فريق HR فقط."""
    record = get_application(app_id)
    if record is None:
        raise HTTPException(status_code=404, detail="الطلب غير موجود")
    return record


@router.delete("/applications/{app_id}")
def delete_application_endpoint(
    app_id: str,
    _admin: None = Depends(require_admin),
    request: Request = None,
) -> dict:
    """حذف طلب تقديم واحد."""
    if not delete_application(app_id):
        raise HTTPException(status_code=404, detail="الطلب غير موجود")
    log_action("delete", "application", app_id,
               ip_address=request.client.host if request and request.client else None)
    return {"ok": True}


@router.post("/applications/batch-delete")
def batch_delete_applications(
    ids: list[str],
    _admin: None = Depends(require_admin),
    request: Request = None,
) -> dict:
    """حذف مجموعة من الطلبات دفعة واحدة."""
    count = delete_applications_batch(ids)
    log_action("batch_delete", "application", details={"count": count, "ids": ids},
               ip_address=request.client.host if request and request.client else None)
    return {"ok": True, "deleted": count}


@router.post("/applications/{app_id}/approve", response_model=ApplicationDetail)
def approve_application(
    app_id: str, req: InterviewApproveRequest, _admin: None = Depends(require_admin), request: Request = None
) -> dict:
    """موافقة على المرشح للحضور للمقابلة مع تحديد الموعد."""
    if get_application(app_id) is None:
        raise HTTPException(status_code=404, detail="الطلب غير موجود")

    updated = update_application(
        app_id,
        {
            "status": "approved",
            "interview_datetime": req.interview_datetime,
            "note_ar": req.note_ar,
        },
    )

    log_action("approve", "application", app_id,
               {"name": updated.get("full_name"), "interview": req.interview_datetime},
               ip_address=request.client.host if request and request.client else None)

    send_status_notification(
        updated.get("email", ""),
        updated.get("full_name", ""),
        "approved",
        req.interview_datetime,
    )

    return updated


@router.post("/applications/{app_id}/reject", response_model=ApplicationDetail)
def reject_application(
    app_id: str, req: InterviewRejectRequest, _admin: None = Depends(require_admin), request: Request = None
) -> dict:
    """الاعتذار عن طلب المرشح."""
    if get_application(app_id) is None:
        raise HTTPException(status_code=404, detail="الطلب غير موجود")

    updated = update_application(app_id, {"status": "rejected", "note_ar": req.note_ar})

    log_action("reject", "application", app_id,
               {"name": updated.get("full_name")},
               ip_address=request.client.host if request and request.client else None)

    send_status_notification(
        updated.get("email", ""), updated.get("full_name", ""), "rejected", req.note_ar
    )

    return updated


@router.post("/applications/{app_id}/questions/generate", response_model=QuestionsResponse)
def generate_questions_for_application(
    app_id: str, question_type: str = "open", _admin: None = Depends(require_admin)
) -> dict:
    """توليد أسئلة مقابلة بالذكاء الاصطناعي (مفتوحة أو اختيار من متعدد)."""
    if question_type not in ("open", "mcq"):
        raise HTTPException(status_code=400, detail="question_type يجب أن تكون open أو mcq")

    record = get_application(app_id)
    if record is None:
        raise HTTPException(status_code=404, detail="الطلب غير موجود")

    domain_ar = None
    try:
        domain_ar = load_criteria(record.get("domain")).get("domain_ar")
    except CriteriaError:
        pass

    analysis_gaps = None
    if record.get("result"):
        analysis_gaps = record["result"].get("gaps_ar")

    try:
        ai_questions = generate_interview_questions(
            record["cv_text"], record["job_title"], domain_ar, analysis_gaps, question_type
        )
    except QuestionGenerationError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # نستبدل فقط أسئلة الذكاء الاصطناعي من نفس النوع، ونحافظ على البقية (يدوية أو نوع آخر)
    kept = [
        q for q in record.get("questions", [])
        if not (q.get("source") == "ai" and q.get("type", "open") == question_type)
    ]
    new_items = [
        {
            "id": uuid.uuid4().hex[:8],
            "text": q["text"],
            "source": "ai",
            "type": question_type,
            "options": q.get("options"),
            "correct_answer": q.get("correct_answer"),
        }
        for q in ai_questions
    ]
    all_questions = new_items + kept

    updated = update_application(app_id, {"questions": all_questions})
    return {"questions": updated["questions"]}


@router.post("/applications/{app_id}/questions", response_model=QuestionsResponse)
def add_manual_question(
    app_id: str, req: AddQuestionRequest, _admin: None = Depends(require_admin)
) -> dict:
    """إضافة سؤال مقابلة يدوي من فريق HR (مفتوح أو اختيار من متعدد)."""
    record = get_application(app_id)
    if record is None:
        raise HTTPException(status_code=404, detail="الطلب غير موجود")

    questions = record.get("questions", [])
    questions.append(
        {
            "id": uuid.uuid4().hex[:8],
            "text": req.text,
            "source": "hr",
            "type": "mcq" if req.options else "open",
            "options": req.options,
            "correct_answer": req.correct_answer,
        }
    )

    updated = update_application(app_id, {"questions": questions})
    return {"questions": updated["questions"]}


@router.put("/applications/{app_id}/questions/{question_id}", response_model=QuestionsResponse)
def edit_question(
    app_id: str, question_id: str, req: EditQuestionRequest, _admin: None = Depends(require_admin)
) -> dict:
    """تعديل نص/خيارات سؤال موجود (سواء وُلّد بالذكاء الاصطناعي أو أضافه HR)."""
    record = get_application(app_id)
    if record is None:
        raise HTTPException(status_code=404, detail="الطلب غير موجود")

    questions = record.get("questions", [])
    target = next((q for q in questions if q.get("id") == question_id), None)
    if target is None:
        raise HTTPException(status_code=404, detail="السؤال غير موجود")

    target["text"] = req.text
    target["options"] = req.options
    target["correct_answer"] = req.correct_answer
    target["type"] = "mcq" if req.options else "open"

    updated = update_application(app_id, {"questions": questions})
    return {"questions": updated["questions"]}


@router.delete("/applications/{app_id}/questions/{question_id}", response_model=QuestionsResponse)
def delete_question(
    app_id: str, question_id: str, _admin: None = Depends(require_admin)
) -> dict:
    """حذف سؤال من قائمة أسئلة المقابلة (سواء وُلّد بالذكاء الاصطناعي أو أضافه HR)."""
    record = get_application(app_id)
    if record is None:
        raise HTTPException(status_code=404, detail="الطلب غير موجود")

    questions = record.get("questions", [])
    remaining = [q for q in questions if q.get("id") != question_id]
    if len(remaining) == len(questions):
        raise HTTPException(status_code=404, detail="السؤال غير موجود")

    updated = update_application(app_id, {"questions": remaining})
    return {"questions": updated["questions"]}


@router.get("/applications/{app_id}/interview/questions", response_model=VoiceInterviewQuestionsResponse)
def get_voice_interview_questions(app_id: str, email: str) -> dict:
    """يستخدمها المرشح لبدء المقابلة الصوتية — يتحقق من الموافقة والموعد."""
    record = get_application(app_id)
    if record is None:
        raise HTTPException(status_code=404, detail="الطلب غير موجود")
    _check_voice_eligibility(record, email)

    open_questions = [
        q["text"] for q in record.get("questions", []) if q.get("type", "open") == "open"
    ]

    if not open_questions:
        domain_ar = None
        try:
            domain_ar = load_criteria(record.get("domain")).get("domain_ar")
        except CriteriaError:
            pass

        analysis_gaps = record["result"].get("gaps_ar") if record.get("result") else None

        try:
            generated = generate_interview_questions(
                record["cv_text"], record["job_title"], domain_ar, analysis_gaps, "open"
            )
        except QuestionGenerationError as e:
            raise HTTPException(status_code=400, detail=str(e))

        new_items = [
            {
                "id": uuid.uuid4().hex[:8],
                "text": q["text"],
                "source": "ai",
                "type": "open",
                "options": None,
                "correct_answer": None,
            }
            for q in generated
        ]
        update_application(app_id, {"questions": new_items + record.get("questions", [])})
        open_questions = [q["text"] for q in new_items]

    return {
        "full_name": record["full_name"],
        "job_title": record["job_title"],
        "questions": open_questions,
    }


@router.post("/applications/{app_id}/interview/turn")
async def submit_voice_turn(
    app_id: str,
    request: Request,
    email: str = Form(...),
    question_index: int = Form(...),
    question_text: str = Form(...),
    answer_text: str = Form(""),
    file: UploadFile | None = File(None),
) -> dict:
    """يستقبل زوج سؤال/إجابة واحد من المقابلة الصوتية مع إمكانية رفع ملف صوتي."""
    settings = get_settings()
    record = get_application(app_id)
    if record is None:
        raise HTTPException(status_code=404, detail="الطلب غير موجود")
    _check_voice_eligibility(record, email)

    transcript = record.get("voice_transcript", [])
    turn = {
        "question_index": question_index,
        "question": question_text,
        "answer": answer_text,
    }

    # إذا وُجد ملف صوتي، نقرؤه ونخزّن metadata عنه
    if file:
        audio_bytes = await file.read()
        turn["has_audio"] = True
        turn["audio_size"] = len(audio_bytes)
        turn["audio_type"] = file.content_type or "audio/webm"
        turn["audio_filename"] = file.filename or f"answer_{question_index}.webm"

        # نخزّن الصوت في مجلد مؤقت إذا كان متاحًا
        audio_dir = settings.APPLICATIONS_DIR / "audio"
        try:
            audio_dir.mkdir(parents=True, exist_ok=True)
            audio_path = audio_dir / f"{app_id}_{question_index}.webm"
            audio_path.write_bytes(audio_bytes)
            turn["audio_path"] = str(audio_path)
        except OSError:
            # Vercel read-only FS — نخزّن في الـ DB بالـ base64
            import base64
            turn["audio_base64"] = base64.b64encode(audio_bytes).decode()
            turn.pop("audio_path", None)

    transcript.append(turn)
    update_application(app_id, {"voice_transcript": transcript})
    return {"ok": True}


@router.post("/applications/{app_id}/interview/evaluate", response_model=VoiceInterviewResult)
def evaluate_voice_interview_endpoint(app_id: str, req: VoiceEvaluateRequest) -> dict:
    """يقيّم نص المقابلة الصوتية المتراكم عبر أربعة أبعاد ويحفظ النتيجة لفريق HR."""
    record = get_application(app_id)
    if record is None:
        raise HTTPException(status_code=404, detail="الطلب غير موجود")
    _check_voice_eligibility(record, req.email)

    domain_ar = None
    try:
        domain_ar = load_criteria(record.get("domain")).get("domain_ar")
    except CriteriaError:
        pass

    try:
        result = evaluate_voice_interview(
            record.get("voice_transcript", []), record["job_title"], domain_ar
        )
    except VoiceEvaluationError as e:
        raise HTTPException(status_code=400, detail=str(e))

    update_application(app_id, {"voice_interview_result": result})
    return result


@router.post("/applications/{app_id}/written-test/submit", response_model=WrittenTestResult)
def submit_written_test(
    app_id: str, req: WrittenTestSubmitRequest, _admin: None = Depends(require_admin)
) -> dict:
    """يستقبل إجابات اختبار ورقي أدخلها فريق HR يدويًا ويصحّحها (MCQ آليًا، المفتوحة بالذكاء الاصطناعي)."""
    record = get_application(app_id)
    if record is None:
        raise HTTPException(status_code=404, detail="الطلب غير موجود")

    if not req.answers:
        raise HTTPException(status_code=400, detail="لم يتم إرسال أي إجابات.")

    domain_ar = None
    try:
        domain_ar = load_criteria(record.get("domain")).get("domain_ar")
    except CriteriaError:
        pass

    try:
        result = score_written_test(
            record.get("questions", []),
            [a.model_dump() for a in req.answers],
            record["job_title"],
            domain_ar,
        )
    except WrittenTestError as e:
        raise HTTPException(status_code=400, detail=str(e))

    update_application(app_id, {"written_test_result": result})
    return result


@router.post("/applications/{app_id}/recommendation/generate", response_model=FinalRecommendation)
def generate_recommendation_endpoint(
    app_id: str, _admin: None = Depends(require_admin)
) -> dict:
    """يولّد توصية استرشادية نهائية تجمع كل مصادر التقييم المتاحة — القرار يبقى للـ HR."""
    record = get_application(app_id)
    if record is None:
        raise HTTPException(status_code=404, detail="الطلب غير موجود")

    domain_ar = None
    try:
        domain_ar = load_criteria(record.get("domain")).get("domain_ar")
    except CriteriaError:
        pass

    try:
        result = generate_final_recommendation(
            record["job_title"],
            domain_ar,
            record.get("result"),
            record.get("voice_interview_result"),
            record.get("written_test_result"),
        )
    except RecommendationError as e:
        raise HTTPException(status_code=400, detail=str(e))

    update_application(app_id, {"final_recommendation": result})
    return result


@router.post("/applications/{app_id}/decision", response_model=ApplicationDetail)
def set_hiring_decision(
    app_id: str, req: HiringDecisionRequest, _admin: None = Depends(require_admin), request: Request = None
) -> dict:
    """قرار HR النهائي بقبول أو رفض المرشح، مع ملاحظات تُعرض له عند التحقق من حالة طلبه."""
    if req.decision not in ("accepted", "rejected"):
        raise HTTPException(status_code=400, detail="decision يجب أن تكون accepted أو rejected")

    record = get_application(app_id)
    if record is None:
        raise HTTPException(status_code=404, detail="الطلب غير موجود")

    feedback = req.feedback_ar
    if not feedback:
        rec = record.get("final_recommendation")
        if rec:
            parts = []
            if rec.get("strengths_ar"):
                parts.append("نقاط القوة: " + "، ".join(rec["strengths_ar"]))
            if rec.get("weaknesses_ar"):
                parts.append("نقاط تحتاج تطوير: " + "، ".join(rec["weaknesses_ar"]))
            feedback = " | ".join(parts) or None

    updated = update_application(
        app_id, {"hiring_decision": req.decision, "hiring_feedback_ar": feedback}
    )

    log_action(req.decision, "application", app_id,
               {"name": updated.get("full_name")},
               ip_address=request.client.host if request and request.client else None)

    send_status_notification(
        updated.get("email", ""), updated.get("full_name", ""), req.decision, feedback
    )

    return updated


@router.get("/audit-logs")
def get_audit_logs(
    limit: int = 100,
    offset: int = 0,
    _admin: None = Depends(require_admin),
) -> dict:
    """سجل التدقيق — آخر العمليات في النظام."""
    items, total = list_logs(limit, offset)
    return {"items": items, "total": total}


# ═══════════════════════════════════════════════════════════════
# AI Command Center — وكيل المحادثة الذكي
# ═══════════════════════════════════════════════════════════════


@router.post("/agent/chat", response_model=AgentChatResponse)
def agent_chat(req: AgentChatRequest, _admin: None = Depends(require_admin)) -> dict:
    """إرسال رسالة إلى وكيل الذكاء الاصطناعي والحصول على رد."""
    conv_id = req.conversation_id if req.conversation_id and req.conversation_id != "null" else None
    result = process_message(req.message, conv_id, current_page=req.current_page, voice_mode=req.voice_mode)
    log_action("agent_chat", "agent",
               details={"message_preview": req.message[:80], "page": req.current_page, "voice": req.voice_mode},
               username="admin")
    return result.model_dump()


@router.post("/agent/confirm", response_model=AgentChatResponse)
def agent_confirm(req: AgentConfirmRequest, _admin: None = Depends(require_admin)) -> dict:
    """تأكيد أو إلغاء طلب تنفيذ أداة من الوكيل."""
    result = confirm_and_execute(req.conversation_id, req.confirm)
    log_action("agent_confirm" if req.confirm else "agent_cancel", "agent",
               details={"conv_id": req.conversation_id},
               username="admin")
    return result.model_dump()


@router.post("/agent/clear")
def agent_clear_conv(conv_id: str, _admin: None = Depends(require_admin)) -> dict:
    """مسح محادثة وكيل الذكاء الاصطناعي."""
    ok = clear_conversation(conv_id)
    return {"ok": ok}
