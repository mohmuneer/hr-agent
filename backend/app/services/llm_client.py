"""طبقة موحّدة لاستدعاء نموذج الذكاء الاصطناعي (Anthropic أو Gemini).

تفصل تفاصيل كل مزوّد عن الخدمات التي تستخدم النموذج (تحليل السير الذاتية،
توليد أسئلة المقابلة، ...) بحيث لا تتكرر منطق التبديل بين المزوّدين.
"""
from __future__ import annotations

import anthropic
from anthropic import Anthropic
from google import genai
from google.genai import errors as genai_errors

from app.core.config import get_settings


class LLMError(Exception):
    pass


def _call_anthropic(settings, prompt: str, max_tokens: int) -> str:
    if not settings.ANTHROPIC_API_KEY:
        raise LLMError("مفتاح ANTHROPIC_API_KEY غير مضبوط.")

    client = Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    try:
        response = client.messages.create(
            model=settings.MODEL,
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
    except anthropic.APIStatusError as e:
        message = e.body.get("error", {}).get("message", str(e)) if isinstance(e.body, dict) else str(e)
        raise LLMError(f"تعذّر الاتصال بنموذج الذكاء الاصطناعي (Anthropic): {message}")
    except anthropic.APIError as e:
        raise LLMError(f"تعذّر الاتصال بنموذج الذكاء الاصطناعي (Anthropic): {e}")

    return "".join(b.text for b in response.content if b.type == "text")


def _call_gemini(settings, prompt: str, max_tokens: int) -> str:
    if not settings.GEMINI_API_KEY:
        raise LLMError("مفتاح GEMINI_API_KEY غير مضبوط.")

    client = genai.Client(api_key=settings.GEMINI_API_KEY)
    try:
        response = client.models.generate_content(
            model=settings.GEMINI_MODEL,
            contents=prompt,
        )
    except genai_errors.APIError as e:
        raise LLMError(f"تعذّر الاتصال بنموذج الذكاء الاصطناعي (Gemini): {e.message}")

    if not response.text:
        raise LLMError("لم يرجع النموذج أي نص (قد يكون بسبب فلاتر السلامة).")
    return response.text


def generate_text(prompt: str, max_tokens: int = 2000) -> str:
    settings = get_settings()
    if not settings.is_configured:
        raise LLMError(
            f"لم يتم ضبط مفتاح API لمزوّد النموذج الحالي ({settings.PROVIDER}). راجع ملف .env"
        )

    if settings.PROVIDER == "gemini":
        return _call_gemini(settings, prompt, max_tokens)
    return _call_anthropic(settings, prompt, max_tokens)
