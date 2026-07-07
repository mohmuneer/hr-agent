"""محرك تحليل السير الذاتية.

يجمع المعايير + السيرة، يرسلها للنموذج، يحسب الدرجة الموزونة،
ويعيد نتيجة منظمة. القرار النهائي يبقى للإنسان.
"""
from __future__ import annotations

from app.core.prompts import build_cv_analysis_prompt
from app.schemas.analysis import CriterionScore, CVAnalysisResult
from app.services.criteria_loader import load_criteria
from app.services.json_utils import JsonExtractionError, extract_json
from app.services.llm_client import LLMError, generate_text


class AnalysisError(Exception):
    pass


def analyze_cv(cv_text: str, job_title: str, domain: str | None = None) -> CVAnalysisResult:
    criteria = load_criteria(domain)
    prompt = build_cv_analysis_prompt(cv_text, job_title, criteria)

    try:
        raw = generate_text(prompt)
    except LLMError as e:
        raise AnalysisError(str(e))

    try:
        parsed = extract_json(raw)
    except JsonExtractionError as e:
        raise AnalysisError(str(e))

    # ربط درجات النموذج بأوزان المعايير وحساب الدرجة الموزونة
    weight_map = {c["key"]: c for c in criteria["criteria"]}
    model_scores = {s["key"]: s for s in parsed.get("scores", [])}

    scores: list[CriterionScore] = []
    weighted_total = 0.0
    for key, crit in weight_map.items():
        ms = model_scores.get(key, {})
        raw_score = float(ms.get("score", 0))
        weighted_total += raw_score * crit["weight"] / 100
        scores.append(
            CriterionScore(
                key=key,
                label_ar=crit["label_ar"],
                weight=crit["weight"],
                score=raw_score,
                justification_ar=ms.get("justification_ar", "لا يوجد تبرير."),
            )
        )

    return CVAnalysisResult(
        job_title=job_title,
        domain=criteria["domain"],
        overall_score=round(weighted_total, 1),
        recommendation_ar=parsed.get("recommendation_ar", ""),
        scores=scores,
        strengths_ar=parsed.get("strengths_ar", []),
        gaps_ar=parsed.get("gaps_ar", []),
    )
