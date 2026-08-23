from __future__ import annotations

from datetime import datetime
from typing import Any, Optional


KIND_WEIGHTS: dict[str, float] = {
    "supply_alert": 5.0,
    "regulation_change": 4.8,
    "recall_due": 4.5,
    "chronic_refill_due": 4.5,
    "perf_dip": 4.2,
    "renewal_due": 4.0,
    "review_theme_emerged": 3.8,
    "ipl_match_today": 3.6,
    "research_digest": 3.2,
    "cde_webinar": 3.0,
    "festival_upcoming": 2.8,
    "perf_spike": 2.8,
    "milestone_reached": 2.6,
    "customer_lapsed_hard": 2.5,
    "customer_lapsed_soft": 2.4,
    "wedding_package_followup": 2.3,
    "active_planning_intent": 2.2,
    "curious_ask_due": 1.8,
    "seasonal_perf_dip": 2.0,
    "winback_eligible": 2.0,
    "appointment_tomorrow": 3.5,
    "corporate_thali_planning": 2.5,
    "kids_program_drafting": 2.2,
    "summer_demand_shift": 2.4,
    "competitor_opened": 2.6,
    "weather_heatwave": 2.2,
    "local_news_event": 2.0,
    "category_trend_movement": 2.4,
    "scheduled_recurring": 1.5,
    "dormant_with_vera": 1.8,
}


def _parse_expires(expires_at: Optional[str]) -> Optional[datetime]:
    if not expires_at:
        return None
    try:
        return datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
    except ValueError:
        return None


def score_trigger(
    trigger: dict[str, Any],
    merchant: dict[str, Any],
    category: dict[str, Any],
    now_iso: str,
    suppressed: bool,
) -> float:
    if suppressed:
        return -1.0

    expires = _parse_expires(trigger.get("expires_at"))
    if expires:
        try:
            now = datetime.fromisoformat(now_iso.replace("Z", "+00:00"))
            if expires.tzinfo and now.tzinfo is None:
                now = now.replace(tzinfo=expires.tzinfo)
            if now > expires:
                return -1.0
        except ValueError:
            pass

    kind = str(trigger.get("kind", ""))
    urgency = int(trigger.get("urgency", 1))
    base = KIND_WEIGHTS.get(kind, 2.0) * urgency

    signals = merchant.get("signals") or []
    signal_text = " ".join(signals).lower()

    if kind == "research_digest" and "high_risk" in signal_text:
        base += 2.0
    if kind == "perf_dip" and "perf_dip" in signal_text:
        base += 2.5
    if kind == "renewal_due" and "renewal" in signal_text:
        base += 2.0
    if kind == "recall_due":
        base += 1.5
    if kind == "supply_alert":
        base += 3.0

    perf = merchant.get("performance") or {}
    delta = perf.get("delta_7d") or {}
    if kind == "perf_dip" and any(
        (delta.get(k) or 0) < -0.15 for k in ("views_pct", "calls_pct", "ctr_pct")
    ):
        base += 1.5
    if kind == "perf_spike" and any((delta.get(k) or 0) > 0.15 for k in ("views_pct", "calls_pct")):
        base += 1.0

    peer = category.get("peer_stats") or {}
    ctr = perf.get("ctr")
    if ctr is not None and peer.get("avg_ctr") and ctr < peer["avg_ctr"]:
        if kind in ("research_digest", "curious_ask_due", "review_theme_emerged"):
            base += 1.0

    return base


def rank_triggers(
    triggers: list[tuple[str, dict[str, Any]]],
    merchants: dict[str, dict[str, Any]],
    categories: dict[str, dict[str, Any]],
    now_iso: str,
    is_suppressed_fn,
) -> list[tuple[str, dict[str, Any], float]]:
    scored: list[tuple[str, dict[str, Any], float]] = []
    for trigger_id, trigger in triggers:
        merchant_id = trigger.get("merchant_id")
        if not merchant_id:
            continue
        merchant = merchants.get(merchant_id)
        if not merchant:
            continue
        category_slug = merchant.get("category_slug", "")
        category = categories.get(category_slug, {})
        suppression_key = str(trigger.get("suppression_key", trigger_id))
        score = score_trigger(
            trigger,
            merchant,
            category,
            now_iso,
            is_suppressed_fn(suppression_key),
        )
        if score >= 0:
            scored.append((trigger_id, trigger, score))
    scored.sort(key=lambda x: (-x[2], x[0]))
    return scored
