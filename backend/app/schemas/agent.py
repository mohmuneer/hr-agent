"""نماذج الذكاء الاصطناعي للمحادثة."""
from __future__ import annotations

from pydantic import BaseModel


class ChatMessage(BaseModel):
    role: str  # "user" | "assistant" | "system"
    content: str


class AgentChatRequest(BaseModel):
    message: str
    conversation_id: str | None = None


class ToolAction(BaseModel):
    tool: str
    parameters: dict = {}
    explanation_ar: str = ""
    needs_confirmation: bool = True


class AgentChatResponse(BaseModel):
    type: str  # "text_response" | "tool_call" | "tool_result" | "error"
    message_ar: str = ""
    action: ToolAction | None = None
    result: dict | None = None
    conversation_id: str | None = None


class AgentConfirmRequest(BaseModel):
    conversation_id: str
    confirm: bool = True
