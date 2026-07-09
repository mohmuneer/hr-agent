"""محرك الوكيل الذكي (AI Agent Engine).
يحلل رسائل المستخدم باللغة الطبيعية، يكتشف النية (intent)،
يوجّه إلى الأداة المناسبة، ويولّد الردود.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from app.services.llm_client import generate_text, LLMError
from app.services.agent_tools import TOOL_DEFINITIONS, execute_tool
from app.schemas.agent import AgentChatResponse, ToolAction

from app.core.config import get_settings


CONVERSATIONS: dict[str, list[dict]] = {}

SYSTEM_PROMPT = """أنت مساعد AI Command Center لنظام الموارد البشرية.
مهمتك هي فهم طلبات مدير النظام باللغة العربية وتنفيذها عبر الأدوات المتاحة.

لديك الأدوات التالية:

{tools_block}

تعليمات مهمة:
1. حلّل رسالة المستخدم واختر الأداة المناسبة.
2. استخرج المعاملات (parameters) من الرسالة بدقة.
3. إذا كان الطلب محادثة عادية وليس أمراً تنفيذياً، أجب مباشرة.
4. إذا طلب المستخدم معلومات (عرض، قائمة، إحصائيات) - قدِّمها بلا تأكيد.
5. إذا طلب المستخدم تنفيذ عملية (إضافة، تعديل، حذف، إرسال) - اطلب تأكيداً.
6. أعد الرد بصيغة JSON فقط.

صيغة الرد المطلوبة:
- للرد النصي المباشر:
{{"type": "text_response", "message_ar": "نص الرد"}}

- لاستدعاء أداة:
{{"type": "tool_call", "action": {{"tool": "اسم_الأداة", "parameters": {{...}}, "explanation_ar": "شرح ما سينفذه", "needs_confirmation": true/false}}}}

- للخطأ:
{{"type": "error", "message_ar": "وصف الخطأ"}}

ملاحظات:
- لا تستدعِ أداة غير موجودة.
- تأكد من ملء المعاملات المطلوبة.
- للأوامر الخطيرة (إضافة/تعديل/حذف/إرسال) اجعل needs_confirmation = true.
- للأوامر الاستعلامية (عرض/بحث/إحصائيات) اجعل needs_confirmation = false.
"""


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


def process_message(message: str, conv_id: str | None = None) -> AgentChatResponse:
    conv_id, history = _get_or_create_conv(conv_id)

    history.append({"role": "user", "content": message, "timestamp": datetime.now(timezone.utc).isoformat()})

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
        parsed = json.loads(raw_response)
    except json.JSONDecodeError:
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
        history.append({"role": "assistant", "content": text, "timestamp": datetime.now(timezone.utc).isoformat()})
        return AgentChatResponse(
            type="text_response",
            message_ar=text,
            conversation_id=conv_id,
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

        return AgentChatResponse(
            type="tool_result",
            message_ar=summary,
            result=result,
            conversation_id=conv_id,
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
