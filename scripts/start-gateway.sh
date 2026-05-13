#!/usr/bin/env bash
# Start the Multi-Provider Model Gateway for Claude Code
# Usage: bash scripts/start-gateway.sh [port]
#
# Routes Anthropic-format requests to different backends based on model name.
# Model→provider mapping defined in config/litellm.yaml
# API keys loaded from .env (copy from config/.env.example)

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
PORT="${1:-4000}"

# ── Load .env if present ──
if [ -f "$PROJECT_DIR/.env" ]; then
  set -a
  source "$PROJECT_DIR/.env"
  set +a
fi

# ── Check critical env vars ──
missing=""
[ -z "$DEEPSEEK_API_KEY" ] && [ -z "$OPENAI_API_KEY" ] && [ -z "$ANTHROPIC_API_KEY" ] && missing="yes"

if [ -n "$missing" ]; then
  echo "⚠ No API keys found. Create a .env file:"
  echo "    cp config/.env.example .env"
  echo "    # edit .env with your API keys"
  echo ""
fi

echo "Starting Model Gateway on port $PORT..."
echo "Claude Code env: ANTHROPIC_BASE_URL=http://localhost:$PORT"
echo ""

python3.14 "$PROJECT_DIR/scripts/model-gateway.py" --port "$PORT"
