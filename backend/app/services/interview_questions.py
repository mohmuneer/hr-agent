"""توليد أسئلة مقابلة مخصصة (مفتوحة أو اختيار من متعدد) بناءً على السيرة الذاتية."""
from __future__ import annotations

from app.core.prompts import build_interview_questions_prompt, build_mcq_questions_prompt
from app.services.json_utils import JsonExtractionError, extract_json
from app.services.llm_client import LLMError, generate_text


class QuestionGenerationError(Exception):
    pass


def generate_interview_questions(
    cv_text: str,
    job_title: str,
    domain_ar: str | None = None,
    analysis_gaps: list[str] | None = None,
    question_type: str = "open",
) -> list[dict]:
    if question_type == "mcq":
        prompt = build_mcq_questions_prompt(cv_text, job_title, domain_ar, analysis_gaps)
    else:
        prompt = build_interview_questions_prompt(cv_text, job_title, domain_ar, analysis_gaps)

    try:
        raw = generate_text(prompt)
    except LLMError as e:
        raise QuestionGenerationError(str(e))

    try:
        parsed = extract_json(raw)
    except JsonExtractionError as e:
        raise QuestionGenerationError(str(e))

    raw_questions = parsed.get("questions", [])
    questions: list[dict] = []

    for q in raw_questions:
        if question_type == "mcq":
            if not isinstance(q, dict):
                continue
            text = str(q.get("text", "")).strip()
            options = [str(o).strip() for o in q.get("options", []) if str(o).strip()]
            correct_answer = str(q.get("correct_answer", "")).strip() or None
            if text and options:
                questions.append({"text": text, "options": options, "correct_answer": correct_answer})
        else:
            text = str(q).strip()
            if text:
                questions.append({"text": text, "options": None, "correct_answer": None})

    if not questions:
        raise QuestionGenerationError("لم يتمكن النموذج من توليد أسئلة.")
    return questions
