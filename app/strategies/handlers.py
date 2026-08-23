from __future__ import annotations

from typing import Any, Callable, Optional

from app.models.schemas import SendAs
from app.strategies.base import ComposeResult, customer_name, first_active_offer_title, trigger_payload
from app.utils.formatting import (
    digest_item,
    format_ctr,
    merchant_display,
    owner_name,
    pct_change,
    peer_ctr,
    truncate,
    uses_hindi_mix,
)


Handler = Callable[
    [dict[str, Any], dict[str, Any], dict[str, Any], Optional[dict[str, Any]], dict[str, Any], str],
    ComposeResult,
]


def _cta_open() -> str:
    return "open_ended"


def _sk(trg: dict[str, Any]) -> str:
    return str(trg.get("suppression_key", trg.get("id", "unknown")))


def _compose_research_digest(
    category, merchant, trigger, customer, trg_payload, trigger_id
) -> ComposeResult:
    item_id = trg_payload.get("top_item_id")
    item = digest_item(category, item_id) or {}
    name = merchant_display(merchant)
    title = item.get("title", "new research")
    source = item.get("source", "")
    trial_n = item.get("trial_n")
    segment = item.get("patient_segment") or item.get("segment", "")
    aggregate = merchant.get("customer_aggregate") or {}
    cohort_note = ""
    if segment and "high_risk" in str(segment).lower():
        count = aggregate.get("high_risk_adult_count")
        if count:
            cohort_note = f" relevant to your {count} high-risk adult patients"
        else:
            cohort_note = " relevant to your high-risk adult patients"
    trial_part = ""
    if trial_n:
        trial_part = f" — {trial_n:,}-patient trial: "
    body = (
        f"{name}, {source.split(',')[0] if source else 'this week'} issue landed.{cohort_note} —"
        f"{trial_part}{title}."
    )
    if source:
        body += f" Want me to pull the abstract + draft a patient-ed WhatsApp you can share? — {source}"
    else:
        body += " Want me to pull the abstract + draft a patient-ed WhatsApp you can share?"
    return ComposeResult(
        body=truncate(body),
        cta="open_ended",
        send_as="vera",
        suppression_key=_sk(trigger),
        rationale=f"Research digest trigger; anchored on digest item '{item.get('id')}' with source citation.",
        template_params=[name, title[:80], "Want me to draft a patient-ed WhatsApp?"],
    )


def _compose_recall_due(category, merchant, trigger, customer, trg_payload, trigger_id):
    if not customer:
        raise ValueError("recall_due requires customer context")
    cust = customer_name(customer)
    slots = trg_payload.get("available_slots") or []
    offer = first_active_offer_title(merchant, category) or "cleaning"
    slot_text = ""
    if len(slots) >= 2:
        slot_text = f" Apke liye 2 slots ready hain: {slots[0].get('label')} ya {slots[1].get('label')}."
    elif len(slots) == 1:
        slot_text = f" Slot available: {slots[0].get('label')}."
    hi = uses_hindi_mix(merchant, customer)
    clinic = (merchant.get("identity") or {}).get("name", "the clinic")
    due = trg_payload.get("due_date", trg_payload.get("last_service_date", ""))
    if hi:
        body = (
            f"Hi {cust}, {clinic} here 🦷 Your recall is due"
            f"{f' ({due})' if due else ''}.{slot_text} {offer}."
            f" Reply YES for the first slot, or tell us a time that works."
        )
    else:
        body = (
            f"Hi {cust}, {clinic} here — your recall is due"
            f"{f' (due {due})' if due else ''}.{slot_text} {offer}."
            f" Reply YES to book, or suggest a time."
        )
    return ComposeResult(
        body=truncate(body),
        cta="binary_yes_no",
        send_as="merchant_on_behalf",
        suppression_key=_sk(trigger),
        rationale="Customer recall_due trigger with real slots and active offer from merchant catalog.",
        template_params=[cust, offer, slot_text.strip()],
    )


def _compose_perf_dip(category, merchant, trigger, customer, trg_payload, trigger_id):
    name = merchant_display(merchant)
    metric = trg_payload.get("metric", "calls")
    delta = trg_payload.get("delta_pct")
    delta_text = pct_change(delta) if delta is not None else "down"
    offer = first_active_offer_title(merchant, category)
    locality = (merchant.get("identity") or {}).get("locality", "")
    body = (
        f"{name}, your {metric} are {delta_text} this week"
        f"{f' in {locality}' if locality else ''}."
    )
    if offer:
        body += f" You have {offer} active — want me to draft a Google post + WhatsApp reply around it?"
    else:
        body += " Want me to audit what's driving the dip and draft a fix plan?"
    return ComposeResult(
        body=truncate(body),
        cta="open_ended",
        send_as="vera",
        suppression_key=_sk(trigger),
        rationale=f"Perf dip on {metric} ({delta_text}); proposing low-friction draft using merchant offer if available.",
    )


def _compose_renewal_due(category, merchant, trigger, customer, trg_payload, trigger_id):
    name = merchant_display(merchant)
    days = trg_payload.get("days_remaining", (merchant.get("subscription") or {}).get("days_remaining"))
    plan = trg_payload.get("plan", (merchant.get("subscription") or {}).get("plan", "Pro"))
    amount = trg_payload.get("renewal_amount")
    amount_part = f" (₹{amount:,})" if amount else ""
    body = (
        f"{name}, your {plan} plan renews in {days} days{amount_part}. "
        f"Want me to send the renewal link + a summary of what Vera handled for you this month?"
    )
    return ComposeResult(
        body=truncate(body),
        cta="binary_yes_no",
        send_as="vera",
        suppression_key=_sk(trigger),
        rationale="Renewal due trigger with days remaining from payload/subscription.",
    )


def _compose_ipl_match(category, merchant, trigger, customer, trg_payload, trigger_id):
    name = merchant_display(merchant)
    match = trg_payload.get("match", "today's match")
    venue = trg_payload.get("venue", "")
    is_weeknight = trg_payload.get("is_weeknight", True)
    offer = first_active_offer_title(merchant, category)
    if is_weeknight:
        body = (
            f"Quick heads-up {name} — {match} tonight{f' at {venue}' if venue else ''}. "
            f"Match nights usually lift delivery orders 15-20%. "
        )
        if offer:
            body += f"Push {offer} as a match-night special on Swiggy/Zomato? Want me to draft the banner?"
        else:
            body += "Want me to draft a match-night delivery promo for tonight?"
    else:
        body = (
            f"Quick heads-up {name} — {match} tonight{f' at {venue}' if venue else ''}. "
            f"Saturday IPL matches often shift covers down as people watch at home. "
        )
        if offer:
            body += f"Skip generic match promos; push {offer} as delivery-only instead. Want me to draft the Swiggy banner?"
        else:
            body += "Want me to draft a delivery-only special instead of a dine-in match promo?"
    return ComposeResult(
        body=truncate(body),
        cta="open_ended",
        send_as="vera",
        suppression_key=_sk(trigger),
        rationale="IPL match trigger with weeknight/weekend-aware recommendation and existing offer leverage.",
    )


def _compose_curious_ask(category, merchant, trigger, customer, trg_payload, trigger_id):
    name = owner_name(merchant)
    biz = (merchant.get("identity") or {}).get("name", "your shop")
    body = (
        f"Hi {name}! Quick check — what service has been most asked-for this week at {biz}? "
        f"I'll turn the answer into a Google post + a 4-line WhatsApp reply for pricing questions. Takes 5 min."
    )
    return ComposeResult(
        body=truncate(body),
        cta="open_ended",
        send_as="vera",
        suppression_key=_sk(trigger),
        rationale="Curious-ask cadence; low-friction question with reciprocity (draft post + reply).",
    )


def _compose_wedding_followup(category, merchant, trigger, customer, trg_payload, trigger_id):
    if not customer:
        raise ValueError("wedding followup requires customer")
    cust = customer_name(customer)
    days = trg_payload.get("days_to_wedding")
    wedding = trg_payload.get("wedding_date", (customer.get("preferences") or {}).get("wedding_date", ""))
    owner = owner_name(merchant)
    biz = (merchant.get("identity") or {}).get("name", "the salon")
    offer = first_active_offer_title(merchant, category)
    days_part = f"{days} days to your wedding" if days else "your wedding window"
    offer_part = f" {offer}." if offer else "."
    body = (
        f"Hi {cust} 💍 {owner} from {biz} here. {days_part} — good time to start skin-prep before bridal bookings peak.{offer_part} "
        f"Want me to block your preferred Saturday slot for the first session next week?"
    )
    return ComposeResult(
        body=truncate(body),
        cta="open_ended",
        send_as="merchant_on_behalf",
        suppression_key=_sk(trigger),
        rationale="Bridal followup with wedding countdown and merchant offer from catalog.",
    )


def _compose_supply_alert(category, merchant, trigger, customer, trg_payload, trigger_id):
    name = merchant_display(merchant)
    batches = trg_payload.get("batches") or trg_payload.get("batch_numbers") or []
    batch_text = ", ".join(batches[:2]) if batches else trg_payload.get("batch_id", "listed batches")
    affected = trg_payload.get("affected_customers") or trg_payload.get("affected_count")
    agg = merchant.get("customer_aggregate") or {}
    if affected is None:
        affected = agg.get("chronic_rx_affected_count") or agg.get("total_unique_ytd")
    body = (
        f"{name}, urgent: voluntary recall on {batch_text} — "
        f"{trg_payload.get('reason', 'quality check required')}. "
    )
    if affected:
        body += f"{affected} of your customers may need replacement. "
    body += "Want me to draft their WhatsApp note + the replacement-pickup workflow?"
    return ComposeResult(
        body=truncate(body),
        cta="open_ended",
        send_as="vera",
        suppression_key=_sk(trigger),
        rationale="Supply alert/compliance trigger with batch specificity and affected customer count from context.",
    )


def _compose_chronic_refill(category, merchant, trigger, customer, trg_payload, trigger_id):
    if not customer:
        raise ValueError("chronic refill requires customer")
    cust = customer_name(customer)
    meds = trg_payload.get("medicines") or trg_payload.get("molecules") or []
    med_text = ", ".join(meds[:5]) if meds else "your monthly medicines"
    run_out = trg_payload.get("run_out_date", trg_payload.get("due_date", ""))
    total = trg_payload.get("total_amount")
    savings = trg_payload.get("savings")
    pharmacy = (merchant.get("identity") or {}).get("name", "the pharmacy")
    locality = (merchant.get("identity") or {}).get("locality", "")
    body = f"Namaste — {pharmacy}{f' {locality}' if locality else ''}. {cust}'s {med_text}"
    if run_out:
        body += f" run out on {run_out}."
    else:
        body += " refill is due soon."
    if total:
        body += f" Total ₹{total:,}"
        if savings:
            body += f" (₹{savings:,} saved with senior discount)."
        body += "."
    body += " Reply CONFIRM to dispatch, or call if any dosage change."
    return ComposeResult(
        body=truncate(body),
        cta="binary_yes_no",
        send_as="merchant_on_behalf",
        suppression_key=_sk(trigger),
        rationale="Chronic refill due with molecule names and pricing from trigger payload.",
    )


def _compose_seasonal_dip(category, merchant, trigger, customer, trg_payload, trigger_id):
    name = merchant_display(merchant)
    delta = trg_payload.get("delta_pct") or (merchant.get("performance") or {}).get("delta_7d", {}).get("views_pct")
    delta_text = pct_change(delta) if delta is not None else "down"
    members = trg_payload.get("active_members") or (merchant.get("customer_aggregate") or {}).get("active_members")
    window = trg_payload.get("season_window", "Apr-Jun")
    body = (
        f"{name}, views are {delta_text} this week — normal {window} lull for metro gyms "
        f"(-25 to -35% is typical). "
    )
    if members:
        body += f"Focus retention on your {members} members. "
    body += 'Want me to draft a "summer attendance challenge" to keep them through the dip?'
    return ComposeResult(
        body=truncate(body),
        cta="open_ended",
        send_as="vera",
        suppression_key=_sk(trigger),
        rationale="Seasonal perf dip reframed with industry benchmark; retention-focused CTA.",
    )


def _compose_lapsed_hard(category, merchant, trigger, customer, trg_payload, trigger_id):
    if not customer:
        raise ValueError("lapsed customer trigger requires customer")
    cust = customer_name(customer)
    owner = owner_name(merchant)
    biz = (merchant.get("identity") or {}).get("name", "here")
    days = trg_payload.get("days_since_visit", trg_payload.get("days_lapsed"))
    offer = first_active_offer_title(merchant, category)
    class_name = trg_payload.get("new_class", trg_payload.get("recommended_class", "evening class"))
    body = (
        f"Hi {cust} 👋 {owner} from {biz}. "
        f"{f'It has been about {days} days' if days else 'It has been a while'} — happens to most members, no judgment. "
        f"We added a {class_name} that fits your goals well. "
    )
    if offer:
        body += f"{offer}. "
    body += "Reply YES for a free trial spot — no commitment, no auto-charge."
    return ComposeResult(
        body=truncate(body),
        cta="binary_yes_stop",
        send_as="merchant_on_behalf",
        suppression_key=_sk(trigger),
        rationale="Lapsed customer winback with no-shame framing and low-friction trial CTA.",
    )


def _compose_active_planning(category, merchant, trigger, customer, trg_payload, trigger_id):
    name = merchant_display(merchant)
    topic = trg_payload.get("topic", trg_payload.get("planning_topic", "your idea"))
    locality = (merchant.get("identity") or {}).get("locality", "")
    body = (
        f"{name}, here's a starter draft for {topic}"
        f"{f' in {locality}' if locality else ''} — edit anything:\n"
        f"- Tier 1: 10 units @ discounted rate\n"
        f"- Tier 2: 25 units @ better rate + bonus\n"
        f"- Day-before WhatsApp order, fixed delivery window\n\n"
        f"Want me to draft a 3-line WhatsApp to send to nearby offices?"
    )
    return ComposeResult(
        body=truncate(body),
        cta="open_ended",
        send_as="vera",
        suppression_key=_sk(trigger),
        rationale="Active planning intent — merchant asked for a draft; providing artifact + outreach CTA.",
    )


def _compose_review_theme(category, merchant, trigger, customer, trg_payload, trigger_id):
    name = merchant_display(merchant)
    theme = trg_payload.get("theme", "an issue")
    count = trg_payload.get("occurrences_30d")
    quote = trg_payload.get("common_quote")
    body = f"{name}, {count} reviews this month mention '{theme.replace('_', ' ')}'" if count else f"{name}, a review theme emerged: '{theme.replace('_', ' ')}'"
    if quote:
        body += f' — e.g. "{quote}"'
    body += ". Want me to draft a reply template + a fix checklist for your team?"
    return ComposeResult(
        body=truncate(body),
        cta="open_ended",
        send_as="vera",
        suppression_key=_sk(trigger),
        rationale=f"Review theme trigger '{theme}' with occurrence count and sample quote from payload.",
    )


def _compose_regulation_change(category, merchant, trigger, customer, trg_payload, trigger_id):
    name = merchant_display(merchant)
    item = digest_item(category, trg_payload.get("top_item_id")) or {}
    title = item.get("title", trg_payload.get("title", "regulatory update"))
    source = item.get("source", trg_payload.get("source", ""))
    deadline = trg_payload.get("deadline_iso", trg_payload.get("deadline", ""))
    body = f"{name}, compliance update: {title}"
    if deadline:
        body += f" (effective {deadline})"
    if source:
        body += f" — {source}"
    body += ". Want me to pull the checklist + draft a patient/staff note if needed?"
    return ComposeResult(
        body=truncate(body),
        cta="open_ended",
        send_as="vera",
        suppression_key=_sk(trigger),
        rationale="Regulation change trigger with source/deadline from digest or payload.",
    )


def _compose_milestone(category, merchant, trigger, customer, trg_payload, trigger_id):
    name = merchant_display(merchant)
    milestone = trg_payload.get("milestone", trg_payload.get("metric", "milestone"))
    value = trg_payload.get("value", trg_payload.get("count"))
    body = f"{name}, you crossed {value} {milestone}! "
    body += "Want me to draft a Google post + WhatsApp story to capitalize on the momentum?"
    return ComposeResult(
        body=truncate(body),
        cta="open_ended",
        send_as="vera",
        suppression_key=_sk(trigger),
        rationale="Milestone trigger celebrating verifiable achievement from payload.",
    )


def _compose_festival(category, merchant, trigger, customer, trg_payload, trigger_id):
    name = merchant_display(merchant)
    festival = trg_payload.get("festival", "the upcoming festival")
    days = trg_payload.get("days_until")
    offer = first_active_offer_title(merchant, category)
    body = f"{name}, {festival} is {days} days out" if days else f"{name}, {festival} is coming up"
    if offer:
        body += f". You have {offer} — want me to draft a festival campaign around it?"
    else:
        body += ". Want me to draft a festival offer + Google post?"
    return ComposeResult(
        body=truncate(body),
        cta="open_ended",
        send_as="vera",
        suppression_key=_sk(trigger),
        rationale=f"Festival trigger ({festival}) with days-until and merchant offer leverage.",
    )


def _compose_perf_spike(category, merchant, trigger, customer, trg_payload, trigger_id):
    name = merchant_display(merchant)
    metric = trg_payload.get("metric", "views")
    delta = trg_payload.get("delta_pct")
    delta_text = pct_change(delta) if delta is not None else "up"
    body = (
        f"{name}, {metric} are {delta_text} vs your baseline — good momentum. "
        f"Want me to draft a Google post to lock in the spike while it's hot?"
    )
    return ComposeResult(
        body=truncate(body),
        cta="open_ended",
        send_as="vera",
        suppression_key=_sk(trigger),
        rationale=f"Perf spike on {metric}; capitalize with timely post draft.",
    )


def _compose_competitor(category, merchant, trigger, customer, trg_payload, trigger_id):
    name = merchant_display(merchant)
    comp = trg_payload.get("competitor_name", "a new competitor")
    distance = trg_payload.get("distance_km")
    offer = first_active_offer_title(merchant, category)
    dist_part = f" {distance}km away" if distance else " nearby"
    body = f"{name}, {comp} opened{dist_part}."
    if offer:
        body += f" Your {offer} is a strong differentiator — want me to update your GBP highlights + draft a comparison post?"
    else:
        body += " Want me to audit your GBP vs theirs and suggest 3 differentiation moves?"
    return ComposeResult(
        body=truncate(body),
        cta="open_ended",
        send_as="vera",
        suppression_key=_sk(trigger),
        rationale="Competitor opened trigger using named competitor from payload only.",
    )


def _compose_dormant(category, merchant, trigger, customer, trg_payload, trigger_id):
    name = merchant_display(merchant)
    days = trg_payload.get("days_silent", 14)
    ctr = (merchant.get("performance") or {}).get("ctr")
    peer = peer_ctr(category)
    body = f"{name}, it's been {days} days since we synced."
    if ctr is not None and peer:
        body += f" Your CTR is {format_ctr(ctr)} vs {format_ctr(peer)} peer median."
    body += " Want a 2-min profile audit summary?"
    return ComposeResult(
        body=truncate(body),
        cta="open_ended",
        send_as="vera",
        suppression_key=_sk(trigger),
        rationale="Dormant-with-Vera re-engagement using peer CTR comparison when available.",
    )


def _compose_generic(category, merchant, trigger, customer, trg_payload, trigger_id):
    name = merchant_display(merchant)
    kind = trigger.get("kind", "update")
    offer = first_active_offer_title(merchant, category)
    locality = (merchant.get("identity") or {}).get("locality", "")
    body = f"{name}, flagged a {kind.replace('_', ' ')}"
    if locality:
        body += f" for {locality}"
    body += "."
    if offer:
        body += f" With {offer} active, want me to draft the next step?"
    else:
        body += " Want me to draft the next step?"
    return ComposeResult(
        body=truncate(body),
        cta="open_ended",
        send_as="merchant_on_behalf" if trigger.get("scope") == "customer" else "vera",
        suppression_key=_sk(trigger),
        rationale=f"Fallback handler for trigger kind '{kind}' using available merchant/category facts.",
    )


HANDLERS: dict[str, Handler] = {
    "research_digest": _compose_research_digest,
    "recall_due": _compose_recall_due,
    "perf_dip": _compose_perf_dip,
    "renewal_due": _compose_renewal_due,
    "ipl_match_today": _compose_ipl_match,
    "curious_ask_due": _compose_curious_ask,
    "wedding_package_followup": _compose_wedding_followup,
    "supply_alert": _compose_supply_alert,
    "chronic_refill_due": _compose_chronic_refill,
    "seasonal_perf_dip": _compose_seasonal_dip,
    "customer_lapsed_hard": _compose_lapsed_hard,
    "customer_lapsed_soft": _compose_lapsed_hard,
    "active_planning_intent": _compose_active_planning,
    "corporate_thali_planning": _compose_active_planning,
    "kids_program_drafting": _compose_active_planning,
    "kids_yoga_program_drafting": _compose_active_planning,
    "review_theme_emerged": _compose_review_theme,
    "regulation_change": _compose_regulation_change,
    "cde_opportunity": _compose_research_digest,
    "cde_webinar": _compose_research_digest,
    "milestone_reached": _compose_milestone,
    "festival_upcoming": _compose_festival,
    "perf_spike": _compose_perf_spike,
    "competitor_opened": _compose_competitor,
    "dormant_with_vera": _compose_dormant,
    "winback_eligible": _compose_dormant,
    "category_seasonal": _compose_festival,
    "gbp_unverified": _compose_dormant,
    "trial_followup": _compose_lapsed_hard,
    "appointment_tomorrow": _compose_recall_due,
    "summer_demand_shift": _compose_seasonal_dip,
}


def compose_message(
    category: dict[str, Any],
    merchant: dict[str, Any],
    trigger: dict[str, Any],
    customer: Optional[dict[str, Any]],
    trigger_id: str,
) -> ComposeResult:
    kind = str(trigger.get("kind", ""))
    handler = HANDLERS.get(kind, _compose_generic)
    trg_payload = trigger_payload(trigger)
    result = handler(category, merchant, trigger, customer, trg_payload, trigger_id)
    if trigger.get("scope") == "customer":
        result.send_as = "merchant_on_behalf"
    elif result.send_as != "merchant_on_behalf":
        result.send_as = "vera"
    return result
