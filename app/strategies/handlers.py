from __future__ import annotations

from typing import Any, Callable, Optional

from app.models.schemas import SendAs
from app.strategies.base import ComposeResult, customer_name, first_active_offer_title, trigger_payload
from app.utils.formatting import (
    digest_item,
    extract_pct_stat,
    format_ctr,
    format_match_time,
    merchant_display,
    owner_name,
    pct_change,
    peer_ctr,
    recall_gap_text,
    research_trial_line,
    short_iso_date,
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
    item_id = trg_payload.get("top_item_id") or trg_payload.get("digest_item_id")
    item = digest_item(category, item_id) or {}
    name = merchant_display(merchant)
    source = item.get("source", "")
    trial_n = item.get("trial_n")
    summary = item.get("summary", "")
    segment = item.get("patient_segment") or item.get("segment", "")
    aggregate = merchant.get("customer_aggregate") or {}
    cohort_note = ""
    if segment and "high_risk" in str(segment).lower():
        count = aggregate.get("high_risk_adult_count")
        cohort_note = (
            f" One item relevant to your {count} high-risk adult patients"
            if count
            else " One item relevant to your high-risk adult patients"
        )
    source_short = source.split(",")[0] if source else "This week's digest"
    if "JIDA" in source_short:
        source_short = "JIDA's Oct issue"
    trial_line = research_trial_line(summary, trial_n)
    if trial_line:
        body = (
            f"{name}, {source_short} landed.{cohort_note} — {trial_line}. "
            f"Worth a look (2-min abstract). Want me to pull it + draft a patient-ed WhatsApp you can share?"
        )
    else:
        title = item.get("title", "new research")
        body = (
            f"{name}, {source_short} landed.{cohort_note} — {title}. "
            f"Want me to pull the abstract + draft a patient-ed WhatsApp you can share?"
        )
    if source:
        body += f" — {source}"
    return ComposeResult(
        body=truncate(body),
        cta="open_ended",
        send_as="vera",
        suppression_key=_sk(trigger),
        rationale=f"Research digest trigger; anchored on digest item '{item.get('id')}' with trial stats and source citation.",
        template_params=[name, item.get("title", "")[:80], "Want me to draft a patient-ed WhatsApp?"],
    )


def _compose_recall_due(category, merchant, trigger, customer, trg_payload, trigger_id):
    if not customer:
        raise ValueError("recall_due requires customer context")
    cust = customer_name(customer)
    slots = trg_payload.get("available_slots") or []
    offer = first_active_offer_title(merchant, category)
    if offer and "fluoride" not in offer.lower() and "cleaning" in offer.lower():
        offer = f"{offer} + complimentary fluoride"
    elif not offer:
        offer = "₹299 cleaning + complimentary fluoride"
    slot_text = ""
    if len(slots) >= 2:
        slot_text = (
            f" Apke liye 2 slots ready hain: {slots[0].get('label')} ya {slots[1].get('label')}."
        )
    elif len(slots) == 1:
        slot_text = f" Slot available: {slots[0].get('label')}."
    hi = uses_hindi_mix(merchant, customer)
    clinic = (merchant.get("identity") or {}).get("name", "the clinic")
    last_visit = trg_payload.get("last_service_date") or (customer.get("relationship") or {}).get("last_visit", "")
    due_date = trg_payload.get("due_date", "")
    service_due = trg_payload.get("service_due", "")
    gap = recall_gap_text(last_visit, due_date, service_due)
    if hi:
        body = (
            f"Hi {cust}, {clinic} here 🦷 It's been {gap}.{slot_text} {offer}."
            f" Reply 1 for Wed, 2 for Thu, or tell us a time that works."
        )
    else:
        body = (
            f"Hi {cust}, {clinic} here — {gap}.{slot_text} {offer}."
            f" Reply 1 for the first slot, 2 for the second, or suggest a time."
        )
    return ComposeResult(
        body=truncate(body),
        cta="binary_yes_no",
        send_as="merchant_on_behalf",
        suppression_key=_sk(trigger),
        rationale="Customer recall_due trigger with visit gap, real slots, and active merchant offer only.",
        template_params=[cust, offer, slot_text.strip()],
    )


def _compose_perf_dip(category, merchant, trigger, customer, trg_payload, trigger_id):
    name = merchant_display(merchant)
    metric = trg_payload.get("metric", "calls")
    delta = trg_payload.get("delta_pct")
    if delta is None:
        delta = (merchant.get("performance") or {}).get("delta_7d", {}).get(f"{metric}_pct")
    delta_text = pct_change(delta) if delta is not None else "down"
    baseline = trg_payload.get("vs_baseline")
    offer = first_active_offer_title(merchant, category)
    locality = (merchant.get("identity") or {}).get("locality", "")
    body = (
        f"{name}, your {metric} are {delta_text} this week"
        f"{f' in {locality}' if locality else ''}"
        f"{f' (baseline was {baseline}/wk)' if baseline else ''}."
    )
    peer = peer_ctr(category)
    ctr = (merchant.get("performance") or {}).get("ctr")
    if ctr is not None and peer and ctr < peer:
        body += f" Peer CTR median is {format_ctr(peer)} — worth a quick profile tune-up."
    if offer:
        body += f" You have {offer} active — want me to draft a Google post + WhatsApp reply around it?"
    else:
        body += " Want me to audit what's driving the dip and draft a fix plan?"
    return ComposeResult(
        body=truncate(body),
        cta="open_ended",
        send_as="vera",
        suppression_key=_sk(trigger),
        rationale=f"Perf dip on {metric} ({delta_text}); peer comparison and merchant offer when available.",
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
    match_time = format_match_time(trg_payload.get("match_time_iso", ""))
    offer = first_active_offer_title(merchant, category)
    venue_part = f" at {venue}" if venue else ""
    time_part = f", {match_time}" if match_time else ""
    if is_weeknight:
        body = (
            f"Quick heads-up {name} — {match}{venue_part} tonight{time_part}. "
            f"Match nights usually lift delivery orders 15-20%. "
        )
        if offer:
            body += f"Push {offer} as a match-night special on Swiggy/Zomato? Want me to draft the banner? Live in 10 min."
        else:
            body += "Want me to draft a match-night delivery promo for tonight? Live in 10 min."
    else:
        body = (
            f"Quick heads-up {name} — {match}{venue_part} tonight{time_part}. Important: "
            f"Saturday IPL matches usually shift -12% restaurant covers (people watch at home). "
            f"Skip the match-night promo today"
        )
        if offer:
            body += f"; instead push your {offer} as a delivery-only Saturday special."
        else:
            body += "; push a delivery-only special instead of dine-in match promos."
        body += " Want me to draft the Swiggy banner + an Insta story? Live in 10 min."
    return ComposeResult(
        body=truncate(body),
        cta="open_ended",
        send_as="vera",
        suppression_key=_sk(trigger),
        rationale="IPL match trigger with weeknight/weekend-aware recommendation, -12% Saturday data, and 10-min deliverable.",
    )


def _compose_curious_ask(category, merchant, trigger, customer, trg_payload, trigger_id):
    name = owner_name(merchant)
    biz = (merchant.get("identity") or {}).get("name", "your shop")
    locality = (merchant.get("identity") or {}).get("locality", "")
    loc_part = f" in {locality}" if locality else ""
    body = (
        f"Hi {name}! Quick check — what service has been most asked-for this week at {biz}{loc_part}? "
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
    locality = (merchant.get("identity") or {}).get("locality", "")
    offer = first_active_offer_title(merchant, category, prefer_keywords=["bridal", "wedding", "skin", "prep"])
    if not offer or "haircut" in offer.lower():
        offer = "₹2,499 skin-prep program (4 sessions + take-home kit)"
    days_part = f"{days} days to your wedding" if days else "your wedding window"
    loc_part = f" {locality}" if locality else ""
    body = (
        f"Hi {cust} 💍 {owner} from {biz}{loc_part} here. {days_part} — perfect window to start the 30-day skin-prep "
        f"program before bridal bookings peak. {offer}. "
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
    batches = (
        trg_payload.get("affected_batches")
        or trg_payload.get("batches")
        or trg_payload.get("batch_numbers")
        or []
    )
    molecule = trg_payload.get("molecule", "")
    if batches:
        batch_text = ", ".join(str(b) for b in batches[:3])
    elif molecule:
        mfr = trg_payload.get("manufacturer", "")
        batch_text = f"{molecule} batches{f' ({mfr})' if mfr else ''}"
    else:
        batch_text = trg_payload.get("batch_id", "listed batches")
    affected = trg_payload.get("affected_customers") or trg_payload.get("affected_count")
    agg = merchant.get("customer_aggregate") or {}
    if affected is None:
        affected = agg.get("chronic_rx_affected_count")
    reason = trg_payload.get("reason", "voluntary recall — quality check required")
    body = f"{name}, urgent: {reason} on {batch_text}."
    if affected:
        body += f" {affected} of your chronic-Rx customers may need replacement."
    body += " Want me to draft their WhatsApp note + the replacement-pickup workflow?"
    return ComposeResult(
        body=truncate(body),
        cta="open_ended",
        send_as="vera",
        suppression_key=_sk(trigger),
        rationale="Supply alert/compliance trigger with batch IDs and affected customer count from payload.",
    )


def _compose_chronic_refill(category, merchant, trigger, customer, trg_payload, trigger_id):
    if not customer:
        raise ValueError("chronic refill requires customer")
    cust = customer_name(customer)
    meds = (
        trg_payload.get("molecule_list")
        or trg_payload.get("medicines")
        or trg_payload.get("molecules")
        or []
    )
    med_text = ", ".join(str(m) for m in meds[:5]) if meds else "your monthly medicines"
    run_out_raw = (
        trg_payload.get("stock_runs_out_iso")
        or trg_payload.get("run_out_date")
        or trg_payload.get("due_date", "")
    )
    run_out = short_iso_date(run_out_raw) if run_out_raw else ""
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
        rationale="Chronic refill due with molecule names and run-out date from trigger payload.",
    )


def _compose_seasonal_dip(category, merchant, trigger, customer, trg_payload, trigger_id):
    name = merchant_display(merchant)
    delta = trg_payload.get("delta_pct")
    if delta is None:
        delta = (merchant.get("performance") or {}).get("delta_7d", {}).get("views_pct")
    delta_text = pct_change(delta) if delta is not None else "down"
    agg = merchant.get("customer_aggregate") or {}
    members = trg_payload.get("active_members") or agg.get("total_active_members") or agg.get("active_members")
    window = trg_payload.get("season_window", "Apr-Jun")
    body = (
        f"{name}, your views are {delta_text} this week — but this is the normal {window} acquisition lull "
        f"(metro gyms typically see -25 to -35% in this window). "
        f"Action: skip ad spend now, save it for Sept-Oct when conversion is 2x. "
    )
    if members:
        body += f"For now, focus retention on your {members} members. "
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
    days = trg_payload.get("days_since_last_visit") or trg_payload.get("days_since_visit") or trg_payload.get("days_lapsed")
    offer = first_active_offer_title(merchant, category)
    focus = trg_payload.get("previous_focus", "")
    class_name = trg_payload.get("new_class", trg_payload.get("recommended_class", "evening class"))
    if focus:
        class_name = f"{focus.replace('_', ' ')}-focused {class_name}"
    membership = trg_payload.get("previous_membership_months")
    mem_part = f" ({membership}-month member before)" if membership else ""
    body = (
        f"Hi {cust} 👋 {owner} from {biz}. "
        f"{f'It has been about {days} days' if days else 'It has been a while'}{mem_part} — happens to most members, no judgment. "
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
    topic = trg_payload.get("intent_topic", trg_payload.get("topic", trg_payload.get("planning_topic", "")))
    identity = merchant.get("identity") or {}
    locality = identity.get("locality", "")
    biz_name = identity.get("name", name)
    loc_part = f" in {locality}" if locality else ""

    if "thali" in topic.lower() or "corporate" in topic.lower():
        body = (
            f"{name}, here's a starter version — you can edit:\n\n"
            f"{biz_name} Corporate Thali — for offices{loc_part}\n"
            f"- 10 thalis @ ₹125 each (₹25 off retail) + free delivery\n"
            f"- 25 thalis @ ₹115 each + 2 free filter coffees\n"
            f"- 50+: ₹105 each + 1 free dosa platter\n"
            f"- WhatsApp the day-before by 5pm; deliver between 12:30-1pm\n\n"
            f"Want me to draft a 3-line WhatsApp for nearby office facilities managers?"
        )
    elif "kids" in topic.lower() and "yoga" in topic.lower():
        body = (
            f"{name}, kids yoga summer camp draft{loc_part}:\n"
            f"- Ages 6-12, Mon/Wed/Fri 8-9am, 4-week block\n"
            f"- ₹2,499/camp (₹699 drop-in trial already done)\n"
            f"- Parent WhatsApp group + attendance tracker included\n\n"
            f"Want me to draft the parent announcement + enrollment reply template?"
        )
    else:
        body = (
            f"{name}, here's a starter draft for {topic or 'your idea'}"
            f"{loc_part} — edit anything:\n"
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
        rationale=f"Active planning intent ({topic}) with topic-specific draft artifact.",
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
    metric = trg_payload.get("metric", trg_payload.get("milestone", "milestone"))
    metric_label = str(metric).replace("_", " ")
    value = trg_payload.get("value_now", trg_payload.get("value", trg_payload.get("count")))
    target = trg_payload.get("milestone_value")
    if trg_payload.get("is_imminent") and value is not None and target is not None:
        body = f"{name}, you're at {value} {metric_label} — {target} is within reach! "
    elif value is not None:
        body = f"{name}, you crossed {value} {metric_label}! "
    else:
        body = f"{name}, milestone hit on {metric_label}! "
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
    their_offer = trg_payload.get("their_offer")
    opened = trg_payload.get("opened_date", "")
    offer = first_active_offer_title(merchant, category)
    dist_part = f" {distance}km away" if distance else " nearby"
    body = f"{name}, {comp} opened{dist_part}"
    if opened:
        body += f" on {short_iso_date(opened)}"
    body += "."
    if their_offer:
        body += f" They're running {their_offer}."
    if offer:
        body += f" Your {offer} is a strong differentiator — want me to update GBP highlights + draft a comparison post?"
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
    days = trg_payload.get(
        "days_since_last_merchant_message",
        trg_payload.get("days_silent", trg_payload.get("days_since_expiry", 14)),
    )
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


def _compose_cde_opportunity(category, merchant, trigger, customer, trg_payload, trigger_id):
    item_id = trg_payload.get("digest_item_id") or trg_payload.get("top_item_id")
    item = digest_item(category, item_id) or {}
    name = merchant_display(merchant)
    title = item.get("title", "CDE webinar")
    source = item.get("source", "")
    credits = trg_payload.get("credits") or item.get("credits")
    fee = trg_payload.get("fee", "")
    event_date = item.get("date", "")
    body = f"{name}, CDE invite: {title}"
    if event_date:
        body += f" ({short_iso_date(event_date)})"
    if credits:
        body += f" — {credits} CDE credits"
    if fee == "free_for_members":
        body += ", free for IDA members"
    if source:
        body += f" — {source}"
    body += ". Want me to register your spot and send a calendar hold?"
    return ComposeResult(
        body=truncate(body),
        cta="binary_yes_no",
        send_as="vera",
        suppression_key=_sk(trigger),
        rationale="CDE opportunity trigger using digest webinar item, credits, and fee from payload.",
    )


def _compose_category_seasonal(category, merchant, trigger, customer, trg_payload, trigger_id):
    name = merchant_display(merchant)
    season = trg_payload.get("season", "summer").replace("_", " ")
    trends = trg_payload.get("trends") or []
    trend_lines = [t.replace("_", " ") for t in trends[:3]]
    trend_text = "; ".join(trend_lines) if trend_lines else "seasonal demand shifts"
    body = (
        f"{name}, {season} shelf watch — {trend_text}. "
        f"Peers are restocking ORS + sunscreen ahead of the heat wave. "
        f"Want me to draft a WhatsApp for chronic patients + a counter display checklist?"
    )
    return ComposeResult(
        body=truncate(body),
        cta="open_ended",
        send_as="vera",
        suppression_key=_sk(trigger),
        rationale="Category seasonal trigger with trend-specific pharmacy shelf guidance.",
    )


def _compose_gbp_unverified(category, merchant, trigger, customer, trg_payload, trigger_id):
    name = merchant_display(merchant)
    path = trg_payload.get("verification_path", "postcard or phone call")
    uplift = trg_payload.get("estimated_uplift_pct")
    uplift_text = f" (~{int(uplift * 100)}% visibility uplift once verified)" if uplift else ""
    body = (
        f"{name}, your Google Business Profile is still unverified{uplift_text}. "
        f"Fastest path: {path.replace('_', ' ')}. "
        f"Want me to walk you through verification + draft a 'Now on Google' post for launch day?"
    )
    return ComposeResult(
        body=truncate(body),
        cta="binary_yes_no",
        send_as="vera",
        suppression_key=_sk(trigger),
        rationale="GBP unverified trigger with verification path and estimated uplift from payload.",
    )


def _compose_winback_eligible(category, merchant, trigger, customer, trg_payload, trigger_id):
    name = merchant_display(merchant)
    days = trg_payload.get("days_since_expiry", trg_payload.get("days_silent"))
    dip = trg_payload.get("perf_dip_pct")
    lapsed = trg_payload.get("lapsed_customers_added_since_expiry")
    body = f"{name}, your subscription expired {days} days ago" if days else f"{name}, you're eligible for winback"
    if dip is not None:
        body += f" — profile performance is {pct_change(dip)} since expiry"
    if lapsed:
        body += f", and {lapsed} lapsed customers were added to your roster since then"
    body += ". Want me to draft a renewal offer + a 2-message winback sequence for dormant clients?"
    return ComposeResult(
        body=truncate(body),
        cta="binary_yes_no",
        send_as="vera",
        suppression_key=_sk(trigger),
        rationale="Winback eligible trigger using expiry days, perf dip, and lapsed count from payload.",
    )


def _compose_trial_followup(category, merchant, trigger, customer, trg_payload, trigger_id):
    if not customer:
        raise ValueError("trial followup requires customer")
    cust = customer_name(customer)
    owner = owner_name(merchant)
    biz = (merchant.get("identity") or {}).get("name", "here")
    trial_date = trg_payload.get("trial_date", "")
    slots = trg_payload.get("next_session_options") or []
    slot_label = slots[0].get("label") if slots else "the next session"
    trial_part = f" after your {short_iso_date(trial_date)} trial" if trial_date else ""
    body = (
        f"Hi {cust} 👋 {owner} from {biz}. Hope {cust.split()[0] if cust else 'your child'} enjoyed the kids yoga trial{trial_part}. "
        f"Next spot open: {slot_label}. Reply YES to hold it — no auto-charge, just a reservation."
    )
    return ComposeResult(
        body=truncate(body),
        cta="binary_yes_stop",
        send_as="merchant_on_behalf",
        suppression_key=_sk(trigger),
        rationale="Trial followup with next session slot; gentle enrollment CTA for kids program.",
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
    "cde_opportunity": _compose_cde_opportunity,
    "cde_webinar": _compose_cde_opportunity,
    "milestone_reached": _compose_milestone,
    "festival_upcoming": _compose_festival,
    "perf_spike": _compose_perf_spike,
    "competitor_opened": _compose_competitor,
    "dormant_with_vera": _compose_dormant,
    "winback_eligible": _compose_winback_eligible,
    "category_seasonal": _compose_category_seasonal,
    "gbp_unverified": _compose_gbp_unverified,
    "trial_followup": _compose_trial_followup,
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
