"""استخراج JSON من ردود النموذج، حتى لو غلّفها بعلامات markdown أو كانت ناقصة."""
from __future__ import annotations

import json
import re


class JsonExtractionError(Exception):
    pass


def _find_outer_json(text: str) -> str | None:
    """يبحث عن أول كائن JSON متوازن الأقواس ويعيد نصّه."""
    for start in range(len(text)):
        if text[start] == "{":
            depth = 0
            in_str = False
            escape = False
            for end in range(start, len(text)):
                c = text[end]
                if escape:
                    escape = False
                    continue
                if c == "\\":
                    escape = True
                elif c == '"':
                    in_str = not in_str
                elif not in_str:
                    if c == "{":
                        depth += 1
                    elif c == "}":
                        depth -= 1
                        if depth == 0:
                            return text[start : end + 1]
            return text[start:]
    return None


def _fix_partial_json(s: str) -> str:
    """محاولة إصلاح JSON ناقص: إغلاق السلاسل الناقصة أولاً ثم الأقواس."""
    s = re.sub(r",\s*([}\]])", r"\1", s)
    s = re.sub(r",\s*$", "", s)

    # 1. أغلق أي string مفتوح أولاً (قبل الأقواس)
    if _has_open_string(s):
        s += '"'

    # 2. أغلق الأقواس غير المغلقة بالترتيب العكسي للفتح
    order = _open_brackets(s)
    closer = {"{": "}", "[": "]", "(": ")"}
    while order:
        s += closer[order.pop()]

    return s


def _has_open_string(s: str) -> bool:
    in_str = False
    escape = False
    for c in s:
        if escape:
            escape = False
            continue
        if c == "\\":
            escape = True
        elif c == '"':
            in_str = not in_str
    return in_str


def _open_brackets(s: str) -> list[str]:
    pair = {"{": "}", "[": "]", "(": ")"}
    rev = {v: k for k, v in pair.items()}
    order: list[str] = []
    in_str = False
    escape = False
    for c in s:
        if escape:
            escape = False
            continue
        if c == "\\":
            escape = True
        elif c == '"':
            in_str = not in_str
        elif not in_str:
            if c in pair:
                order.append(c)
            elif c in rev:
                if order and order[-1] == rev[c]:
                    order.pop()
    return order


def extract_json(text: str) -> dict:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("```", 2)[1]
        if cleaned.startswith("json"):
            cleaned = cleaned[4:]
    cleaned = cleaned.strip()

    # 1. محاولة مباشرة
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # 2. إيجاد أول كائن JSON متوازن وإصلاحه
    outer = _find_outer_json(cleaned)
    if outer:
        # 2أ. المحاولة كاملة
        try:
            return json.loads(outer)
        except json.JSONDecodeError:
            pass

        # 2ب. إصلاح المشاكل الشائعة (أقواس/سلاسل ناقصة)
        fixed = _fix_partial_json(outer)
        try:
            return json.loads(fixed)
        except json.JSONDecodeError:
            pass

        # 2ج. progressive truncation — نجرب باختصار النص من النهاية
        for cut in range(len(outer) - 1, len(outer) // 2, -1):
            try:
                return json.loads(outer[:cut])
            except json.JSONDecodeError:
                continue
        for cut in range(len(fixed) - 1, len(fixed) // 2, -1):
            try:
                return json.loads(fixed[:cut])
            except json.JSONDecodeError:
                continue

    # 3. raw_decode — يتجاهل المحتوى الزائد بعد JSON (مثل نص إضافي بعد JSON صالح)
    decoder = json.JSONDecoder()
    for i, ch in enumerate(cleaned):
        if ch in ("{", "["):
            try:
                obj, _ = decoder.raw_decode(cleaned[i:])
                return obj
            except json.JSONDecodeError:
                continue

    raise JsonExtractionError("تعذّر تحليل رد النموذج كـ JSON")
