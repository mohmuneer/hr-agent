"""مخططات بيانات الموظفين — رواتب، جنسيات، إقامات."""
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


class EmployeeUpdateRequest(BaseModel):
    full_name: str | None = None
    employee_number: str | None = None
    nationality: str | None = None
    job_title: str | None = None
    phone: str | None = None
    salary: float | None = None
    iqama_number: str | None = None
    iqama_expiry_date: str | None = None


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


class ImportRowError(BaseModel):
    row: int
    reason: str


class ImportResult(BaseModel):
    imported: int
    errors: list[ImportRowError]
