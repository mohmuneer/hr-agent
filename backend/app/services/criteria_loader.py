"""تحميل معايير التقييم — يقرأ من قاعدة البيانات أولاً، مع احتفاظ بدعم ملفات JSON.

هذه الطبقة تفصل المعايير عن الكود بحيث يقدر خبير HR يعدّل الملفات
مباشرة، أو نربطها لاحقاً بمخرجات dataset — بلا لمس الكود.
"""
from __future__ import annotations

import json
from pathlib import Path

from app.core.config import get_settings
from app.services.criteria_service import get_domain_by_key, list_domains


class CriteriaError(Exception):
    """خطأ في تحميل أو التحقق من المعايير."""


def load_criteria(domain: str | None = None) -> dict:
    settings = get_settings()
    domain = domain or settings.ACTIVE_DOMAIN

    # حاول القراءة من قاعدة البيانات أولاً
    db_data = get_domain_by_key(domain)
    if db_data:
        return _db_to_json_format(db_data)

    # fallback إلى ملف JSON
    path: Path = settings.CRITERIA_DIR / f"{domain}.json"
    if not path.exists():
        raise CriteriaError(f"لا توجد معايير للمجال: {domain}")

    with path.open(encoding="utf-8") as f:
        data = json.load(f)

    _validate(data, domain)
    return data


def _db_to_json_format(db_data: dict) -> dict:
    return {
        "domain": db_data["key"],
        "domain_ar": db_data["domain_ar"],
        "version": db_data.get("version", "0.1.0"),
        "note": db_data.get("note"),
        "weights_sum_to": db_data.get("weights_sum_to", 100),
        "criteria": [
            {
                "key": c["key"],
                "label_ar": c["label_ar"],
                "weight": c["weight"],
                "description_ar": c.get("description_ar"),
                "signals": c.get("signals", []),
            }
            for c in db_data.get("criteria", [])
        ],
    }


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
    # حاول من قاعدة البيانات أولاً
    try:
        domains = list_domains()
        if domains:
            return sorted(d["key"] for d in domains)
    except Exception:
        pass

    # fallback إلى ملفات JSON
    settings = get_settings()
    return sorted(p.stem for p in settings.CRITERIA_DIR.glob("*.json"))
