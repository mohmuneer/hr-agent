"""محرك الوكيل الذكي (AI Agent Engine).
يحلل رسائل المستخدم باللغة الطبيعية، يكتشف النية (intent)،
يوجّه إلى الأداة المناسبة، ويولّد الردود.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from app.services.llm_client import generate_text, generate_text_stream, LLMError
from app.services.agent_tools import TOOL_DEFINITIONS, execute_tool
from app.services.json_utils import extract_json, JsonExtractionError
from app.schemas.agent import AgentChatResponse, ToolAction

from app.core.config import get_settings


CONVERSATIONS: dict[str, list[dict]] = {}

SYSTEM_PROMPT = """أنت مساعد ذكي مدمج بالكامل في نظام موارد البشرية (HR Agent). أنت مركز القيادة الذكي الذي يتحكم في النظام بالكامل.

قدراتك:
1. فهم اللغة الطبيعية بالعربية (جميع اللهجات: سعودية، خليجية، مصرية، يمنية، فصحى) والإنجليزية.
2. تنفيذ أوامر المستخدم داخل النظام (عرض، إضافة، تعديل، حذف، بحث).
3. التنقل بين الصفحات.
4. عرض الإحصائيات والتقارير.
5. تحليل الملفات المرفوعة.
6. إرسال الإشعارات.
7. حساب المستحقات المالية (GOSI، مكافأة نهاية الخدمة).
8. التحقق من الامتثال (الإقامات، السعودة).

الأدوات المتاحة:
{tools_block}

قواعد مهمة:
1. حلّل رسالة المستخدم بدقة واختر الأداة المناسبة.
2. إذا كان الطلب محادثة عادية (سؤال عام، تحيّة، شكر) - أجب مباشرة بدون أداة.
3. إذا طلب المستخدم معلومات (عرض، قائمة، إحصائيات، بحث) - نفّذ الأداة مباشرة بدون تأكيد.
4. إذا طلب المستخدم تنفيذ عملية خطيرة (إضافة، تعديل، حذف، إرسال) - اطلب تأكيداً.
5. إذا طلب المستخدم الانتقال إلى صفحة - استخدم أداة navigate_to_page.
6. إذا كان المستخدم في صفحة معينة وطلب شيئاً مرتبطاً بها - اعرض بيانات تلك الصفحة.
7. قدم اقتراحات مفيدة بعد كل رد.
8. كن مختصراً ومحدداً في ردودك. لا تكتب فقرات طويلة.
9. إذا كان الطلب غامضاً، اسأل المستخدم للتوضيح.
10. تذكر سياق المحادثة السابقة.

صيغة الرد JSON:
- رد نصي: {{"type": "text_response", "message_ar": "الرد", "suggestions": ["اقتراح1", "اقتراح2"]}}
- استدعاء أداة: {{"type": "tool_call", "action": {{"tool": "اسم_الأداة", "parameters": {{...}}, "explanation_ar": "شرح", "needs_confirmation": true/false}}, "suggestions": ["اقتراح1"]}}
- نتائج: {{"type": "tool_result", "message_ar": "الملخص", "result": {{...}}, "suggestions": ["اقتراح1"]}}
- انتقال: {{"type": "navigate", "navigate_to": "اسم_الصفحة", "message_ar": "جارٍ الانتقال..."}}
- خطأ: {{"type": "error", "message_ar": "وصف الخطأ"}}"""


def _format_tools_for_prompt() -> str:
    lines = []
    for t in TOOL_DEFINITIONS:
        params = t["parameters"]
        props = params.get("properties", {})
        req = params.get("required", [])
        param_lines = []
        for p_name, p_info in props.items():
            desc = p_info.get("description", "")
            required_mark = " (مطلوب)" if p_name in req else ""
            param_lines.append(f"    - {p_name}: {desc}{required_mark}")
        params_str = "\n".join(param_lines) if param_lines else "    لا توجد معاملات"
        lines.append(
            f"📌 {t['name']}: {t['description']}\n"
            f"   يحتاج تأكيد: {'نعم' if t.get('needs_confirmation') else 'لا'}\n"
            f"   المعاملات:\n{params_str}"
        )
    return "\n\n".join(lines)


def _get_or_create_conv(conv_id: str | None) -> tuple[str, list[dict]]:
    if conv_id and conv_id in CONVERSATIONS:
        return conv_id, CONVERSATIONS[conv_id]
    new_id = uuid.uuid4().hex[:12]
    CONVERSATIONS[new_id] = []
    return new_id, CONVERSATIONS[new_id]


def _call_llm(system: str, messages: list[dict]) -> str:
    conv_text = ""
    for m in messages:
        role = "المستخدم" if m["role"] == "user" else "المساعد"
        conv_text += f"{role}: {m['content']}\n\n"

    prompt = f"""{system}

تاريخ المحادثة:
{conv_text}

أعد ردك بصيغة JSON فقط كما هو موصوف أعلاه. لا تضف أي نص خارج JSON."""

    return generate_text(prompt, max_tokens=2000)


def process_message(message: str, conv_id: str | None = None, current_page: str | None = None, voice_mode: bool = False) -> AgentChatResponse:
    conv_id, history = _get_or_create_conv(conv_id)

    user_msg = message
    if current_page:
        user_msg += f"\n[الصفحة الحالية: {current_page}]"
    if voice_mode:
        user_msg += "\n[الطلب جاء من وضع الصوت]"

    history.append({"role": "user", "content": user_msg, "timestamp": datetime.now(timezone.utc).isoformat()})

    system = SYSTEM_PROMPT.format(tools_block=_format_tools_for_prompt())

    try:
        raw_response = _call_llm(system, history[-10:])
    except LLMError as e:
        history.append({"role": "assistant", "content": f"خطأ: {e}", "timestamp": datetime.now(timezone.utc).isoformat()})
        return AgentChatResponse(
            type="error",
            message_ar=str(e),
            conversation_id=conv_id,
        )

    try:
        parsed = extract_json(raw_response)
    except JsonExtractionError:
        text = raw_response.strip()
        history.append({"role": "assistant", "content": text, "timestamp": datetime.now(timezone.utc).isoformat()})
        return AgentChatResponse(
            type="text_response",
            message_ar=text,
            conversation_id=conv_id,
        )

    resp_type = parsed.get("type", "text_response")

    if resp_type == "text_response":
        text = parsed.get("message_ar", "")
        suggestions = parsed.get("suggestions")
        history.append({"role": "assistant", "content": text, "timestamp": datetime.now(timezone.utc).isoformat()})
        return AgentChatResponse(
            type="text_response",
            message_ar=text,
            conversation_id=conv_id,
            suggestions=suggestions,
        )

    if resp_type == "error":
        text = parsed.get("message_ar", "حدث خطأ")
        history.append({"role": "assistant", "content": text, "timestamp": datetime.now(timezone.utc).isoformat()})
        return AgentChatResponse(
            type="error",
            message_ar=text,
            conversation_id=conv_id,
        )

    if resp_type == "tool_call":
        action_data = parsed.get("action", {})
        tool_name = action_data.get("tool", "")
        params = action_data.get("parameters", {})
        explanation = action_data.get("explanation_ar", "")
        needs_confirmation = action_data.get("needs_confirmation", True)
        suggestions = parsed.get("suggestions")

        if not tool_name:
            return AgentChatResponse(
                type="error",
                message_ar="لم يتم تحديد أداة، حاول كتابة طلبك بشكل أوضح",
                conversation_id=conv_id,
            )

        # Save the pending action in conversation context
        history.append({
            "role": "assistant",
            "content": f"[طلب تنفيذ: {tool_name}] {explanation}",
            "action": {"tool": tool_name, "parameters": params},
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

        return AgentChatResponse(
            type="tool_call",
            message_ar=explanation,
            action=ToolAction(
                tool=tool_name,
                parameters=params,
                explanation_ar=explanation,
                needs_confirmation=needs_confirmation,
            ),
            conversation_id=conv_id,
            suggestions=suggestions,
        )

    if resp_type == "navigate":
        navigate_to = parsed.get("navigate_to", "")
        text = parsed.get("message_ar", f"جارٍ الانتقال إلى {navigate_to}...")
        suggestions = parsed.get("suggestions")
        history.append({"role": "assistant", "content": text, "timestamp": datetime.now(timezone.utc).isoformat()})
        return AgentChatResponse(
            type="navigate",
            message_ar=text,
            navigate_to=navigate_to,
            conversation_id=conv_id,
            suggestions=suggestions,
        )

    return AgentChatResponse(
        type="error",
        message_ar="استجابة غير مفهومة من الذكاء الاصطناعي",
        conversation_id=conv_id,
    )


def confirm_and_execute(conv_id: str, confirm: bool = True) -> AgentChatResponse:
    if conv_id not in CONVERSATIONS:
        return AgentChatResponse(
            type="error",
            message_ar="المحادثة غير موجودة أو انتهت صلاحيتها",
        )

    history = CONVERSATIONS[conv_id]

    pending_action = None
    for msg in reversed(history):
        if "action" in msg:
            pending_action = msg["action"]
            break

    if pending_action is None:
        return AgentChatResponse(
            type="error",
            message_ar="لا يوجد طلب تنفيذ معلق",
        )

    if not confirm:
        history.append({
            "role": "assistant",
            "content": "تم إلغاء الطلب",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        log_action("cancel", "agent_action",
                    details={"tool": pending_action["tool"], "params": pending_action["parameters"]},
                    username="admin")
        return AgentChatResponse(
            type="text_response",
            message_ar="تم إلغاء الطلب",
            conversation_id=conv_id,
        )

    result = execute_tool(pending_action["tool"], pending_action["parameters"])

    if result.get("success"):
        summary = result.pop("summary_ar", "تم التنفيذ بنجاح")
        result["success"] = True

        history.append({
            "role": "assistant",
            "content": f"[نتيجة: {pending_action['tool']}] {summary}",
            "result": result,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

        navigate_to = result.pop("navigate_to", None) or result.pop("view", None)

        return AgentChatResponse(
            type="tool_result",
            message_ar=summary,
            result=result,
            conversation_id=conv_id,
            navigate_to=navigate_to,
        )
    else:
        error_msg = result.get("error", "فشل التنفيذ")
        history.append({
            "role": "assistant",
            "content": f"[فشل: {pending_action['tool']}] {error_msg}",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        return AgentChatResponse(
            type="error",
            message_ar=error_msg,
            conversation_id=conv_id,
        )


def log_action(action: str, resource_type: str, **kwargs):
    from app.services.audit_logger import log_action as _log
    _log(action, resource_type, **kwargs)


def clear_conversation(conv_id: str) -> bool:
    if conv_id in CONVERSATIONS:
        del CONVERSATIONS[conv_id]
        return True
    return False


def process_message_stream(message: str, conv_id: str | None = None, current_page: str | None = None, voice_mode: bool = False):
    """Streaming version of process_message. Yields SSE-compatible event dicts."""
    conv_id, history = _get_or_create_conv(conv_id)

    user_msg = message
    if current_page:
        user_msg += f"\n[الصفحة الحالية: {current_page}]"
    if voice_mode:
        user_msg += "\n[الطلب جاء من وضع الصوت]"

    history.append({"role": "user", "content": user_msg, "timestamp": datetime.now(timezone.utc).isoformat()})

    system = SYSTEM_PROMPT.format(tools_block=_format_tools_for_prompt())

    # Yield conversation_id first
    yield {"event": "meta", "data": {"conversation_id": conv_id}}

    # Stream the LLM response
    full_response = ""
    try:
        for chunk in generate_text_stream(
            _build_prompt(system, history[-10:]),
            max_tokens=2000,
        ):
            full_response += chunk
            yield {"event": "chunk", "data": {"text": chunk}}
    except LLMError as e:
        error_msg = str(e)
        history.append({"role": "assistant", "content": f"خطأ: {error_msg}", "timestamp": datetime.now(timezone.utc).isoformat()})
        yield {"event": "error", "data": {"message_ar": error_msg}}
        return

    # Signal end of stream
    yield {"event": "stream_end", "data": {}}

    # Parse the complete response for tool calls, navigation, etc.
    try:
        parsed = extract_json(full_response)
    except JsonExtractionError:
        text = full_response.strip()
        history.append({"role": "assistant", "content": text, "timestamp": datetime.now(timezone.utc).isoformat()})
        yield {"event": "done", "data": {"type": "text_response", "message_ar": text, "conversation_id": conv_id}}
        return

    resp_type = parsed.get("type", "text_response")

    if resp_type == "text_response":
        text = parsed.get("message_ar", "")
        suggestions = parsed.get("suggestions")
        history.append({"role": "assistant", "content": text, "timestamp": datetime.now(timezone.utc).isoformat()})
        yield {"event": "done", "data": {"type": "text_response", "message_ar": text, "conversation_id": conv_id, "suggestions": suggestions}}

    elif resp_type == "error":
        text = parsed.get("message_ar", "حدث خطأ")
        history.append({"role": "assistant", "content": text, "timestamp": datetime.now(timezone.utc).isoformat()})
        yield {"event": "done", "data": {"type": "error", "message_ar": text, "conversation_id": conv_id}}

    elif resp_type == "tool_call":
        action_data = parsed.get("action", {})
        tool_name = action_data.get("tool", "")
        params = action_data.get("parameters", {})
        explanation = action_data.get("explanation_ar", "")
        needs_confirmation = action_data.get("needs_confirmation", True)
        suggestions = parsed.get("suggestions")

        if not tool_name:
            yield {"event": "done", "data": {"type": "error", "message_ar": "لم يتم تحديد أداة", "conversation_id": conv_id}}
            return

        history.append({
            "role": "assistant",
            "content": f"[طلب تنفيذ: {tool_name}] {explanation}",
            "action": {"tool": tool_name, "parameters": params},
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

        yield {"event": "done", "data": {
            "type": "tool_call",
            "message_ar": explanation,
            "action": {"tool": tool_name, "parameters": params, "explanation_ar": explanation, "needs_confirmation": needs_confirmation},
            "conversation_id": conv_id,
            "suggestions": suggestions,
        }}

    elif resp_type == "navigate":
        navigate_to = parsed.get("navigate_to", "")
        text = parsed.get("message_ar", f"جارٍ الانتقال إلى {navigate_to}...")
        suggestions = parsed.get("suggestions")
        history.append({"role": "assistant", "content": text, "timestamp": datetime.now(timezone.utc).isoformat()})
        yield {"event": "done", "data": {
            "type": "navigate",
            "message_ar": text,
            "navigate_to": navigate_to,
            "conversation_id": conv_id,
            "suggestions": suggestions,
        }}

    else:
        yield {"event": "done", "data": {"type": "error", "message_ar": "استجابة غير مفهومة", "conversation_id": conv_id}}


def _build_prompt(system: str, messages: list[dict]) -> str:
    """Build the full prompt string from system prompt and conversation history."""
    conv_text = ""
    for m in messages:
        role = "المستخدم" if m["role"] == "user" else "المساعد"
        conv_text += f"{role}: {m['content']}\n\n"

    return f"""{system}

تاريخ المحادثة:
{conv_text}

أعد ردك بصيغة JSON فقط كما هو موصوف أعلاه. لا تضف أي نص خارج JSON."""
