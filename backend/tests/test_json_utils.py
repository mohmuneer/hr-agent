"""اختبارات لاستخراج JSON من ردود النموذج، بما فيها حالة الاقتباسات الداخلية الشائعة."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.json_utils import extract_json, JsonExtractionError


def test_valid_json_parses_directly():
    result = extract_json('{"type": "text_response", "message_ar": "مرحبًا"}')
    assert result == {"type": "text_response", "message_ar": "مرحبًا"}


def test_json_wrapped_in_markdown_fences():
    raw = '```json\n{"type": "text_response", "message_ar": "أهلًا"}\n```'
    result = extract_json(raw)
    assert result["message_ar"] == "أهلًا"


def test_stray_quotes_around_single_word():
    """الحالة المُبلَّغ عنها: النموذج يضع اقتباسات حول كلمة داخل الجملة."""
    raw = (
        '{"type": "text_response", "message_ar": "عذرًا، لا أستطيع تحديد أو عرض '
        '"أفضل" المتقدمين للوظائف."}'
    )
    result = extract_json(raw)
    assert result["type"] == "text_response"
    assert '"أفضل"' in result["message_ar"]
    assert "المتقدمين للوظائف" in result["message_ar"]


def test_stray_quotes_with_prose_before_json():
    raw = (
        'إليك الرد:\n'
        '{"type": "text_response", "message_ar": "هذا يسمى "الأفضل" فعلًا"}'
    )
    result = extract_json(raw)
    assert result["type"] == "text_response"


def test_multiple_stray_quoted_words():
    raw = (
        '{"type": "text_response", "message_ar": '
        '"كلمة "أولى" ثم كلمة "ثانية" في نفس الجملة"}'
    )
    result = extract_json(raw)
    assert "أولى" in result["message_ar"]
    assert "ثانية" in result["message_ar"]


def test_tool_call_with_nested_action_object():
    raw = '''{
        "type": "tool_call",
        "action": {
            "tool": "add_employee",
            "parameters": {"full_name": "خالد \\"الملقب بأبو سالم\\""},
            "explanation_ar": "إضافة موظف",
            "needs_confirmation": true
        }
    }'''
    result = extract_json(raw)
    assert result["type"] == "tool_call"
    assert result["action"]["tool"] == "add_employee"


def test_truncated_json_missing_closing_brace():
    raw = '{"type": "text_response", "message_ar": "رد غير مكتمل'
    result = extract_json(raw)
    assert result["type"] == "text_response"


def test_completely_invalid_text_raises():
    try:
        extract_json("هذا نص عادي بدون أي JSON إطلاقًا")
        assert False, "should have raised JsonExtractionError"
    except JsonExtractionError:
        pass


def test_trailing_comma_is_handled():
    raw = '{"type": "text_response", "message_ar": "تجربة",}'
    result = extract_json(raw)
    assert result["message_ar"] == "تجربة"
