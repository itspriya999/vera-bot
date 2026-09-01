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


def extract_pct_stat(text: str) -> Optional[str]:
    match = re.search(r"(\d+)%", text or "")
    return f"{match.group(1)}%" if match else None


def research_trial_line(summary: str, trial_n: Optional[int]) -> Optional[str]:
    if not trial_n:
        return None
    stat = extract_pct_stat(summary)
    lower = (summary or "").lower()
    if stat and "caries" in lower and "6-month" in lower:
        return (
            f"{trial_n:,}-patient trial showed 3-month fluoride recall cuts caries "
            f"recurrence {stat} better than 6-month"
        )
    if stat:
        return f"{trial_n:,}-patient trial showed {stat} improvement"
    return f"{trial_n:,}-patient trial"


def format_match_time(iso: str) -> str:
    if not iso or "T" not in iso:
        return ""
    try:
        time_part = iso.split("T")[1]
        hour = int(time_part.split(":")[0])
        minute = int(time_part.split(":")[1])
        suffix = "pm" if hour >= 12 else "am"
        hour12 = hour % 12 or 12
        if minute:
            return f"{hour12}:{minute:02d}{suffix}"
        return f"{hour12}{suffix}"
    except (ValueError, IndexError):
        return ""


def recall_gap_text(last_visit: str, due_date: str, service_due: str) -> str:
    if "6_month" in service_due or "6mo" in service_due:
        months = months_since(last_visit, due_date) if last_visit and due_date else None
        if months and months > 0:
            return f"{months} months since your last visit — your 6-month cleaning recall is due"
        return "your 6-month cleaning recall is due"
    months = months_since(last_visit, due_date) if last_visit and due_date else None
    if months and months > 0:
        return f"{months} months since your last visit"
    return "your cleaning recall is due"


def short_iso_date(iso: str) -> str:
    if not iso:
        return ""
    date_part = iso.split("T")[0]
    parts = date_part.split("-")
    if len(parts) == 3:
        months = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
        try:
            return f"{int(parts[2])} {months[int(parts[1]) - 1]}"
        except (ValueError, IndexError):
            pass
    return date_part


def months_since(last_date: str, reference: str = "2026-04-26") -> Optional[int]:
    try:
        last = last_date.split("T")[0]
        ref = reference.split("T")[0]
        ly, lm, ld = (int(x) for x in last.split("-"))
        ry, rm, rd = (int(x) for x in ref.split("-"))
        return max(1, (ry - ly) * 12 + (rm - lm) - (1 if rd < ld else 0))
    except (ValueError, AttributeError):
        return None


def truncate(text: str, max_len: int = 900) -> str:
    text = re.sub(r"\s+", " ", text.strip())
    if len(text) <= max_len:
        return text
    return text[: max_len - 3].rstrip() + "..."
