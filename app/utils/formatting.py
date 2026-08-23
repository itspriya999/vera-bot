from __future__ import annotations

import re
from typing import Any, Optional


def pct(value: float, decimals: int = 0) -> str:
    return f"{value * 100:.{decimals}f}%"


def pct_change(value: float) -> str:
    sign = "+" if value >= 0 else ""
    return f"{sign}{value * 100:.0f}%"


def owner_name(merchant: dict[str, Any]) -> str:
    identity = merchant.get("identity") or {}
    if identity.get("owner_first_name"):
        return str(identity["owner_first_name"])
    name = str(identity.get("name", "there"))
    return name.split()[0].replace("Dr.", "Dr. ").strip()


def merchant_display(merchant: dict[str, Any]) -> str:
    identity = merchant.get("identity") or {}
    first = identity.get("owner_first_name")
    category = merchant.get("category_slug", "")
    if first:
        if category == "dentists":
            return f"Dr. {first}"
        return str(first)
    return str(identity.get("name", "there"))


def active_offer(merchant: dict[str, Any]) -> Optional[str]:
    for offer in merchant.get("offers") or []:
        if offer.get("status") == "active" and offer.get("title"):
            return str(offer["title"])
    return None


def peer_ctr(category: dict[str, Any]) -> Optional[float]:
    stats = category.get("peer_stats") or {}
    ctr = stats.get("avg_ctr")
    return float(ctr) if ctr is not None else None


def digest_item(category: dict[str, Any], item_id: Optional[str]) -> Optional[dict[str, Any]]:
    items = category.get("digest") or []
    if item_id:
        for item in items:
            if item.get("id") == item_id:
                return item
    return items[0] if items else None


def uses_hindi_mix(merchant: dict[str, Any], customer: Optional[dict[str, Any]] = None) -> bool:
    if customer:
        pref = str((customer.get("identity") or {}).get("language_pref", "")).lower()
        if "hi" in pref or "hindi" in pref:
            return True
    langs = (merchant.get("identity") or {}).get("languages") or []
    return "hi" in langs


def format_ctr(ctr: float) -> str:
    return f"{ctr * 100:.1f}%"


def truncate(text: str, max_len: int = 900) -> str:
    text = re.sub(r"\s+", " ", text.strip())
    if len(text) <= max_len:
        return text
    return text[: max_len - 3].rstrip() + "..."
