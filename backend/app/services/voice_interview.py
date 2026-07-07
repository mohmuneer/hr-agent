"""تقييم نص محادثة صوتية (مُحوّلة من صوت لنص في المتصفح) بين المرشح والوكيل."""
from __future__ import annotations

from app.core.prompts import build_voice_evaluation_prompt
from app.services.json_utils import JsonExtractionError, extract_json
from app.services.llm_client import LLMError, generate_text

DIMENSION_LABELS_AR = {
    "confidence": "الثقة والوضوح",
    "communication": "مهارات التواصل",
    "culture": "المعرفة العامة والمهنية",
    "understanding": "الفهم والاستيعاب",
    "reasoning": "المنطق والتحليل",
    "problem_solving": "حل المشكلات",
}


class VoiceEvaluationError(Exception):
    pass


def evaluate_voice_interview(
    transcript: list[dict],
    job_title: str,
    domain_ar: str | None = None,
) -> dict:
    if not transcript:
        raise VoiceEvaluationError("لا يوجد نص محادثة لتقييمه بعد.")

    prompt = build_voice_evaluation_prompt(transcript, job_title, domain_ar)

    try:
        raw = generate_text(prompt)
    except LLMError as e:
        raise VoiceEvaluationError(str(e))

    try:
        parsed = extract_json(raw)
    except JsonExtractionError as e:
        raise VoiceEvaluationError(str(e))

    raw_scores = {s.get("key"): s for s in parsed.get("scores", [])}
    scores = []
    for key, label in DIMENSION_LABELS_AR.items():
        s = raw_scores.get(key, {})
        scores.append(
            {
                "key": key,
                "label_ar": label,
                "score": float(s.get("score", 0)),
                "justification_ar": s.get("justification_ar", "لا يوجد تبرير."),
            }
        )

    return {
        "scores": scores,
        "overall_summary_ar": parsed.get("overall_summary_ar", ""),
        "strengths_ar": parsed.get("strengths_ar", []),
        "improvement_areas_ar": parsed.get("improvement_areas_ar", []),
    }
