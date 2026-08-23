from __future__ import annotations

from typing import Literal

from app.models.schemas import SendAs


def resolve_send_as(trigger_scope: str) -> SendAs:
    if trigger_scope == "customer":
        return "merchant_on_behalf"
    return "vera"
