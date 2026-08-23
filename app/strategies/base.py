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


def first_active_offer_title(merchant: dict[str, Any], category: dict[str, Any]) -> Optional[str]:
    for offer in merchant.get("offers") or []:
        if offer.get("status") == "active" and offer.get("title"):
            return str(offer["title"])
    catalog = category.get("offer_catalog") or []
    if catalog:
        return str(catalog[0].get("title", ""))
    return None
