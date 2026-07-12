"""منطق الامتثال لنظام العمل السعودي، نظام التأمينات الاجتماعية (GOSI)، وبرنامج نطاقات.

المرجعية القانونية (بحسب أحدث تحديث متاح وقت كتابة هذا الملف):
- نظام العمل السعودي الصادر بالمرسوم الملكي رقم م/51 وتعديلاته — المواد 75، 79 مكرر،
  80، 84، 85، 87، 109.
- نظام التأمينات الاجتماعية الجديد الساري اعتبارًا من 3 يوليو 2024، مع جدول زيادة
  تدريجية سنوية حتى عام 2028.
- برنامج نطاقات (التوطين) الصادر عن وزارة الموارد البشرية والتنمية الاجتماعية.

⚠️ تنبيه مهم: هذه الحسابات **تقديرية** لأغراض المساعدة الإدارية الأولية فقط.
لا تُغني عن استشارة مختص قانوني أو محاسبي مرخّص، أو الرجوع للأدوات الرسمية:
- حاسبة مكافأة نهاية الخدمة: hrsd.gov.sa
- حاسبة نطاقات الرسمية: qiwa.sa
- التأمينات الاجتماعية: gosi.gov.sa
القيم والنسب القانونية قابلة للتغيير بقرارات وزارية لاحقة.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime


# ============================================================================
# أدوات مشتركة
# ============================================================================

def _parse_date(value: str | date) -> date:
    if isinstance(value, date):
        return value
    return datetime.strptime(value, "%Y-%m-%d").date()


def _is_saudi_nationality(nationality: str | None) -> bool:
    """يحدد إن كانت الجنسية سعودية من نص حر (سعودي/سعودية/Saudi/KSA...)."""
    if not nationality:
        return False
    n = nationality.strip().lower()
    saudi_markers = ["سعود", "ksa", "saudi"]
    return any(marker in n for marker in saudi_markers)


# ============================================================================
# 1) التأمينات الاجتماعية (GOSI)
# ============================================================================

GOSI_WAGE_CEILING = 45000.0  # الحد الأقصى الشهري للأجر الخاضع للاشتراك (ريال)

# النظام القائم (قبل 3 يوليو 2024): نسب ثابتة
EXISTING_SYSTEM_EMPLOYEE_RATE = 0.0975  # 9% تقاعد + 0.75% ساند
EXISTING_SYSTEM_EMPLOYER_RATE = 0.1175  # 9% تقاعد + 2% أخطار مهنية + 0.75% ساند

# النظام الجديد (لمن لا اشتراك سابق له قبل 3 يوليو 2024): زيادة تدريجية كل 1 يوليو
# كل عنصر: (تاريخ بدء السريان, نسبة الموظف, نسبة صاحب العمل)
NEW_SYSTEM_SCHEDULE: list[tuple[date, float, float]] = [
    (date(2024, 7, 3), 0.0975, 0.1175),
    (date(2025, 7, 1), 0.1025, 0.1225),
    (date(2026, 7, 1), 0.1075, 0.1275),
    (date(2027, 7, 1), 0.1125, 0.1325),
    (date(2028, 7, 1), 0.1175, 0.1375),  # النسبة النهائية المستهدفة
]

NON_SAUDI_EMPLOYER_RATE = 0.02  # أخطار مهنية فقط — بلا خصم من الموظف وبلا تقاعد/ساند


def _new_system_rates_for_date(as_of: date) -> tuple[float, float]:
    applicable = NEW_SYSTEM_SCHEDULE[0]
    for entry in NEW_SYSTEM_SCHEDULE:
        if entry[0] <= as_of:
            applicable = entry
        else:
            break
    return applicable[1], applicable[2]


@dataclass
class GosiResult:
    contributory_wage: float
    is_saudi: bool
    system: str  # "existing" | "new" | "non_saudi"
    employee_rate: float
    employer_rate: float
    employee_contribution: float
    employer_contribution: float
    total_contribution: float
    notes_ar: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "contributory_wage": self.contributory_wage,
            "is_saudi": self.is_saudi,
            "system": self.system,
            "employee_rate_percent": round(self.employee_rate * 100, 2),
            "employer_rate_percent": round(self.employer_rate * 100, 2),
            "employee_contribution": self.employee_contribution,
            "employer_contribution": self.employer_contribution,
            "total_contribution": self.total_contribution,
            "notes_ar": self.notes_ar,
        }


def calculate_gosi(
    basic_salary: float,
    housing_allowance: float = 0.0,
    nationality: str | None = None,
    is_saudi: bool | None = None,
    registered_before_july_2024: bool = True,
    as_of: date | None = None,
) -> GosiResult:
    """يحسب اشتراك التأمينات الاجتماعية الشهري (تقديري).

    الأجر الخاضع للاشتراك = الراتب الأساسي + بدل السكن فقط (وفق تعريف GOSI)،
    بحد أقصى شهري 45,000 ريال.
    """
    as_of = as_of or date.today()
    if is_saudi is None:
        is_saudi = _is_saudi_nationality(nationality)

    raw_wage = (basic_salary or 0.0) + (housing_allowance or 0.0)
    contributory_wage = min(raw_wage, GOSI_WAGE_CEILING)
    notes: list[str] = []
    if raw_wage > GOSI_WAGE_CEILING:
        notes.append(
            f"الأجر الفعلي ({raw_wage:,.0f} ريال) يتجاوز سقف الاشتراك "
            f"({GOSI_WAGE_CEILING:,.0f} ريال) — تم احتساب الاشتراك على السقف فقط."
        )

    if not is_saudi:
        employer_rate = NON_SAUDI_EMPLOYER_RATE
        employee_rate = 0.0
        system = "non_saudi"
        notes.append(
            "الموظف غير سعودي: اشتراك أخطار مهنية فقط على صاحب العمل (2%)، "
            "بلا خصم من راتب الموظف، وبلا تغطية تقاعد أو تأمين ضد التعطل (ساند)."
        )
    elif registered_before_july_2024:
        employee_rate = EXISTING_SYSTEM_EMPLOYEE_RATE
        employer_rate = EXISTING_SYSTEM_EMPLOYER_RATE
        system = "existing"
        notes.append("النظام القائم: نسب ثابتة 9.75% موظف / 11.75% صاحب عمل (المجموع 21.5%).")
    else:
        employee_rate, employer_rate = _new_system_rates_for_date(as_of)
        system = "new"
        notes.append(
            "النظام الجديد (لموظف بلا اشتراك سابق قبل 3 يوليو 2024): "
            "النسب ترتفع تدريجيًا 0.5% كل طرف في 1 يوليو من كل عام حتى الوصول "
            "إلى 11.75%/13.75% في يوليو 2028."
        )

    employee_contribution = round(contributory_wage * employee_rate, 2)
    employer_contribution = round(contributory_wage * employer_rate, 2)

    return GosiResult(
        contributory_wage=round(contributory_wage, 2),
        is_saudi=is_saudi,
        system=system,
        employee_rate=employee_rate,
        employer_rate=employer_rate,
        employee_contribution=employee_contribution,
        employer_contribution=employer_contribution,
        total_contribution=round(employee_contribution + employer_contribution, 2),
        notes_ar=notes,
    )


# ============================================================================
# 2) مكافأة نهاية الخدمة (Articles 84, 85, 87)
# ============================================================================

SEPARATION_TYPES = {
    "employer_termination": "إنهاء من صاحب العمل (بدون سبب مشروع بموجب المادة 80)",
    "contract_end": "انتهاء مدة العقد المحدد",
    "resignation": "استقالة الموظف",
    "article_80": "فصل بسبب مشروع وفق المادة 80 (لا يستحق مكافأة)",
    "force_majeure_or_article_87": "ظروف قاهرة / حالات المادة 87 الخاصة (تُصرف كاملة)",
}


@dataclass
class EndOfServiceResult:
    years_of_service: float
    full_service_days: int
    base_wage: float
    full_gratuity: float
    reduction_factor: float
    reduction_label_ar: str
    payable_gratuity: float
    separation_type: str
    notes_ar: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "years_of_service": round(self.years_of_service, 2),
            "full_service_days": self.full_service_days,
            "base_wage": self.base_wage,
            "full_gratuity": round(self.full_gratuity, 2),
            "reduction_factor": self.reduction_factor,
            "reduction_label_ar": self.reduction_label_ar,
            "payable_gratuity": round(self.payable_gratuity, 2),
            "separation_type": self.separation_type,
            "separation_type_label_ar": SEPARATION_TYPES.get(self.separation_type, self.separation_type),
            "notes_ar": self.notes_ar,
        }


def _resignation_reduction_factor(years: float) -> tuple[float, str]:
    """معامل تخفيض المكافأة عند الاستقالة وفق المادة 85."""
    if years < 2:
        return 0.0, "أقل من سنتين: لا يستحق مكافأة عند الاستقالة"
    if years < 5:
        return 1 / 3, "من 2 إلى أقل من 5 سنوات: يستحق ثلث المكافأة"
    if years < 10:
        return 2 / 3, "من 5 إلى أقل من 10 سنوات: يستحق ثلثي المكافأة"
    return 1.0, "10 سنوات فأكثر: يستحق المكافأة كاملة"


def calculate_end_of_service(
    hire_date: str | date,
    end_date: str | date,
    basic_salary: float,
    housing_allowance: float = 0.0,
    other_fixed_allowances: float = 0.0,
    separation_type: str = "employer_termination",
) -> EndOfServiceResult:
    """يحسب مكافأة نهاية الخدمة وفق المادتين 84 و85.

    أساس الاحتساب = آخر أجر فعلي (الراتب الأساسي + البدلات الثابتة المنتظمة
    كالسكن والنقل)، وفق التعريف الشائع للأجر في المادة 2. بعض الجهات تحتسبها
    على الراتب الأساسي فقط — تأكد من سياسة شركتك أو استشر مختصًا قبل الاعتماد
    النهائي على الرقم.
    """
    hire = _parse_date(hire_date)
    end = _parse_date(end_date)
    if end < hire:
        raise ValueError("تاريخ الانتهاء يجب أن يكون بعد تاريخ التعيين")

    total_days = (end - hire).days
    years = total_days / 365.0
    monthly_wage = (basic_salary or 0.0) + (housing_allowance or 0.0) + (other_fixed_allowances or 0.0)

    first_five = min(years, 5)
    remaining = max(years - 5, 0)
    full_gratuity = (first_five * 0.5 * monthly_wage) + (remaining * 1.0 * monthly_wage)

    notes: list[str] = [
        "الاحتساب: نصف شهر عن كل سنة من أول 5 سنوات، وشهر كامل عن كل سنة بعدها "
        "(المادة 84)، بالتناسب لأجزاء السنة.",
    ]

    if separation_type == "article_80":
        return EndOfServiceResult(
            years_of_service=years, full_service_days=total_days, base_wage=monthly_wage,
            full_gratuity=full_gratuity, reduction_factor=0.0,
            reduction_label_ar="فصل تأديبي وفق المادة 80 — لا يستحق مكافأة نهاية خدمة",
            payable_gratuity=0.0, separation_type=separation_type,
            notes_ar=notes + ["الفصل بموجب المادة 80 (كالغياب أو الإخلال الجسيم) يُسقط الحق في المكافأة."],
        )

    if separation_type == "resignation":
        factor, label = _resignation_reduction_factor(years)
        payable = full_gratuity * factor
        notes.append("تم تطبيق تخفيض الاستقالة وفق المادة 85 حسب سنوات الخدمة.")
        return EndOfServiceResult(
            years_of_service=years, full_service_days=total_days, base_wage=monthly_wage,
            full_gratuity=full_gratuity, reduction_factor=factor, reduction_label_ar=label,
            payable_gratuity=payable, separation_type=separation_type, notes_ar=notes,
        )

    # إنهاء من صاحب العمل / انتهاء عقد محدد / حالات المادة 87 → المكافأة كاملة
    notes.append("هذا النوع من إنهاء الخدمة يستحق المكافأة كاملة دون تخفيض.")
    return EndOfServiceResult(
        years_of_service=years, full_service_days=total_days, base_wage=monthly_wage,
        full_gratuity=full_gratuity, reduction_factor=1.0,
        reduction_label_ar="مكافأة كاملة", payable_gratuity=full_gratuity,
        separation_type=separation_type, notes_ar=notes,
    )


# ============================================================================
# 3) الإجازات، فترة التجربة، مهلة الإشعار
# ============================================================================

def annual_leave_days(years_of_service: float) -> int:
    """المادة 109: 21 يومًا، وترتفع إلى 30 يومًا بعد 5 سنوات خدمة متصلة."""
    return 30 if years_of_service >= 5 else 21


PROBATION_DEFAULT_DAYS = 90
PROBATION_MAX_DAYS = 180  # بحد أقصى بموافقة كتابية من الموظف (تعديل فبراير 2025)

NOTICE_PERIOD_INFO_AR = {
    "employee_resignation_days": 30,
    "employer_termination_days": 60,
    "note_ar": (
        "للعقود غير محددة المدة المدفوعة شهريًا: مهلة إشعار لا تقل عن 30 يومًا من "
        "الموظف عند الاستقالة، و60 يومًا من صاحب العمل عند الإنهاء ما لم يتفق الطرفان "
        "على خلاف ذلك في العقد (المادة 75 وتعديلاتها). يُنصح بمراجعة نص العقد الفعلي."
    ),
}


def probation_info(agreed_days: int | None = None) -> dict:
    days = agreed_days or PROBATION_DEFAULT_DAYS
    days = min(days, PROBATION_MAX_DAYS)
    return {
        "probation_days": days,
        "default_days": PROBATION_DEFAULT_DAYS,
        "max_days": PROBATION_MAX_DAYS,
        "note_ar": (
            f"فترة التجربة الافتراضية {PROBATION_DEFAULT_DAYS} يومًا، ويجوز تمديدها "
            f"بموافقة كتابية من الموظف بما لا يتجاوز {PROBATION_MAX_DAYS} يومًا إجمالًا."
        ),
    }


def sick_leave_schedule() -> dict:
    return {
        "full_pay_days": 30,
        "partial_pay_days": 60,
        "partial_pay_percent": 75,
        "unpaid_days": 30,
        "total_days_per_year": 120,
        "note_ar": "أول 30 يومًا بأجر كامل، ثم 60 يومًا بـ75% من الأجر، ثم 30 يومًا بلا أجر (المادة 117).",
    }


# ============================================================================
# 4) نطاقات (Nitaqat) — تقدير تقريبي فقط
# ============================================================================

NITAQAT_DISCLAIMER_AR = (
    "⚠️ نطاقات نظام دقيق يعتمد على النشاط الاقتصادي المسجل للمنشأة (ISIC4) وحجمها "
    "الفعلي ومهن محددة (بعضها له حصص سعودة مستقلة كالمحاسبة والهندسة)، ولا توجد نسبة "
    "موحّدة لكل الشركات. الرقم أدناه نسبة السعودة الفعلية في بياناتك فقط كمؤشر عام — "
    "للتصنيف الرسمي الدقيق راجع حاسبة نطاقات على qiwa.sa."
)


@dataclass
class SaudizationResult:
    total_employees: int
    saudi_employees: int
    non_saudi_employees: int
    saudization_percent: float
    rough_band_ar: str
    disclaimer_ar: str = NITAQAT_DISCLAIMER_AR

    def to_dict(self) -> dict:
        return {
            "total_employees": self.total_employees,
            "saudi_employees": self.saudi_employees,
            "non_saudi_employees": self.non_saudi_employees,
            "saudization_percent": round(self.saudization_percent, 1),
            "rough_band_ar": self.rough_band_ar,
            "disclaimer_ar": self.disclaimer_ar,
        }


def _rough_band(pct: float, total_employees: int) -> str:
    """تصنيف تقريبي عام جدًا فقط للاستئناس — ليس التصنيف الرسمي."""
    if total_employees <= 5:
        # منشآت "كيان صغير أ" — تصنيف من فئتين فقط (أخضر/أحمر) حسب توظيف سعودي واحد
        return "أخضر (تقريبي)" if pct > 0 else "أحمر (تقريبي)"
    if pct < 4:
        return "أحمر (تقريبي)"
    if pct < 9:
        return "أحمر إلى منخفض أخضر (تقريبي)"
    if pct < 20:
        return "أخضر منخفض/متوسط (تقريبي)"
    if pct < 38:
        return "أخضر متوسط/مرتفع (تقريبي)"
    return "أخضر مرتفع/بلاتيني محتمل (تقريبي)"


def calculate_saudization(employees: list[dict]) -> SaudizationResult:
    """يحسب نسبة السعودة الإجمالية من قائمة موظفين (كل عنصر يحتوي 'nationality').

    هذا حساب مبسّط على مستوى المنشأة ككل، ولا يراعي أوزان المهن أو الأجور
    (نطاقات موزون) أو تصنيف الأنشطة — راجع الديسكليمر.
    """
    total = len(employees)
    saudi = sum(1 for e in employees if _is_saudi_nationality(e.get("nationality")))
    non_saudi = total - saudi
    pct = (saudi / total * 100) if total else 0.0

    return SaudizationResult(
        total_employees=total,
        saudi_employees=saudi,
        non_saudi_employees=non_saudi,
        saudization_percent=pct,
        rough_band_ar=_rough_band(pct, total),
    )


# ============================================================================
# 5) متابعة الإقامات — تنبيهات انتهاء
# ============================================================================

def days_until(target_date: str | date, as_of: date | None = None) -> int:
    as_of = as_of or date.today()
    return (_parse_date(target_date) - as_of).days


def iqama_alert_level(days_remaining: int) -> str:
    if days_remaining < 0:
        return "expired"
    if days_remaining <= 30:
        return "urgent"
    if days_remaining <= 90:
        return "warning"
    return "ok"


IQAMA_ALERT_LABELS_AR = {
    "expired": "منتهية الصلاحية",
    "urgent": "عاجل — أقل من 30 يومًا",
    "warning": "تنبيه — أقل من 90 يومًا",
    "ok": "سارية",
}


def check_iqama_expiry(employees: list[dict], as_of: date | None = None) -> list[dict]:
    """يفحص قائمة موظفين ويعيد فقط من لديهم إقامة تنتهي قريبًا أو منتهية.

    كل عنصر إدخال متوقع أن يحتوي: id, full_name, iqama_number, iqama_expiry_date.
    """
    as_of = as_of or date.today()
    alerts: list[dict] = []
    for emp in employees:
        expiry = emp.get("iqama_expiry_date")
        if not expiry:
            continue
        try:
            remaining = days_until(expiry, as_of)
        except (ValueError, TypeError):
            continue
        level = iqama_alert_level(remaining)
        if level == "ok":
            continue
        alerts.append({
            "employee_id": emp.get("id"),
            "full_name": emp.get("full_name"),
            "iqama_number": emp.get("iqama_number"),
            "iqama_expiry_date": expiry,
            "days_remaining": remaining,
            "level": level,
            "level_label_ar": IQAMA_ALERT_LABELS_AR[level],
        })
    alerts.sort(key=lambda a: a["days_remaining"])
    return alerts
