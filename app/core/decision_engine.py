from __future__ import annotations

from app.core.composer import compose, to_tick_action
from app.core.scoring import rank_triggers
from app.core.state import BotState
from app.models.schemas import TickAction


MAX_ACTIONS_PER_TICK = 20


class DecisionEngine:
    def __init__(self, state: BotState) -> None:
        self.state = state

    def _load_maps(self) -> tuple[dict, dict]:
        merchants: dict = {}
        categories: dict = {}
        with self.state._lock:
            for (scope, cid), entry in self.state._contexts.items():
                if scope == "merchant":
                    merchants[cid] = entry["payload"]
                elif scope == "category":
                    categories[cid] = entry["payload"]
        return merchants, categories

    def decide_tick_actions(self, now_iso: str, available_triggers: list[str]) -> list[TickAction]:
        merchants, categories = self._load_maps()
        trigger_items: list[tuple[str, dict]] = []
        for tid in available_triggers:
            trg = self.state.get_context("trigger", tid)
            if trg:
                trigger_items.append((tid, trg))

        ranked = rank_triggers(
            trigger_items,
            merchants,
            categories,
            now_iso,
            self.state.is_suppressed,
        )

        actions: list[TickAction] = []
        seen_merchants: set[str] = set()

        for trigger_id, _trigger, _score in ranked:
            if len(actions) >= MAX_ACTIONS_PER_TICK:
                break

            msg = compose(self.state, trigger_id, now_iso)
            if not msg:
                continue

            if msg.merchant_id in seen_merchants:
                continue

            seen_merchants.add(msg.merchant_id)
            action = to_tick_action(msg)
            actions.append(action)

            self.state.record_outbound(
                msg.conversation_id,
                msg.body,
                msg.merchant_id,
                msg.customer_id,
                msg.trigger_id,
                msg.send_as,
                msg.suppression_key,
            )
            self.state.mark_suppressed(msg.suppression_key)

        return actions
