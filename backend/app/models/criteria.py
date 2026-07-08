"""نماذج المجالات ومعايير التقييم في قاعدة البيانات."""
from __future__ import annotations

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.sql import func

from app.core.database import Base


class Domain(Base):
    __tablename__ = "domains"

    id = Column(String(16), primary_key=True)
    key = Column(String(64), unique=True, nullable=False, index=True)
    domain_ar = Column(String(255), nullable=False)
    version = Column(String(32), default="0.1.0")
    note = Column(Text, nullable=True)
    weights_sum_to = Column(Integer, default=100, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class Criterion(Base):
    __tablename__ = "criteria"

    id = Column(String(16), primary_key=True)
    domain_id = Column(String(16), ForeignKey("domains.id", ondelete="CASCADE"), nullable=False, index=True)
    key = Column(String(64), nullable=False)
    label_ar = Column(String(255), nullable=False)
    weight = Column(Integer, nullable=False)
    description_ar = Column(Text, nullable=True)
    signals = Column(Text, nullable=True)
    sort_order = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
