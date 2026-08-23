from __future__ import annotations

import threading
import time
from typing import Any, Optional

from app.models.schemas import ConversationState, ConversationTurn


class BotState:
    """Thread-safe in-memory state for the challenge harness."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._start = time.time()
        self._contexts: dict[tuple[str, str], dict[str, Any]] = {}
        self._conversations: dict[str, ConversationState] = {}
        self._suppression_keys: set[str] = set()
        self._ended_conversations: set[str] = set()
        self._sent_bodies: dict[str, set[str]] = {}
        self._merchant_auto_replies: dict[str, dict[str, int]] = {}
        self._metrics = {
            "requests": 0,
            "errors": 0,
            "messages_generated": 0,
            "suppressed_messages": 0,
        }

    @property
    def uptime_seconds(self) -> int:
        return int(time.time() - self._start)

    def increment(self, key: str, amount: int = 1) -> None:
        with self._lock:
            self._metrics[key] = self._metrics.get(key, 0) + amount

    def metrics_snapshot(self) -> dict[str, int]:
        with self._lock:
            return dict(self._metrics)

    def context_counts(self) -> dict[str, int]:
        counts = {"category": 0, "merchant": 0, "customer": 0, "trigger": 0}
        with self._lock:
            for (scope, _), _ in self._contexts.items():
                if scope in counts:
                    counts[scope] += 1
        return counts

    def get_context(self, scope: str, context_id: str) -> Optional[dict[str, Any]]:
        with self._lock:
            entry = self._contexts.get((scope, context_id))
            return entry["payload"] if entry else None

    def get_context_version(self, scope: str, context_id: str) -> Optional[int]:
        with self._lock:
            entry = self._contexts.get((scope, context_id))
            return entry["version"] if entry else None

    def store_context(
        self, scope: str, context_id: str, version: int, payload: dict[str, Any]
    ) -> tuple[bool, Optional[str], Optional[int]]:
        with self._lock:
            key = (scope, context_id)
            current = self._contexts.get(key)
            if current and current["version"] >= version:
                return False, "stale_version", current["version"]
            self._contexts[key] = {"version": version, "payload": payload}
            return True, None, None

    def list_triggers(self) -> dict[str, dict[str, Any]]:
        with self._lock:
            return {
                cid: entry["payload"]
                for (scope, cid), entry in self._contexts.items()
                if scope == "trigger"
            }

    def is_suppressed(self, key: str) -> bool:
        with self._lock:
            return key in self._suppression_keys

    def mark_suppressed(self, key: str) -> None:
        with self._lock:
            self._suppression_keys.add(key)

    def is_conversation_ended(self, conversation_id: str) -> bool:
        with self._lock:
            return conversation_id in self._ended_conversations

    def end_conversation(self, conversation_id: str) -> None:
        with self._lock:
            self._ended_conversations.add(conversation_id)
            if conversation_id in self._conversations:
                self._conversations[conversation_id].ended = True

    def body_already_sent(self, conversation_id: str, body: str) -> bool:
        with self._lock:
            bodies = self._sent_bodies.setdefault(conversation_id, set())
            normalized = body.strip().lower()
            if normalized in bodies:
                return True
            bodies.add(normalized)
            return False

    def get_conversation(self, conversation_id: str) -> Optional[ConversationState]:
        with self._lock:
            return self._conversations.get(conversation_id)

    def save_conversation(self, state: ConversationState) -> None:
        with self._lock:
            self._conversations[state.conversation_id] = state

    def append_turn(self, conversation_id: str, turn: ConversationTurn) -> ConversationState:
        with self._lock:
            state = self._conversations.setdefault(
                conversation_id,
                ConversationState(conversation_id=conversation_id),
            )
            state.turns.append(turn)
            return state

    def record_outbound(
        self,
        conversation_id: str,
        body: str,
        merchant_id: str,
        customer_id: Optional[str],
        trigger_id: str,
        send_as: str,
        suppression_key: str,
    ) -> None:
        with self._lock:
            state = self._conversations.setdefault(
                conversation_id,
                ConversationState(conversation_id=conversation_id),
            )
            state.last_bot_body = body
            state.merchant_id = merchant_id
            state.customer_id = customer_id
            state.trigger_id = trigger_id
            state.send_as = send_as  # type: ignore[assignment]
            state.last_suppression_key = suppression_key
            self._sent_bodies.setdefault(conversation_id, set()).add(body.strip().lower())
            self._metrics["messages_generated"] = self._metrics.get("messages_generated", 0) + 1

    def record_auto_reply(self, merchant_id: str, message: str) -> int:
        normalized = message.strip().lower()
        with self._lock:
            counts = self._merchant_auto_replies.setdefault(merchant_id, {})
            counts[normalized] = counts.get(normalized, 0) + 1
            return counts[normalized]

    def teardown(self) -> None:
        with self._lock:
            self._contexts.clear()
            self._conversations.clear()
            self._suppression_keys.clear()
            self._ended_conversations.clear()
            self._sent_bodies.clear()
            self._merchant_auto_replies.clear()


bot_state = BotState()
