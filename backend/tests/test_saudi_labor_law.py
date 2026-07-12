"""اختبارات لا تحتاج قاعدة بيانات — تتحقق من صحة حسابات الامتثال السعودي."""
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.saudi_labor_law import (
    calculate_gosi,
    calculate_end_of_service,
    calculate_saudization,
    check_iqama_expiry,
    annual_leave_days,
    probation_info,
    days_until,
)


# ---------------------------------------------------------------------------
# GOSI
# ---------------------------------------------------------------------------

def test_gosi_saudi_existing_system():
    result = calculate_gosi(basic_salary=8000, housing_allowance=2000, is_saudi=True,
                             registered_before_july_2024=True)
    assert result.system == "existing"
    assert result.contributory_wage == 10000
    # 9.75% من 10000 = 975
    assert result.employee_contribution == 975.0
    # 11.75% من 10000 = 1175
    assert result.employer_contribution == 1175.0


def test_gosi_non_saudi_employer_only():
    result = calculate_gosi(basic_salary=6000, housing_allowance=1000, is_saudi=False)
    assert result.system == "non_saudi"
    assert result.employee_contribution == 0.0
    assert result.employer_contribution == round(7000 * 0.02, 2)


def test_gosi_wage_ceiling_applied():
    result = calculate_gosi(basic_salary=40000, housing_allowance=10000, is_saudi=True,
                             registered_before_july_2024=True)
    assert result.contributory_wage == 45000
    assert len(result.notes_ar) >= 1


def test_gosi_new_system_rate_for_2026():
    result = calculate_gosi(
        basic_salary=10000, housing_allowance=0, is_saudi=True,
        registered_before_july_2024=False, as_of=date(2026, 8, 1),
    )
    assert result.system == "new"
    # اعتبارًا من 1 يوليو 2026: 10.75% / 12.75%
    assert round(result.employee_rate, 4) == 0.1075
    assert round(result.employer_rate, 4) == 0.1275


def test_gosi_infers_saudi_from_nationality_text():
    result = calculate_gosi(basic_salary=5000, nationality="سعودي")
    assert result.is_saudi is True
    result2 = calculate_gosi(basic_salary=5000, nationality="Egyptian")
    assert result2.is_saudi is False


# ---------------------------------------------------------------------------
# End of service gratuity
# ---------------------------------------------------------------------------

def test_eos_termination_under_five_years():
    result = calculate_end_of_service(
        hire_date="2022-01-01", end_date="2024-01-01",
        basic_salary=6000, separation_type="employer_termination",
    )
    # سنتان × نصف شهر = شهر كامل من الراتب تقريبًا
    assert 5800 < result.payable_gratuity < 6200


def test_eos_resignation_under_two_years_gets_nothing():
    result = calculate_end_of_service(
        hire_date="2024-01-01", end_date="2025-06-01",
        basic_salary=5000, separation_type="resignation",
    )
    assert result.payable_gratuity == 0.0


def test_eos_resignation_between_five_and_ten_gets_two_thirds():
    result = calculate_end_of_service(
        hire_date="2016-01-01", end_date="2023-01-01",
        basic_salary=10000, separation_type="resignation",
    )
    assert round(result.reduction_factor, 3) == round(2 / 3, 3)


def test_eos_article_80_gets_nothing():
    result = calculate_end_of_service(
        hire_date="2015-01-01", end_date="2023-01-01",
        basic_salary=10000, separation_type="article_80",
    )
    assert result.payable_gratuity == 0.0


def test_eos_rejects_end_before_hire():
    try:
        calculate_end_of_service(hire_date="2024-01-01", end_date="2023-01-01", basic_salary=5000)
        assert False, "should have raised"
    except ValueError:
        pass


# ---------------------------------------------------------------------------
# الإجازات وفترة التجربة
# ---------------------------------------------------------------------------

def test_annual_leave_before_and_after_five_years():
    assert annual_leave_days(3) == 21
    assert annual_leave_days(5) == 30
    assert annual_leave_days(9) == 30


def test_probation_capped_at_max():
    info = probation_info(agreed_days=200)
    assert info["probation_days"] == 180


# ---------------------------------------------------------------------------
# نطاقات (Nitaqat) تقديري
# ---------------------------------------------------------------------------

def test_saudization_percent_calculation():
    employees = [
        {"nationality": "سعودي"},
        {"nationality": "سعودي"},
        {"nationality": "Egyptian"},
        {"nationality": "Indian"},
    ]
    result = calculate_saudization(employees)
    assert result.total_employees == 4
    assert result.saudi_employees == 2
    assert result.saudization_percent == 50.0


def test_saudization_empty_list():
    result = calculate_saudization([])
    assert result.saudization_percent == 0.0


# ---------------------------------------------------------------------------
# تنبيهات الإقامة
# ---------------------------------------------------------------------------

def test_iqama_alerts_flags_urgent_and_expired():
    today = date(2026, 7, 12)
    employees = [
        {"id": "1", "full_name": "أحمد", "iqama_expiry_date": "2026-07-20"},  # عاجل
        {"id": "2", "full_name": "محمد", "iqama_expiry_date": "2026-06-01"},  # منتهية
        {"id": "3", "full_name": "سالم", "iqama_expiry_date": "2027-07-01"},  # سارية
    ]
    alerts = check_iqama_expiry(employees, as_of=today)
    ids = {a["employee_id"] for a in alerts}
    assert ids == {"1", "2"}
    levels = {a["employee_id"]: a["level"] for a in alerts}
    assert levels["1"] == "urgent"
    assert levels["2"] == "expired"


def test_days_until_helper():
    assert days_until("2026-07-20", as_of=date(2026, 7, 12)) == 8
