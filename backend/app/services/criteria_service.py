"""خدمة إدارة المجالات ومعايير التقييم في قاعدة البيانات."""
from __future__ import annotations

import json
import uuid
from pathlib import Path

from sqlalchemy import desc

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.models.criteria import Criterion, Domain


def _criterion_to_dict(c: Criterion) -> dict:
    signals = None
    if c.signals:
        try:
            signals = json.loads(c.signals)
        except (json.JSONDecodeError, TypeError):
            signals = []
    return {
        "id": c.id,
        "domain_id": c.domain_id,
        "key": c.key,
        "label_ar": c.label_ar,
        "weight": c.weight,
        "description_ar": c.description_ar,
        "signals": signals or [],
        "sort_order": c.sort_order,
    }


def _domain_to_dict(d: Domain) -> dict:
    return {
        "id": d.id,
        "key": d.key,
        "domain_ar": d.domain_ar,
        "version": d.version or "0.1.0",
        "note": d.note,
        "weights_sum_to": d.weights_sum_to or 100,
        "created_at": d.created_at.isoformat() if d.created_at else None,
        "updated_at": d.updated_at.isoformat() if d.updated_at else None,
    }


def _get_criteria_for_domain(db, domain_id: str) -> list[dict]:
    rows = (
        db.query(Criterion)
        .filter(Criterion.domain_id == domain_id)
        .order_by(Criterion.sort_order)
        .all()
    )
    return [_criterion_to_dict(r) for r in rows]


def list_domains() -> list[dict]:
    db = SessionLocal()
    try:
        rows = db.query(Domain).order_by(Domain.key).all()
        result = []
        for d in rows:
            data = _domain_to_dict(d)
            data["criteria"] = _get_criteria_for_domain(db, d.id)
            result.append(data)
        return result
    finally:
        db.close()


def get_domain(domain_id: str) -> dict | None:
    db = SessionLocal()
    try:
        d = db.query(Domain).filter(Domain.id == domain_id).first()
        if d is None:
            return None
        data = _domain_to_dict(d)
        data["criteria"] = _get_criteria_for_domain(db, d.id)
        return data
    finally:
        db.close()


def get_domain_by_key(key: str) -> dict | None:
    db = SessionLocal()
    try:
        d = db.query(Domain).filter(Domain.key == key).first()
        if d is None:
            return None
        data = _domain_to_dict(d)
        data["criteria"] = _get_criteria_for_domain(db, d.id)
        return data
    finally:
        db.close()


def create_domain(data: dict) -> dict:
    domain_id = uuid.uuid4().hex[:12]
    db = SessionLocal()
    try:
        existing = db.query(Domain).filter(Domain.key == data["key"]).first()
        if existing:
            raise ValueError(f"المجال {data['key']} موجود مسبقاً")

        row = Domain(
            id=domain_id,
            key=data["key"],
            domain_ar=data["domain_ar"],
            version=data.get("version", "0.1.0"),
            note=data.get("note"),
            weights_sum_to=data.get("weights_sum_to", 100),
        )
        db.add(row)
        db.flush()

        criteria_data = data.get("criteria", [])
        for i, c in enumerate(criteria_data):
            signals_json = json.dumps(c.get("signals", []), ensure_ascii=False) if c.get("signals") else None
            c_row = Criterion(
                id=uuid.uuid4().hex[:12],
                domain_id=domain_id,
                key=c["key"],
                label_ar=c["label_ar"],
                weight=c["weight"],
                description_ar=c.get("description_ar"),
                signals=signals_json,
                sort_order=c.get("sort_order", i),
            )
            db.add(c_row)

        db.commit()
        db.refresh(row)
        return get_domain(domain_id)
    finally:
        db.close()


def update_domain(domain_id: str, updates: dict) -> dict | None:
    db = SessionLocal()
    try:
        row = db.query(Domain).filter(Domain.id == domain_id).first()
        if row is None:
            return None

        for key in ("domain_ar", "version", "note", "weights_sum_to"):
            if key in updates:
                setattr(row, key, updates[key])

        if "criteria" in updates and updates["criteria"] is not None:
            db.query(Criterion).filter(Criterion.domain_id == domain_id).delete()
            for i, c in enumerate(updates["criteria"]):
                signals_json = json.dumps(c.get("signals", []), ensure_ascii=False) if c.get("signals") else None
                c_row = Criterion(
                    id=uuid.uuid4().hex[:12],
                    domain_id=domain_id,
                    key=c["key"],
                    label_ar=c["label_ar"],
                    weight=c["weight"],
                    description_ar=c.get("description_ar"),
                    signals=signals_json,
                    sort_order=c.get("sort_order", i),
                )
                db.add(c_row)

        db.commit()
        db.refresh(row)
        return get_domain(domain_id)
    finally:
        db.close()


def delete_domain(domain_id: str) -> bool:
    db = SessionLocal()
    try:
        row = db.query(Domain).filter(Domain.id == domain_id).first()
        if row is None:
            return False
        db.query(Criterion).filter(Criterion.domain_id == domain_id).delete()
        db.delete(row)
        db.commit()
        return True
    finally:
        db.close()


def add_criterion(domain_id: str, data: dict) -> dict:
    db = SessionLocal()
    try:
        domain = db.query(Domain).filter(Domain.id == domain_id).first()
        if domain is None:
            raise ValueError("المجال غير موجود")

        signals_json = json.dumps(data.get("signals", []), ensure_ascii=False) if data.get("signals") else None
        c_row = Criterion(
            id=uuid.uuid4().hex[:12],
            domain_id=domain_id,
            key=data["key"],
            label_ar=data["label_ar"],
            weight=data["weight"],
            description_ar=data.get("description_ar"),
            signals=signals_json,
            sort_order=data.get("sort_order", 0),
        )
        db.add(c_row)
        db.commit()
        db.refresh(c_row)
        return _criterion_to_dict(c_row)
    finally:
        db.close()


def update_criterion(criterion_id: str, updates: dict) -> dict | None:
    db = SessionLocal()
    try:
        row = db.query(Criterion).filter(Criterion.id == criterion_id).first()
        if row is None:
            return None

        for key in ("key", "label_ar", "weight", "description_ar", "sort_order"):
            if key in updates:
                setattr(row, key, updates[key])

        if "signals" in updates:
            row.signals = json.dumps(updates["signals"], ensure_ascii=False) if updates["signals"] else None

        db.commit()
        db.refresh(row)
        return _criterion_to_dict(row)
    finally:
        db.close()


def delete_criterion(criterion_id: str) -> bool:
    db = SessionLocal()
    try:
        row = db.query(Criterion).filter(Criterion.id == criterion_id).first()
        if row is None:
            return False
        db.delete(row)
        db.commit()
        return True
    finally:
        db.close()


def seed_from_json() -> None:
    """ترحيل بيانات المعايير من ملفات JSON إلى قاعدة البيانات إذا كانت فارغة."""
    db = SessionLocal()
    try:
        if db.query(Domain).count() > 0:
            return

        settings = get_settings()
        json_dir: Path = settings.CRITERIA_DIR
        if not json_dir.exists():
            return

        for json_path in sorted(json_dir.glob("*.json")):
            try:
                with json_path.open(encoding="utf-8") as f:
                    data = json.load(f)
            except (json.JSONDecodeError, OSError):
                continue

            domain_id = uuid.uuid4().hex[:12]
            row = Domain(
                id=domain_id,
                key=data.get("domain", json_path.stem),
                domain_ar=data.get("domain_ar", json_path.stem),
                version=data.get("version", "0.1.0"),
                note=data.get("note"),
                weights_sum_to=data.get("weights_sum_to", 100),
            )
            db.add(row)
            db.flush()

            for i, c in enumerate(data.get("criteria", [])):
                signals_json = json.dumps(c.get("signals", []), ensure_ascii=False) if c.get("signals") else None
                c_row = Criterion(
                    id=uuid.uuid4().hex[:12],
                    domain_id=domain_id,
                    key=c["key"],
                    label_ar=c["label_ar"],
                    weight=c["weight"],
                    description_ar=c.get("description_ar"),
                    signals=signals_json,
                    sort_order=i,
                )
                db.add(c_row)

        db.commit()
    finally:
        db.close()
