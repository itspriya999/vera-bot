from __future__ import annotations

from typing import Any, Optional

from app.core.send_identity import resolve_send_as
from app.core.state import BotState
from app.models.schemas import ComposedMessage, TickAction
from app.strategies.handlers import compose_message


def make_conversation_id(merchant_id: str, trigger_id: str, customer_id: Optional[str]) -> str:
    base = f"conv_{merchant_id}_{trigger_id}"
    if customer_id:
        return f"{base}_{customer_id}"
    return base


def compose(
    state: BotState,
    trigger_id: str,
    now_iso: str,
) -> Optional[ComposedMessage]:
    trigger = state.get_context("trigger", trigger_id)
    if not trigger:
        return None

    merchant_id = trigger.get("merchant_id")
    if not merchant_id:
        return None

    merchant = state.get_context("merchant", merchant_id)
    if not merchant:
        return None

    category_slug = merchant.get("category_slug", "")
    category = state.get_context("category", category_slug) or {}

    customer_id = trigger.get("customer_id")
    customer = state.get_context("customer", customer_id) if customer_id else None

    if customer_id and not customer:
        return None

    suppression_key = str(trigger.get("suppression_key", trigger_id))
    if state.is_suppressed(suppression_key):
        return None

    result = compose_message(category, merchant, trigger, customer, trigger_id)
    conversation_id = make_conversation_id(merchant_id, trigger_id, customer_id)

    if state.is_conversation_ended(conversation_id):
        return None

    if state.body_already_sent(conversation_id, result.body):
        state.increment("suppressed_messages")
        return None

    send_as = resolve_send_as(str(trigger.get("scope", "merchant")))

    return ComposedMessage(
        body=result.body,
        cta=result.cta,
        send_as=send_as,
        suppression_key=result.suppression_key,
        rationale=result.rationale,
        template_name=result.template_name,
        template_params=result.template_params,
        conversation_id=conversation_id,
        merchant_id=merchant_id,
        customer_id=customer_id,
        trigger_id=trigger_id,
    )


def to_tick_action(msg: ComposedMessage) -> TickAction:
    return TickAction(
        conversation_id=msg.conversation_id,
        merchant_id=msg.merchant_id,
        customer_id=msg.customer_id,
        send_as=msg.send_as,
        trigger_id=msg.trigger_id,
        template_name=msg.template_name,
        template_params=msg.template_params,
        body=msg.body,
        cta=msg.cta,
        suppression_key=msg.suppression_key,
        rationale=msg.rationale,
    )
