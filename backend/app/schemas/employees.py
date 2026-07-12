"""مخططات بيانات الموظفين — رواتب، جنسيات، إقامات، وامتثال نظام العمل السعودي."""
from __future__ import annotations

from pydantic import BaseModel, Field


class EmployeeCreateRequest(BaseModel):
    full_name: str = Field(..., min_length=2, description="اسم الموظف")
    employee_number: str | None = None
    nationality: str | None = None
    job_title: str | None = None
    phone: str | None = None
    salary: float | None = None
    iqama_number: str | None = None
    iqama_expiry_date: str | None = Field(None, description="تاريخ انتهاء الإقامة بصيغة YYYY-MM-DD")

    # حقول الامتثال السعودي
    national_id: str | None = Field(None, description="رقم الهوية الوطنية (للسعوديين)")
    hire_date: str | None = Field(None, description="تاريخ التعيين YYYY-MM-DD")
    basic_salary: float | None = Field(None, description="الراتب الأساسي (أساس GOSI ومكافأة نهاية الخدمة)")
    housing_allowance: float | None = 0.0
    other_allowances: float | None = 0.0
    contract_type: str | None = Field("unlimited", description="unlimited أو limited")
    contract_end_date: str | None = None
    probation_end_date: str | None = None
    gosi_registered_before_2024: bool | None = True


class EmployeeUpdateRequest(BaseModel):
    full_name: str | None = None
    employee_number: str | None = None
    nationality: str | None = None
    job_title: str | None = None
    phone: str | None = None
    salary: float | None = None
    iqama_number: str | None = None
    iqama_expiry_date: str | None = None

    national_id: str | None = None
    hire_date: str | None = None
    basic_salary: float | None = None
    housing_allowance: float | None = None
    other_allowances: float | None = None
    contract_type: str | None = None
    contract_end_date: str | None = None
    probation_end_date: str | None = None
    gosi_registered_before_2024: bool | None = None


class Employee(BaseModel):
    id: str
    full_name: str
    employee_number: str | None = None
    nationality: str | None = None
    job_title: str | None = None
    phone: str | None = None
    salary: float | None = None
    iqama_number: str | None = None
    iqama_expiry_date: str | None = None
    created_at: str

    national_id: str | None = None
    hire_date: str | None = None
    basic_salary: float | None = None
    housing_allowance: float | None = None
    other_allowances: float | None = None
    contract_type: str | None = None
    contract_end_date: str | None = None
    probation_end_date: str | None = None
    gosi_registered_before_2024: bool | None = None


class ImportRowError(BaseModel):
    row: int
    reason: str


class ImportResult(BaseModel):
    imported: int
    errors: list[ImportRowError]


# --- طلبات أدوات الامتثال ---

class EndOfServiceRequest(BaseModel):
    end_date: str = Field(..., description="تاريخ انتهاء الخدمة YYYY-MM-DD")
    separation_type: str = Field(
        "employer_termination",
        description="employer_termination | resignation | contract_end | article_80 | force_majeure_or_article_87",
    )
    # اختياري: تجاوز رواتب الموظف المخزنة برقم مخصص لغرض المحاكاة
    basic_salary_override: float | None = None
    housing_allowance_override: float | None = None
    other_allowances_override: float | None = None


class GosiCalcRequest(BaseModel):
    basic_salary_override: float | None = None
    housing_allowance_override: float | None = None
    registered_before_july_2024: bool | None = None
