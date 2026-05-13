#!/usr/bin/env python3
"""
Sync role models from config/models.json to agent definition files.

Usage:
  python3 scripts/sync-models.py          # sync all agents
  python3 scripts/sync-models.py --dry-run  # preview changes only
"""

import json
import os
import re
import sys
from pathlib import Path

PROJECT_DIR = Path(os.environ.get('CLAUDE_PROJECT_DIR', os.getcwd()))
CONFIG_FILE = PROJECT_DIR / 'config' / 'models.json'
AGENTS_DIR = PROJECT_DIR / 'agents'

# Map role names to agent filenames
ROLE_TO_AGENT = {
    'architect': 'architect.md',
    'cto': 'cto.md',
    'pm': 'pm.md',
    'tech-lead': 'tech-lead.md',
    'designer': 'designer.md',
    'reviewer-r1': 'reviewer-r1.md',
    'reviewer-r2': 'reviewer-r2.md',
    'reviewer-r3': 'reviewer-r3.md',
    'senior-engineer': 'senior-engineer.md',
    'devops': 'devops.md',
    'market-manager': 'market-manager.md',
}


def sync(dry_run: bool = False):
    if not CONFIG_FILE.exists():
        print(f"Config file not found: {CONFIG_FILE}")
        sys.exit(1)

    config = json.loads(CONFIG_FILE.read_text())
    roles = config.get('roles', {})
    available = config.get('_models_available', ['opus', 'sonnet', 'haiku', 'inherit'])
    changes = []

    for role, model in roles.items():
        if role not in ROLE_TO_AGENT:
            print(f"  ⚠ Unknown role: {role} (no matching agent file)")
            continue
        if model not in available:
            print(f"  ⚠ Invalid model for {role}: {model} (must be one of {available})")
            continue

        agent_file = AGENTS_DIR / ROLE_TO_AGENT[role]
        if not agent_file.exists():
            print(f"  ⚠ Agent file not found: {agent_file}")
            continue

        content = agent_file.read_text()
        old_model = None
        m = re.search(r'^model:\s*(\S+)', content, re.MULTILINE)
        if m:
            old_model = m.group(1)

        if old_model == model:
            continue

        if dry_run:
            changes.append(f"  {role}: {old_model} → {model} (dry-run)")
        else:
            new_content = re.sub(
                r'^model:\s*\S+',
                f'model: {model}',
                content,
                flags=re.MULTILINE
            )
            agent_file.write_text(new_content)
            changes.append(f"  {role}: {old_model} → {model}")

    if changes:
        label = "Would change" if dry_run else "Synced"
        print(f"{label} {len(changes)} agent(s):")
        for c in changes:
            print(c)
    else:
        print("All agents already up to date.")


if __name__ == '__main__':
    dry_run = '--dry-run' in sys.argv
    sync(dry_run=dry_run)
