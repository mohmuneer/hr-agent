"""مخططات إدارة المجالات ومعايير التقييم."""
from __future__ import annotations

from pydantic import BaseModel, Field


class CriterionCreate(BaseModel):
    key: str = Field(..., min_length=1, description="المعرف المميز للمعيار")
    label_ar: str = Field(..., min_length=1, description="اسم المعيار بالعربية")
    weight: int = Field(..., ge=0, le=100, description="وزن المعيار")
    description_ar: str | None = None
    signals: list[str] | None = None
    sort_order: int = 0


class CriterionUpdate(BaseModel):
    key: str | None = None
    label_ar: str | None = None
    weight: int | None = Field(None, ge=0, le=100)
    description_ar: str | None = None
    signals: list[str] | None = None
    sort_order: int | None = None


class CriterionResponse(BaseModel):
    id: str
    domain_id: str
    key: str
    label_ar: str
    weight: int
    description_ar: str | None = None
    signals: list[str] | None = None
    sort_order: int = 0


class DomainCreate(BaseModel):
    key: str = Field(..., min_length=1, description="المعرف المميز للمجال (مثل accounting)")
    domain_ar: str = Field(..., min_length=1, description="اسم المجال بالعربية")
    version: str = "0.1.0"
    note: str | None = None
    weights_sum_to: int = 100
    criteria: list[CriterionCreate] = []


class DomainUpdate(BaseModel):
    domain_ar: str | None = None
    version: str | None = None
    note: str | None = None
    weights_sum_to: int | None = None
    criteria: list[CriterionCreate] | None = None


class DomainResponse(BaseModel):
    id: str
    key: str
    domain_ar: str
    version: str
    note: str | None = None
    weights_sum_to: int = 100
    criteria: list[CriterionResponse] = []
