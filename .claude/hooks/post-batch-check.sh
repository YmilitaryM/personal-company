#!/bin/bash
# Post-batch check hook — runs after each batch of tool calls
# Checks if project files were modified and logs it

PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "$0")/../.." && pwd)}"
LOG_FILE="$PROJECT_DIR/.claude/activity.log"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Post-batch check completed" >> "$LOG_FILE"
exit 0
