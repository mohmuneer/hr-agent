"""مخططات إدارة الوظائف المتاحة."""
from __future__ import annotations

from pydantic import BaseModel, Field


class JobCreateRequest(BaseModel):
    title: str = Field(..., min_length=2, description="المسمى الوظيفي")
    domain: str | None = Field(None, description="المجال المرتبط بمعايير التقييم")
    description: str | None = None
    location: str | None = None


class JobUpdateRequest(BaseModel):
    title: str | None = None
    domain: str | None = None
    description: str | None = None
    location: str | None = None
    status: str | None = Field(None, description="open أو closed")


class Job(BaseModel):
    id: str
    title: str
    domain: str | None = None
    description: str | None = None
    location: str | None = None
    status: str = "open"
    created_at: str
