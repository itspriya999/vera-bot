import json
from pathlib import Path

import pytest

from app.strategies.handlers import compose_message

ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT / "dataset"


def load(path):
    return json.loads(path.read_text())


@pytest.mark.parametrize("trigger_idx", [0, 7, 9, 13, 18])
def test_category_compose(trigger_idx):
    merchants = {m["merchant_id"]: m for m in load(DATASET / "merchants_seed.json")["merchants"]}
    triggers = load(DATASET / "triggers_seed.json")["triggers"]
    trigger = triggers[trigger_idx]
    merchant = merchants[trigger["merchant_id"]]
    category = load(DATASET / "categories" / f"{merchant['category_slug']}.json")

    customers = {c["customer_id"]: c for c in load(DATASET / "customers_seed.json")["customers"]}
    customer = customers.get(trigger.get("customer_id")) if trigger.get("customer_id") else None

    result = compose_message(category, merchant, trigger, customer, trigger["id"])
    assert result.body
    assert len(result.body) > 20
    assert result.rationale
    assert result.suppression_key
    assert result.cta in ("open_ended", "binary_yes_no", "binary_yes_stop", "none")
