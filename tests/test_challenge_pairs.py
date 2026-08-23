import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app

ROOT = Path(__file__).resolve().parents[1]
EXPANDED = ROOT / "expanded"


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture(autouse=True)
def reset_state():
    from app.core.state import bot_state

    bot_state.teardown()
    yield
    bot_state.teardown()


def _push_all(client: TestClient):
    for cat in (EXPANDED / "categories").glob("*.json"):
        data = json.loads(cat.read_text())
        client.post(
            "/v1/context",
            json={
                "scope": "category",
                "context_id": data["slug"],
                "version": 1,
                "payload": data,
                "delivered_at": "2026-04-26T10:00:00Z",
            },
        )
    for m in (EXPANDED / "merchants").glob("*.json"):
        data = json.loads(m.read_text())
        client.post(
            "/v1/context",
            json={
                "scope": "merchant",
                "context_id": data["merchant_id"],
                "version": 1,
                "payload": data,
                "delivered_at": "2026-04-26T10:00:00Z",
            },
        )
    for c in (EXPANDED / "customers").glob("*.json"):
        data = json.loads(c.read_text())
        client.post(
            "/v1/context",
            json={
                "scope": "customer",
                "context_id": data["customer_id"],
                "version": 1,
                "payload": data,
                "delivered_at": "2026-04-26T10:00:00Z",
            },
        )


@pytest.mark.skipif(not EXPANDED.exists(), reason="expanded dataset not generated")
def test_all_30_canonical_pairs(client):
    pairs = json.loads((EXPANDED / "test_pairs.json").read_text())["pairs"]
    _push_all(client)

    ok = 0
    for pair in pairs:
        trigger_id = pair["trigger_id"]
        trigger = json.loads((EXPANDED / "triggers" / f"{trigger_id}.json").read_text())
        client.post(
            "/v1/context",
            json={
                "scope": "trigger",
                "context_id": trigger_id,
                "version": 1,
                "payload": trigger,
                "delivered_at": "2026-04-26T10:30:00Z",
            },
        )
        r = client.post(
            "/v1/tick",
            json={"now": "2026-04-26T10:35:00Z", "available_triggers": [trigger_id]},
        )
        actions = r.json()["actions"]
        if actions and actions[0]["body"]:
            ok += 1

    assert ok >= 28, f"Only {ok}/30 pairs produced messages"
