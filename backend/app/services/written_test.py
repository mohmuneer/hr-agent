"""تصحيح إجابات اختبار ورقي أدخلها فريق HR يدويًا (أسئلة MCQ ومفتوحة)."""
from __future__ import annotations

from app.core.prompts import build_written_test_prompt
from app.services.json_utils import JsonExtractionError, extract_json
from app.services.llm_client import LLMError, generate_text


class WrittenTestError(Exception):
    pass


def score_written_test(
    questions: list[dict],
    answers: list[dict],
    job_title: str,
    domain_ar: str | None = None,
) -> dict:
    questions_by_id = {q["id"]: q for q in questions}
    results = []
    open_items = []  # (result_index, question, answer_text)

    for ans in answers:
        q = questions_by_id.get(ans["question_id"])
        if q is None:
            continue

        answer_text = ans["answer_text"].strip()

        if q.get("type") == "mcq":
            correct = (q.get("correct_answer") or "").strip()
            is_correct = answer_text == correct
            results.append(
                {
                    "question_id": q["id"],
                    "question_text": q["text"],
                    "type": "mcq",
                    "candidate_answer": answer_text,
                    "correct_answer": q.get("correct_answer"),
                    "is_correct": is_correct,
                    "score": 100.0 if is_correct else 0.0,
                    "justification_ar": None,
                }
            )
        else:
            results.append(
                {
                    "question_id": q["id"],
                    "question_text": q["text"],
                    "type": "open",
                    "candidate_answer": answer_text,
                    "correct_answer": None,
                    "is_correct": None,
                    "score": None,
                    "justification_ar": None,
                }
            )
            open_items.append((len(results) - 1, q["text"], answer_text))

    if open_items:
        prompt = build_written_test_prompt(
            [{"question": q_text, "answer": a_text} for _, q_text, a_text in open_items],
            job_title,
            domain_ar,
        )
        try:
            raw = generate_text(prompt)
        except LLMError as e:
            raise WrittenTestError(str(e))
        try:
            parsed = extract_json(raw)
        except JsonExtractionError as e:
            raise WrittenTestError(str(e))

        scores_by_index = {r.get("index"): r for r in parsed.get("results", [])}
        for local_i, (result_idx, _, _) in enumerate(open_items):
            s = scores_by_index.get(local_i, {})
            results[result_idx]["score"] = float(s.get("score", 0))
            results[result_idx]["justification_ar"] = s.get("justification_ar", "لا يوجد تبرير.")

    scored = [r["score"] for r in results if r.get("score") is not None]
    overall_score = round(sum(scored) / len(scored), 1) if scored else 0.0

    return {"answers": results, "overall_score": overall_score}
