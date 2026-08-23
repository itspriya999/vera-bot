from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


Scope = Literal["category", "merchant", "customer", "trigger"]
ReplyAction = Literal["send", "wait", "end"]
SendAs = Literal["vera", "merchant_on_behalf"]
CtaType = Literal["open_ended", "binary_yes_no", "binary_yes_stop", "none"]


class ContextPushRequest(BaseModel):
    scope: Scope
    context_id: str
    version: int
    payload: dict[str, Any]
    delivered_at: str


class ContextPushResponse(BaseModel):
    accepted: bool
    ack_id: Optional[str] = None
    stored_at: Optional[str] = None
    reason: Optional[str] = None
    current_version: Optional[int] = None
    details: Optional[str] = None


class TickRequest(BaseModel):
    now: str
    available_triggers: list[str] = Field(default_factory=list)


class TickAction(BaseModel):
    conversation_id: str
    merchant_id: str
    customer_id: Optional[str] = None
    send_as: SendAs
    trigger_id: str
    template_name: str = "vera_contextual_v1"
    template_params: list[str] = Field(default_factory=list)
    body: str
    cta: CtaType
    suppression_key: str
    rationale: str


class TickResponse(BaseModel):
    actions: list[TickAction] = Field(default_factory=list)


class ReplyRequest(BaseModel):
    conversation_id: str
    merchant_id: Optional[str] = None
    customer_id: Optional[str] = None
    from_role: str
    message: str
    received_at: str
    turn_number: int


class ReplyResponse(BaseModel):
    action: ReplyAction
    body: Optional[str] = None
    cta: Optional[CtaType] = None
    wait_seconds: Optional[int] = None
    rationale: str


class HealthResponse(BaseModel):
    status: str = "ok"
    uptime_seconds: int
    contexts_loaded: dict[str, int]


class MetadataResponse(BaseModel):
    team_name: str
    team_members: list[str]
    model: str
    approach: str
    contact_email: str
    version: str
    submitted_at: str


class ComposedMessage(BaseModel):
    body: str
    cta: CtaType
    send_as: SendAs
    suppression_key: str
    rationale: str
    template_name: str = "vera_contextual_v1"
    template_params: list[str] = Field(default_factory=list)
    conversation_id: str = ""
    merchant_id: str = ""
    customer_id: Optional[str] = None
    trigger_id: str = ""


class ConversationTurn(BaseModel):
    from_role: str
    message: str
    received_at: str
    turn_number: int


class ConversationState(BaseModel):
    conversation_id: str
    merchant_id: Optional[str] = None
    customer_id: Optional[str] = None
    trigger_id: Optional[str] = None
    send_as: SendAs = "vera"
    turns: list[ConversationTurn] = Field(default_factory=list)
    last_bot_body: Optional[str] = None
    last_suppression_key: Optional[str] = None
    ended: bool = False
    auto_reply_count: int = 0
    pending_action: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
