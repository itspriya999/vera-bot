#!/usr/bin/env python3
"""
Run judge behavioral scenarios WITHOUT an LLM API key.

Use this for local development. For full message scoring, use judge_simulator.py
with an LLM key (OpenAI, Anthropic, Gemini, etc.).
"""
from __future__ import annotations

import os
import sys

# Allow importing from project root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import judge_simulator as js


class NoOpLLM:
    """Stub LLM — scoring steps are skipped; behavioral checks still run."""

    def complete(self, prompt: str, system: str | None = None) -> str:
        return "{}"

    def name(self) -> str:
        return "noop-local"


def main() -> int:
    js.BOT_URL = os.environ.get("BOT_URL", "http://localhost:8080")
    js.TEST_SCENARIO = os.environ.get("TEST_SCENARIO", "all")

    print("\n" + "=" * 60)
    print("  Local Judge (no LLM) — behavioral scenarios only")
    print(f"  Bot: {js.BOT_URL}")
    print("=" * 60 + "\n")

    judge = js.JudgeSimulator(NoOpLLM())
    ok = judge.run(js.TEST_SCENARIO)
    print("\nNote: Message quality scores require judge_simulator.py + LLM_API_KEY")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
