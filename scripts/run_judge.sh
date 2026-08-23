#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

export BOT_URL="${BOT_URL:-http://localhost:8080}"

if [[ -f "$ROOT/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$ROOT/.env"
  set +a
fi

if ! curl -sf "$BOT_URL/v1/healthz" >/dev/null 2>&1; then
  echo "Bot not reachable at $BOT_URL"
  echo "Start it first in another terminal:"
  echo "  source .venv/bin/activate && python main.py"
  exit 1
fi

# Full judge with LLM scoring (needs API key in judge_simulator.py or env)
if [[ -n "${LLM_API_KEY:-}" ]] || grep -q 'LLM_API_KEY = "[^"][^"]' judge_simulator.py 2>/dev/null; then
  python3 judge_simulator.py
else
  echo "No LLM_API_KEY set — running behavioral scenarios only (no message scores)."
  echo "For full scoring, set LLM_API_KEY or edit judge_simulator.py CONFIGURATION section."
  echo ""
  python3 scripts/run_judge_local.py
fi
