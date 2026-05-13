#!/bin/bash
# Hook: post-tool-batch — auto-collect dashboard data after significant changes
# Triggered after each batch of tool calls completes

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "$0")/../.." && pwd)}"
COLLECTOR="$PROJECT_DIR/scripts/collect-dashboard.py"
DATA_FILE="$PROJECT_DIR/.claude/dashboard-data.json"

# Only run if projects/ has changed in the last minute
if [ -f "$DATA_FILE" ]; then
    LAST_MODIFIED=$(stat -f %m "$DATA_FILE" 2>/dev/null || stat -c %Y "$DATA_FILE" 2>/dev/null)
    NOW=$(date +%s)
    if [ $((NOW - LAST_MODIFIED)) -lt 60 ]; then
        exit 0  # Data is fresh, skip
    fi
fi

if [ -f "$COLLECTOR" ]; then
    python3 "$COLLECTOR" 2>/dev/null || exit 0
fi

exit 0
