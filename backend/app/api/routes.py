"""نقاط النهاية (API endpoints)."""
from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Cookie, Depends, File, Form, HTTPException, Request, Response, UploadFile

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
    ImportResult,
)
from app.schemas.jobs import Job, JobCreateRequest, JobUpdateRequest
from app.services.application_store import (
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
from app.services.cv_analyzer import AnalysisError, analyze_cv
from app.services.document_extractor import (
    ExtractionError,
    extract_text_from_file,
    extract_text_from_url,
)
from app.services.employee_import import EmployeeImportError, generate_template_excel, parse_employees_excel
from app.services.employee_store import (
    delete_employee,
    get_employee,
    list_employees,
    save_employee,
    update_employee,
)
from app.services.interview_questions import (
    QuestionGenerationError,
    generate_interview_questions,
)
from app.services.job_store import delete_job, get_job, list_jobs, save_job, update_job
from app.services.recommendation import RecommendationError, generate_final_recommendation
from app.services.voice_interview import VoiceEvaluationError, evaluate_voice_interview
from app.services.written_test import WrittenTestError, score_written_test

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


@router.get("/domains")
def get_domains() -> dict:
    """المجالات المتاحة حالياً."""
    return {"domains": list_available_domains()}


@router.get("/criteria/{domain}")
def get_criteria(domain: str) -> dict:
    """عرض معايير مجال معيّن — يفيد لوحة الإدارة."""
    try:
        return load_criteria(domain)
    except CriteriaError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/jobs", response_model=list[Job])
def get_jobs(status: str | None = None) -> list[dict]:
    """قائمة الوظائف — عامة (تستخدمها صفحة التقديم لعرض الوظائف المفتوحة)."""
    return list_jobs(status)


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


@router.get("/employees", response_model=list[Employee])
def get_employees(_admin: None = Depends(require_admin)) -> list[dict]:
    """قائمة الموظفين."""
    return list_employees()


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


@router.get("/applications", response_model=list[ApplicationSummary])
def get_applications(_admin: None = Depends(require_admin)) -> list[dict]:
    """قائمة الطلبات الواردة — لاستخدام فريق HR فقط."""
    return list_applications()


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
def submit_voice_turn(app_id: str, req: VoiceTurnRequest) -> dict:
    """يستقبل زوج سؤال/إجابة واحد من المقابلة الصوتية ويضيفه لنص المحادثة المتراكم."""
    record = get_application(app_id)
    if record is None:
        raise HTTPException(status_code=404, detail="الطلب غير موجود")
    _check_voice_eligibility(record, req.email)

    transcript = record.get("voice_transcript", [])
    transcript.append(
        {
            "question_index": req.question_index,
            "question": req.question_text,
            "answer": req.answer_text,
        }
    )
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

    return updated


@router.get("/audit-logs")
def get_audit_logs(
    limit: int = 100,
    offset: int = 0,
    _admin: None = Depends(require_admin),
) -> list[dict]:
    """سجل التدقيق — آخر العمليات في النظام."""
    return list_logs(limit, offset)
