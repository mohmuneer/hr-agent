"""استخراج JSON من ردود النموذج، حتى لو غلّفها بعلامات markdown."""
from __future__ import annotations

import json


class JsonExtractionError(Exception):
    pass


def extract_json(text: str) -> dict:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("```", 2)[1]
        if cleaned.startswith("json"):
            cleaned = cleaned[4:]
    cleaned = cleaned.strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as e:
        raise JsonExtractionError(f"تعذّر تحليل رد النموذج كـ JSON: {e}")
