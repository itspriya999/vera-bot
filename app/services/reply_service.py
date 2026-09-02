from __future__ import annotations

import re
from typing import Optional

from app.models.schemas import ConversationTurn
from app.rules.intent_rules import Intent, classify_intent
from app.core.state import BotState
from app.models.schemas import ReplyResponse


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip())


def _active_offer_titles(state: BotState, merchant_id: Optional[str]) -> list[str]:
    if not merchant_id:
        return []
    merchant = state.get_context("merchant", merchant_id)
    if not merchant:
        return []
    return [
        str(o["title"])
        for o in merchant.get("offers") or []
        if o.get("status") == "active" and o.get("title")
    ]


def _pricing_reply(state: BotState, merchant_id: Optional[str]) -> str:
    offers = _active_offer_titles(state, merchant_id)
    if offers:
        listed = ", ".join(offers[:3])
        return (
            f"From your active catalog: {listed}. "
            "Want me to list all active offers, or draft a customer message around one?"
        )
    return (
        "I can only quote prices already in your offer catalog — I won't invent rates. "
        "Want me to list what's active on your account, or help draft a service+price offer?"
    )


class ReplyService:
    def __init__(self, state: BotState) -> None:
        self.state = state

    def handle(self, req) -> ReplyResponse:
        turn = ConversationTurn(
            from_role=req.from_role,
            message=req.message,
            received_at=req.received_at,
            turn_number=req.turn_number,
        )
        conv = self.state.append_turn(req.conversation_id, turn)

        if self.state.is_conversation_ended(req.conversation_id):
            return ReplyResponse(
                action="end",
                rationale="Conversation already ended; no further messages.",
            )

        intent = classify_intent(req.message, conv.auto_reply_count)
        merchant_msg = _normalize(req.message)
        lower = merchant_msg.lower()

        if intent == Intent.AUTO_REPLY:
            conv.auto_reply_count += 1
            merchant_key = req.merchant_id or "unknown"
            global_count = self.state.record_auto_reply(merchant_key, req.message)
            self.state.save_conversation(conv)
            if conv.auto_reply_count >= 3 or global_count >= 3:
                self.state.end_conversation(req.conversation_id)
                return ReplyResponse(
                    action="end",
                    rationale="Detected repeated auto-reply pattern; exiting gracefully for owner follow-up.",
                )
            if conv.auto_reply_count == 1:
                return ReplyResponse(
                    action="send",
                    body=(
                        "Looks like an auto-reply — when the owner sees this, reply YES and I'll continue."
                    ),
                    cta="binary_yes_no",
                    rationale="Detected merchant auto-reply; one explicit prompt for the owner.",
                )
            return ReplyResponse(
                action="wait",
                wait_seconds=14400,
                rationale="Same auto-reply again; backing off 4 hours to wait for owner.",
            )

        if intent == Intent.REPETITION_COMPLAINT:
            if conv.last_suppression_key:
                self.state.mark_suppressed(conv.last_suppression_key)
            return ReplyResponse(
                action="send",
                body=(
                    "Fair point — I won't repeat that nudge. "
                    "I can switch to a fresh angle based on your latest account data, or pause outreach for now. "
                    "Which works better?"
                ),
                cta="open_ended",
                rationale="Merchant flagged repetition; acknowledged and offered new angle or pause.",
            )

        if intent in (Intent.STOP, Intent.NOT_INTERESTED, Intent.HOSTILE):
            self.state.end_conversation(req.conversation_id)
            if conv.last_suppression_key:
                self.state.mark_suppressed(conv.last_suppression_key)
            if intent == Intent.HOSTILE:
                return ReplyResponse(
                    action="end",
                    rationale="Merchant hostility detected; closing conversation politely.",
                )
            return ReplyResponse(
                action="end",
                rationale="Merchant opted out; closing conversation and suppressing further outreach.",
            )

        if intent == Intent.LATER:
            return ReplyResponse(
                action="wait",
                wait_seconds=1800,
                rationale="Merchant asked for time; backing off 30 minutes.",
            )

        if intent == Intent.ALREADY_DONE:
            return ReplyResponse(
                action="end",
                rationale="Merchant indicated task already completed; closing loop.",
            )

        if intent == Intent.OFF_TOPIC:
            redirect = "the draft we discussed"
            if conv.last_bot_body:
                lower_last = conv.last_bot_body.lower()
                if any(k in lower_last for k in ("jida", "fluoride", "research")):
                    redirect = "the JIDA abstract + patient-ed draft"
                elif any(k in lower_last for k in ("thali", "corporate")):
                    redirect = "the corporate thali WhatsApp"
                elif any(k in lower_last for k in ("webinar", "cde")):
                    redirect = "the webinar registration"
            return ReplyResponse(
                action="send",
                body=(
                    "That's outside what I can handle directly — GST, legal, and accounting need a specialist. "
                    f"Back to shop growth: want me to proceed with {redirect}, or pick a different priority?"
                ),
                cta="open_ended",
                rationale="Out-of-scope ask declined; redirecting to growth thread using conversation context.",
            )

        if intent in (Intent.YES, Intent.COMMITMENT):
            body = self._commitment_reply(conv, req.merchant_id)
            return ReplyResponse(
                action="send",
                body=body,
                cta="binary_yes_no",
                rationale="Honoring merchant acceptance; switching to action mode with concrete next step.",
            )

        if intent == Intent.NO:
            self.state.end_conversation(req.conversation_id)
            return ReplyResponse(
                action="end",
                rationale="Merchant declined; ending conversation politely.",
            )

        if self._is_pricing_question(lower):
            return ReplyResponse(
                action="send",
                body=_pricing_reply(self.state, req.merchant_id),
                cta="open_ended",
                rationale="Pricing question answered from merchant active offers only; no invented rates.",
            )

        if intent == Intent.NEED_MORE_INFO:
            if conv.last_bot_body:
                return ReplyResponse(
                    action="send",
                    body=(
                        "Happy to clarify — the last suggestion was based on your current account signals. "
                        "Want the numbers breakdown first, or should I draft the next step?"
                    ),
                    cta="open_ended",
                    rationale="Answered merchant question using account context without echoing their wording.",
                )
            return ReplyResponse(
                action="send",
                body=(
                    "Happy to clarify. "
                    "I can explain the reasoning from your account data, or jump straight to a draft. Which do you prefer?"
                ),
                cta="open_ended",
                rationale="Merchant asked a question; offering clarification vs action choice.",
            )

        if any(w in lower for w in ("customer", "patient", "client")):
            body = (
                "I can tailor outreach using your customer context when it's available. "
                "Should I draft a recall/reminder message, or focus on new-customer acquisition?"
            )
        elif conv.last_bot_body:
            body = (
                "Noted. I won't resend the earlier note — "
                "want a revised angle on the last suggestion, or something else entirely?"
            )
        else:
            body = (
                "Got it. Tell me what you'd like help with — "
                "campaign draft, profile fix, or customer message — and I'll take the next step."
            )

        return ReplyResponse(
            action="send",
            body=body,
            cta="open_ended",
            rationale="Acknowledged merchant message with a response tailored to intent and conversation state.",
        )

    @staticmethod
    def _is_pricing_question(lower: str) -> bool:
        if re.search(r"\b(price|pricing|cost|rate|charges|kitna|₹)\b", lower):
            return True
        return bool(re.search(r"\b(what|how much|current)\b.*\b(price|cost|rate)\b", lower))

    def _commitment_reply(self, conv, merchant_id: Optional[str]) -> str:
        last_lower = (conv.last_bot_body or "").lower()
        merchant = self.state.get_context("merchant", merchant_id) if merchant_id else None
        cohort = (merchant or {}).get("customer_aggregate", {}).get("high_risk_adult_count")

        if any(k in last_lower for k in ("jida", "fluoride", "abstract", "research")):
            extra = f" for your {cohort} high-risk adult patients" if cohort else ""
            return (
                "Sending the abstract now. I'll draft the patient-ed WhatsApp next"
                f"{extra} — reply YES when you want it sent."
            )
        if any(k in last_lower for k in ("cde", "webinar", "ida")):
            return (
                "Registering your webinar spot and sending a calendar hold. "
                "Reply YES to confirm the seat."
            )
        if any(k in last_lower for k in ("thali", "corporate", "tier")):
            return (
                "Drafting the corporate thali WhatsApp from the tiers we outlined. "
                "Reply YES to review before send."
            )
        if any(k in last_lower for k in ("kids yoga", "summer camp", "parent")):
            return (
                "Drafting the parent announcement + enrollment reply template now. "
                "Reply YES when ready to broadcast."
            )
        if any(k in last_lower for k in ("batch", "atorvastatin", "recall", "replacement")):
            return (
                "Drafting the replacement-pickup WhatsApp using the batch details from your alert. "
                "Reply YES to review before send."
            )
        return (
            "Great — moving ahead now. "
            "I'll prepare the draft and share it here for a quick yes/no before anything goes live."
        )
