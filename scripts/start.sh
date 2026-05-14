#!/usr/bin/env bash
# AI Dev Team — Start all services
# Usage: bash scripts/start.sh
# Opens: http://localhost:8080 (dashboard) + http://localhost:4000 (gateway)

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="${PROJECT_DIR:-$(dirname "$SCRIPT_DIR")}"

# ── Load .env ──
if [ -f "$PROJECT_DIR/.env" ]; then
  set -a; source "$PROJECT_DIR/.env"; set +a
fi

# ── Ports ──
GW_PORT="${GATEWAY_PORT:-4000}"
WEB_PORT="${WEB_PORT:-8080}"

# ── Check port conflicts ──
check_port() {
  local port=$1
  local name=$2
  if lsof -ti:"$port" &>/dev/null; then
    echo "  ⚠ Port $port is in use ($name)"
    echo "    Set ${3}=<port> to use a different port"
    return 1
  fi
  return 0
}

PORT_OK=1
check_port "$GW_PORT" "Model Gateway" "GATEWAY_PORT" || PORT_OK=0
check_port "$WEB_PORT" "Web Dashboard" "WEB_PORT" || PORT_OK=0
if [ "$PORT_OK" = "0" ]; then
  echo ""
  echo "Tip: Example: WEB_PORT=9090 GATEWAY_PORT=4001 bash scripts/start.sh"
  echo ""
fi

# ── Check deps ──
PYTHON="${PYTHON_CMD:-python3.14}"
if ! command -v "$PYTHON" &>/dev/null; then
  PYTHON="python3"
fi

# ── Check git repo ──
PROJECTS_DIR="$PROJECT_DIR/projects"
if [ ! -d "$PROJECTS_DIR" ]; then
  mkdir -p "$PROJECTS_DIR"
fi
if ! git -C "$PROJECT_DIR" rev-parse --git-dir &>/dev/null; then
  echo "  ⚠ Not a git repository. Initializing..."
  git -C "$PROJECT_DIR" init
fi

# ── Cleanup on exit ──
cleanup() {
  echo ""
  echo "Shutting down..."
  [ -n "$GW_PID" ] && kill "$GW_PID" 2>/dev/null
  [ -n "$WEB_PID" ] && kill "$WEB_PID" 2>/dev/null
  wait 2>/dev/null
  echo "All services stopped."
}
trap cleanup EXIT INT TERM

# ── Start Gateway ──
echo "┌─────────────────────────────────────────┐"
echo "│       AI Dev Team — Starting...          │"
echo "└─────────────────────────────────────────┘"
echo ""

echo "→ Model Gateway (port $GW_PORT)"
if python3 -c "import litellm" 2>/dev/null; then
  "$PYTHON" "$PROJECT_DIR/scripts/model-gateway.py" --port "$GW_PORT" &
  GW_PID=$!
  sleep 1

  if ! kill -0 "$GW_PID" 2>/dev/null; then
    echo "  ⚠ Gateway failed to start (continuing without it)"
    GW_PID=""
  else
    echo "  ✓ Gateway ready"
  fi
else
  echo "  ⚠ LiteLLM not installed — skipping gateway (pip install litellm)"
  GW_PID=""
fi

# ── Start Web Dashboard ──
echo "→ Web Dashboard (port $WEB_PORT)"
"$PYTHON" "$PROJECT_DIR/scripts/web_dashboard.py" --port "$WEB_PORT" --project-dir "$PROJECT_DIR" &
WEB_PID=$!
sleep 1

if ! kill -0 "$WEB_PID" 2>/dev/null; then
  echo "  ✗ Dashboard failed to start"
  exit 1
fi
echo "  ✓ Dashboard ready"

# ── Info ──
echo ""
echo "┌─────────────────────────────────────────┐"
echo "│  Services Running                        │"
echo "├─────────────────────────────────────────┤"
echo "│  Dashboard:  http://localhost:$WEB_PORT       │"
echo "│  Model Config: http://localhost:$WEB_PORT/config │"
if [ -n "$GW_PID" ]; then
  echo "│  Gateway API: http://localhost:$GW_PORT       │"
fi
echo "│                                          │"
echo "│  Claude Code env:                        │"
echo "│  ANTHROPIC_BASE_URL=http://localhost:$GW_PORT │"
echo "└─────────────────────────────────────────┘"
echo ""
echo "Press Ctrl+C to stop all services."

# ── Wait ──
wait
