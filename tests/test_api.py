import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.state import BotState
from app.main import app

ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT / "dataset"


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture(autouse=True)
def reset_state():
    from app.core.state import bot_state

    bot_state.teardown()
    yield
    bot_state.teardown()


def load_json(path: Path):
    return json.loads(path.read_text())


def test_healthz(client):
    r = client.get("/v1/healthz")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    assert "uptime_seconds" in data
    assert data["contexts_loaded"]["category"] == 0


def test_metadata(client):
    r = client.get("/v1/metadata")
    assert r.status_code == 200
    data = r.json()
    assert "team_name" in data
    assert "model" in data
    assert "approach" in data


def test_context_idempotent(client):
    payload = load_json(DATASET / "categories" / "dentists.json")
    body = {
        "scope": "category",
        "context_id": "dentists",
        "version": 1,
        "payload": payload,
        "delivered_at": "2026-04-26T10:00:00Z",
    }
    r1 = client.post("/v1/context", json=body)
    assert r1.status_code == 200
    assert r1.json()["accepted"] is True

    r2 = client.post("/v1/context", json=body)
    assert r2.json()["accepted"] is False
    assert r2.json()["reason"] == "stale_version"


def test_context_version_bump(client):
    payload = load_json(DATASET / "categories" / "dentists.json")
    base = {
        "scope": "category",
        "context_id": "dentists",
        "payload": payload,
        "delivered_at": "2026-04-26T10:00:00Z",
    }
    client.post("/v1/context", json={**base, "version": 1})
    r = client.post("/v1/context", json={**base, "version": 2})
    assert r.json()["accepted"] is True


def test_tick_empty(client):
    r = client.post("/v1/tick", json={"now": "2026-04-26T10:30:00Z", "available_triggers": []})
    assert r.status_code == 200
    assert r.json()["actions"] == []


def test_tick_research_digest(client):
    cat = load_json(DATASET / "categories" / "dentists.json")
    merchants = load_json(DATASET / "merchants_seed.json")["merchants"]
    merchant = merchants[0]
    triggers = load_json(DATASET / "triggers_seed.json")["triggers"]
    trigger = triggers[0]

    client.post("/v1/context", json={"scope": "category", "context_id": "dentists", "version": 1, "payload": cat, "delivered_at": "2026-04-26T10:00:00Z"})
    client.post("/v1/context", json={"scope": "merchant", "context_id": merchant["merchant_id"], "version": 1, "payload": merchant, "delivered_at": "2026-04-26T10:00:00Z"})
    client.post("/v1/context", json={"scope": "trigger", "context_id": trigger["id"], "version": 1, "payload": trigger, "delivered_at": "2026-04-26T10:00:00Z"})

    r = client.post("/v1/tick", json={"now": "2026-04-26T10:35:00Z", "available_triggers": [trigger["id"]]})
    assert r.status_code == 200
    actions = r.json()["actions"]
    assert len(actions) == 1
    action = actions[0]
    assert action["merchant_id"] == merchant["merchant_id"]
    assert action["send_as"] == "vera"
    assert "JIDA" in action["body"] or "fluoride" in action["body"].lower()
    assert action["suppression_key"]
    assert action["rationale"]


def test_reply_hostile(client):
    r = client.post(
        "/v1/reply",
        json={
            "conversation_id": "conv_test",
            "merchant_id": "m_001",
            "from_role": "merchant",
            "message": "Stop messaging me. This is useless spam.",
            "received_at": "2026-04-26T10:45:00Z",
            "turn_number": 2,
        },
    )
    assert r.status_code == 200
    assert r.json()["action"] == "end"


def test_reply_commitment(client):
    r = client.post(
        "/v1/reply",
        json={
            "conversation_id": "conv_intent",
            "merchant_id": "m_001",
            "from_role": "merchant",
            "message": "Ok lets do it. Whats next?",
            "received_at": "2026-04-26T10:45:00Z",
            "turn_number": 2,
        },
    )
    data = r.json()
    assert data["action"] == "send"
    body = data.get("body", "").lower()
    assert "draft" in body or "done" in body or "confirm" in body
    assert "would you" not in body


def test_reply_auto_reply(client):
    r = client.post(
        "/v1/reply",
        json={
            "conversation_id": "conv_auto",
            "merchant_id": "m_001",
            "from_role": "merchant",
            "message": "Thank you for contacting us! Our team will respond shortly.",
            "received_at": "2026-04-26T10:45:00Z",
            "turn_number": 2,
        },
    )
    data = r.json()
    assert data["action"] in ("wait", "end", "send")
    if data["action"] == "wait":
        assert data["wait_seconds"] >= 1800


def test_reply_varies_by_message(client):
    payloads = [
        "why are you repeating the messages",
        "whatis the current price",
        "tell me about my customers",
    ]
    bodies = []
    for i, message in enumerate(payloads):
        r = client.post(
            "/v1/reply",
            json={
                "conversation_id": f"conv_var_{i}",
                "merchant_id": "m_001_drmeera_dentist_delhi",
                "from_role": "merchant",
                "message": message,
                "received_at": "2026-04-26T10:45:00Z",
                "turn_number": 2,
            },
        )
        assert r.status_code == 200
        assert r.json()["action"] == "send"
        bodies.append(r.json()["body"])

    assert len(set(bodies)) == 3
    assert "repeat" in bodies[0].lower() or "won't repeat" in bodies[0].lower()
    assert "\\\"" not in bodies[1]
    assert "catalog" in bodies[1].lower() or "offer" in bodies[1].lower()
    assert "customer" in bodies[2].lower()


def test_reply_pricing_uses_merchant_offers(client):
    merchant = load_json(DATASET / "merchants_seed.json")["merchants"][0]
    client.post(
        "/v1/context",
        json={
            "scope": "merchant",
            "context_id": merchant["merchant_id"],
            "version": 1,
            "payload": merchant,
            "delivered_at": "2026-04-26T10:00:00Z",
        },
    )
    r = client.post(
        "/v1/reply",
        json={
            "conversation_id": "conv_price",
            "merchant_id": merchant["merchant_id"],
            "from_role": "merchant",
            "message": "whatis the current price",
            "received_at": "2026-04-26T10:45:00Z",
            "turn_number": 2,
        },
    )
    body = r.json()["body"]
    assert "Dental Cleaning @ ₹299" in body
    assert "whatis" not in body.lower()


def test_determinism(client):
    from app.core.state import bot_state

    cat = load_json(DATASET / "categories" / "dentists.json")
    merchants = load_json(DATASET / "merchants_seed.json")["merchants"]
    merchant = merchants[0]
    triggers = load_json(DATASET / "triggers_seed.json")["triggers"]
    trigger = triggers[0]

    bodies = []
    for _ in range(2):
        bot_state.teardown()
        client.post("/v1/context", json={"scope": "category", "context_id": "dentists", "version": 1, "payload": cat, "delivered_at": "2026-04-26T10:00:00Z"})
        client.post("/v1/context", json={"scope": "merchant", "context_id": merchant["merchant_id"], "version": 1, "payload": merchant, "delivered_at": "2026-04-26T10:00:00Z"})
        client.post("/v1/context", json={"scope": "trigger", "context_id": trigger["id"], "version": 1, "payload": trigger, "delivered_at": "2026-04-26T10:00:00Z"})
        r = client.post("/v1/tick", json={"now": "2026-04-26T10:35:00Z", "available_triggers": [trigger["id"]]})
        bodies.append(r.json()["actions"][0]["body"])

    assert bodies[0] == bodies[1]
