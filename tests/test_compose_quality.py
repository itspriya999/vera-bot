import json
from pathlib import Path

from app.strategies.handlers import compose_message

ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT / "dataset"


def _load():
    merchants = {m["merchant_id"]: m for m in json.loads((DATASET / "merchants_seed.json").read_text())["merchants"]}
    triggers = json.loads((DATASET / "triggers_seed.json").read_text())["triggers"]
    customers = {c["customer_id"]: c for c in json.loads((DATASET / "customers_seed.json").read_text())["customers"]}
    return merchants, triggers, customers


def _compose(trigger_id: str):
    merchants, triggers, customers = _load()
    trigger = next(t for t in triggers if t["id"] == trigger_id)
    merchant = merchants[trigger["merchant_id"]]
    category = json.loads((DATASET / "categories" / f"{merchant['category_slug']}.json").read_text())
    customer = customers.get(trigger.get("customer_id")) if trigger.get("customer_id") else None
    return compose_message(category, merchant, trigger, customer, trigger["id"])


def test_milestone_uses_value_now():
    result = _compose("trg_012_milestone_mylari")
    assert "145" in result.body
    assert "None" not in result.body


def test_supply_alert_uses_batch_ids():
    result = _compose("trg_018_supply_atorvastatin_recall")
    assert "AT2024-1102" in result.body
    assert "listed batches" not in result.body


def test_chronic_refill_uses_molecules_and_date():
    result = _compose("trg_019_chronic_refill_grandfather")
    assert "metformin" in result.body
    assert "atorvastatin" in result.body
    assert "28 Apr" in result.body


def test_perf_dip_no_fabricated_offer():
    result = _compose("trg_004_perf_dip_bharat")
    assert "Dental Cleaning @ ₹299" not in result.body
    assert "audit" in result.body.lower() or "dip" in result.body.lower()


def test_research_digest_includes_stat():
    result = _compose("trg_001_research_digest_dentists")
    assert "38%" in result.body
    assert "2,100" in result.body
    assert "JIDA" in result.body


def test_ipl_saturday_contrarian():
    result = _compose("trg_010_ipl_match_delhi")
    assert "-12%" in result.body
    assert "7:30pm" in result.body
    assert "Buy 1 Pizza" in result.body or "BOGO" in result.body.upper() or "Get 1 Free" in result.body


def test_seasonal_dip_member_count():
    result = _compose("trg_014_seasonal_acquisition_dip_powerhouse")
    assert "245" in result.body
    assert "-30%" in result.body or "30%" in result.body


def test_corporate_thali_uses_merchant_name():
    result = _compose("trg_013_corporate_thali_planning")
    assert "Mylari" in result.body
    assert "Indiranagar" in result.body
    assert "₹125" in result.body


def test_competitor_mentions_their_offer():
    result = _compose("trg_023_competitor_opened_dentist")
    assert "₹199" in result.body
    assert "Smile Studio" in result.body


def test_lapsed_hard_uses_days_and_focus():
    result = _compose("trg_015_winback_rashmi")
    assert "57" in result.body
    assert "weight loss" in result.body.lower()


def test_cde_uses_webinar_not_fluoride():
    result = _compose("trg_022_cde_webinar_dentists")
    assert "webinar" in result.body.lower() or "CDE" in result.body
    assert "fluoride" not in result.body.lower()


def test_category_seasonal_not_festival():
    result = _compose("trg_020_summer_demand_shift")
    assert "ORS" in result.body or "sunscreen" in result.body
    assert "festival" not in result.body.lower()


def test_gbp_unverified_specific():
    result = _compose("trg_021_unverified_gbp_sunrise")
    assert "unverified" in result.body.lower()
    assert "30%" in result.body or "verification" in result.body.lower()
