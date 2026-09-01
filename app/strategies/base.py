from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from app.models.schemas import CtaType, SendAs


@dataclass
class ComposeResult:
    body: str
    cta: CtaType
    send_as: SendAs
    suppression_key: str
    rationale: str
    template_params: list[str] = field(default_factory=list)
    template_name: str = "vera_contextual_v1"


def customer_name(customer: dict[str, Any]) -> str:
    return str((customer.get("identity") or {}).get("name", "there"))


def trigger_payload(trigger: dict[str, Any]) -> dict[str, Any]:
    return trigger.get("payload") or {}


def merchant_active_offer(
    merchant: dict[str, Any],
    prefer_keywords: Optional[list[str]] = None,
) -> Optional[str]:
    """Return an active merchant offer only — never fall back to category catalog."""
    active = [
        str(o["title"])
        for o in merchant.get("offers") or []
        if o.get("status") == "active" and o.get("title")
    ]
    if not active:
        return None
    if prefer_keywords:
        lower_active = [(t, t.lower()) for t in active]
        for keyword in prefer_keywords:
            kw = keyword.lower()
            for title, lower in lower_active:
                if kw in lower:
                    return title
    return active[0]


def first_active_offer_title(
    merchant: dict[str, Any],
    category: Optional[dict[str, Any]] = None,
    prefer_keywords: Optional[list[str]] = None,
) -> Optional[str]:
    del category  # kept for call-site compatibility; category catalog must not be used
    return merchant_active_offer(merchant, prefer_keywords)
