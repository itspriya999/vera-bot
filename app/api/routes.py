from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, HTTPException

from app.config import settings
from app.core.decision_engine import DecisionEngine
from app.core.state import bot_state
from app.models.schemas import (
    ContextPushRequest,
    ContextPushResponse,
    HealthResponse,
    MetadataResponse,
    ReplyRequest,
    ReplyResponse,
    TickRequest,
    TickResponse,
)
from app.services.reply_service import ReplyService

router = APIRouter()
VALID_SCOPES = {"category", "merchant", "customer", "trigger"}


@router.get("/v1/healthz", response_model=HealthResponse)
async def healthz() -> HealthResponse:
    bot_state.increment("requests")
    return HealthResponse(
        status="ok",
        uptime_seconds=bot_state.uptime_seconds,
        contexts_loaded=bot_state.context_counts(),
    )


@router.get("/v1/metadata", response_model=MetadataResponse)
async def metadata() -> MetadataResponse:
    bot_state.increment("requests")
    return MetadataResponse(
        team_name=settings.team_name,
        team_members=settings.team_members_list,
        model=settings.model,
        approach=settings.approach,
        contact_email=settings.contact_email,
        version=settings.version,
        submitted_at=datetime.utcnow().isoformat() + "Z",
    )


@router.post("/v1/context", response_model=ContextPushResponse)
async def push_context(body: ContextPushRequest) -> ContextPushResponse:
    bot_state.increment("requests")
    if body.scope not in VALID_SCOPES:
        return ContextPushResponse(
            accepted=False,
            reason="invalid_scope",
            details=f"scope must be one of {sorted(VALID_SCOPES)}",
        )

    accepted, reason, current_version = bot_state.store_context(
        body.scope, body.context_id, body.version, body.payload
    )
    if not accepted:
        return ContextPushResponse(
            accepted=False,
            reason=reason,
            current_version=current_version,
        )

    return ContextPushResponse(
        accepted=True,
        ack_id=f"ack_{body.context_id}_v{body.version}",
        stored_at=datetime.utcnow().isoformat() + "Z",
    )


@router.post("/v1/tick", response_model=TickResponse)
async def tick(body: TickRequest) -> TickResponse:
    bot_state.increment("requests")
    engine = DecisionEngine(bot_state)
    actions = engine.decide_tick_actions(body.now, body.available_triggers)
    return TickResponse(actions=actions)


@router.post("/v1/reply", response_model=ReplyResponse)
async def reply(body: ReplyRequest) -> ReplyResponse:
    bot_state.increment("requests")
    service = ReplyService(bot_state)
    return service.handle(body)


@router.post("/v1/teardown")
async def teardown() -> dict:
    bot_state.teardown()
    return {"status": "cleared"}
