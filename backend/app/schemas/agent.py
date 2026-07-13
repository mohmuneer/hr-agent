"""نماذج الذكاء الاصطناعي للمحادثة."""
from __future__ import annotations

from pydantic import BaseModel


class ChatMessage(BaseModel):
    role: str  # "user" | "assistant" | "system"
    content: str


class AgentChatRequest(BaseModel):
    message: str
    conversation_id: str | None = None
    current_page: str | None = None
    voice_mode: bool = False


class ToolAction(BaseModel):
    tool: str
    parameters: dict = {}
    explanation_ar: str = ""
    needs_confirmation: bool = True


class AgentChatResponse(BaseModel):
    type: str  # "text_response" | "tool_call" | "tool_result" | "error" | "navigate"
    message_ar: str = ""
    action: ToolAction | None = None
    result: dict | None = None
    conversation_id: str | None = None
    navigate_to: str | None = None
    suggestions: list[str] | None = None


class AgentConfirmRequest(BaseModel):
    conversation_id: str
    confirm: bool = True


class FileAnalysisRequest(BaseModel):
    file_text: str
    file_name: str
    analysis_type: str = "general"
