"""توصية نهائية استرشادية تجمع كل مصادر التقييم المتاحة (سيرة ذاتية، مقابلة صوتية، اختبار ورقي)."""
from __future__ import annotations

from app.core.prompts import build_final_recommendation_prompt
from app.services.json_utils import JsonExtractionError, extract_json
from app.services.llm_client import LLMError, generate_text


class RecommendationError(Exception):
    pass


def generate_final_recommendation(
    job_title: str,
    domain_ar: str | None,
    cv_result: dict | None,
    voice_result: dict | None,
    written_result: dict | None,
) -> dict:
    if not any([cv_result, voice_result, written_result]):
        raise RecommendationError("لا تتوفر أي بيانات تقييم بعد لبناء توصية.")

    prompt = build_final_recommendation_prompt(
        job_title, domain_ar, cv_result, voice_result, written_result
    )

    try:
        raw = generate_text(prompt)
    except LLMError as e:
        raise RecommendationError(str(e))

    try:
        parsed = extract_json(raw)
    except JsonExtractionError as e:
        raise RecommendationError(str(e))

    return {
        "recommend": bool(parsed.get("recommend", False)),
        "reason_ar": parsed.get("reason_ar", ""),
        "strengths_ar": parsed.get("strengths_ar", []),
        "weaknesses_ar": parsed.get("weaknesses_ar", []),
    }
