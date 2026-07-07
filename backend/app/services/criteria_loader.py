"""تحميل معايير التقييم من ملفات JSON والتحقق من صحتها.

هذه الطبقة تفصل المعايير عن الكود بحيث يقدر خبير HR يعدّل الملفات
مباشرة، أو نربطها لاحقاً بمخرجات dataset — بلا لمس الكود.
"""
from __future__ import annotations

import json
from pathlib import Path

from app.core.config import get_settings


class CriteriaError(Exception):
    """خطأ في تحميل أو التحقق من المعايير."""


def load_criteria(domain: str | None = None) -> dict:
    settings = get_settings()
    domain = domain or settings.ACTIVE_DOMAIN
    path: Path = settings.CRITERIA_DIR / f"{domain}.json"

    if not path.exists():
        raise CriteriaError(f"لا توجد ملف معايير للمجال: {domain} ({path})")

    with path.open(encoding="utf-8") as f:
        data = json.load(f)

    _validate(data, domain)
    return data


def _validate(data: dict, domain: str) -> None:
    if "criteria" not in data or not isinstance(data["criteria"], list):
        raise CriteriaError(f"ملف {domain}: مفقود حقل 'criteria' أو نوعه خاطئ")

    total = sum(c.get("weight", 0) for c in data["criteria"])
    expected = data.get("weights_sum_to", 100)
    if total != expected:
        raise CriteriaError(
            f"ملف {domain}: مجموع الأوزان {total} لا يساوي {expected}. "
            "راجع أوزان المعايير."
        )

    for c in data["criteria"]:
        for field in ("key", "label_ar", "weight"):
            if field not in c:
                raise CriteriaError(
                    f"ملف {domain}: معيار ينقصه الحقل '{field}'"
                )


def list_available_domains() -> list[str]:
    settings = get_settings()
    return sorted(p.stem for p in settings.CRITERIA_DIR.glob("*.json"))
