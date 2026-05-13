#!/usr/bin/env python3
"""
Automated Report Generator — Daily standup, weekly status, sprint retro.

Usage:
  python3 reports.py standup [project]
  python3 reports.py weekly
  python3 reports.py sprint-retro <project> <sprint-num>
"""

import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

PROJECT_DIR = Path(os.environ.get('CLAUDE_PROJECT_DIR', os.getcwd()))
PROJECTS_DIR = PROJECT_DIR / 'projects'
INDEX_FILE = PROJECTS_DIR / '.index.json'


def _load_index():
    if INDEX_FILE.exists():
        return json.loads(INDEX_FILE.read_text())
    return {'projects': {}}


def generate_standup(project_name: str = None) -> str:
    """Generate daily standup reports."""
    index = _load_index()
    today = datetime.now().strftime('%Y-%m-%d')

    lines = [
        f"# 🤙 每日站会 — {today}",
        "",
    ]

    projects = index.get('projects', {})
    target = {project_name: projects[project_name]} if project_name and project_name in projects else projects

    if not target:
        lines.append("(暂无活跃项目)")
        return '\n'.join(lines)

    for pname, pdata in target.items():
        progress = pdata.get('overall_progress', 0)
        status_icon = pdata.get('status', '🟢').replace('🟢正常', '🟢').replace('🟡有风险', '🟡').replace('🔴严重延迟', '🔴')

        lines.append(f"## {status_icon} {pname} (进度: {progress}%)")
        lines.append(f"**阶段**: {pdata.get('phase', '—')} | **TL**: {pdata.get('tech_lead', '—')}")

        # Yesterday
        this_week = pdata.get('this_week_done', [])
        lines.append(f"\n### 昨日完成")
        if this_week:
            for item in this_week[-3:]:  # last 3 items
                lines.append(f"- ✅ {item}")
        else:
            lines.append("- (无记录)")

        # Today
        in_progress_tasks = [t for t in pdata.get('tasks', []) if t.get('status') == 'in_progress']
        lines.append(f"\n### 今日进行中 ({len(in_progress_tasks)})")
        for t in in_progress_tasks:
            lines.append(f"- 🟡 [{t.get('priority', '—')}] {t.get('title', '—')} — {t.get('assignee', '—')}")

        # Blockers
        blockers = pdata.get('blockers', [])
        if blockers:
            lines.append(f"\n### ⚠️ 阻塞项 ({len(blockers)})")
            for b in blockers:
                lines.append(f"- 🔴 {b}")
        else:
            lines.append(f"\n### ⚠️ 阻塞项: 无")

        lines.append("")

    lines.append("---")
    lines.append(f"*报告生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}*")

    return '\n'.join(lines)


def generate_weekly() -> str:
    """Generate weekly status report."""
    index = _load_index()
    today = datetime.now()
    week_start = (today - timedelta(days=today.weekday())).strftime('%Y-%m-%d')
    week_end = (today + timedelta(days=6 - today.weekday())).strftime('%Y-%m-%d')

    projects = index.get('projects', {})
    total_done = 0
    total_blocked = 0

    lines = [
        f"# 📋 周报 — {week_start} ~ {week_end}",
        "",
        "## 项目状态总览",
        "",
        "| 项目 | 方向 | 进度 | 阶段 | 状态 | 本周完成 | 阻塞 |",
        "|------|------|------|------|------|----------|------|",
    ]

    for pname, pdata in projects.items():
        progress = pdata.get('overall_progress', 0)
        done_count = len([t for t in pdata.get('tasks', []) if t.get('status') == 'done'])
        blocked_count = len(pdata.get('blockers', []))
        total_done += done_count
        total_blocked += blocked_count

        lines.append(
            f"| {pname} | {pdata.get('direction', '—')} | {progress}% | "
            f"{pdata.get('phase', '—')} | {pdata.get('status', '🟢')} | "
            f"{done_count} | {blocked_count} |"
        )

    lines.append("")
    lines.append("## 本周统计")
    lines.append(f"- 完成任务: {total_done}")
    lines.append(f"- 阻塞项: {total_blocked}")
    lines.append(f"- 活跃项目: {len(projects)}")

    # At-risk projects
    at_risk = [n for n, p in projects.items() if '🔴' in p.get('status', '') or '延迟' in p.get('status', '')]
    if at_risk:
        lines.append(f"- ⚠️ 风险项目: {', '.join(at_risk)}")

    lines.append("")
    lines.append("## 下周重点")
    for pname, pdata in projects.items():
        plans = pdata.get('next_week_plan', [])
        if plans:
            lines.append(f"### {pname}")
            for plan in plans[:3]:
                lines.append(f"- [ ] {plan}")

    lines.append("")
    lines.append("---")
    lines.append(f"*报告生成: {today.strftime('%Y-%m-%d %H:%M')}*")

    return '\n'.join(lines)


def generate_sprint_retro(project_name: str, sprint_num: int) -> str:
    """Generate sprint retrospective template."""
    sprints_dir = PROJECTS_DIR / project_name / '.sprints'
    sprint_file = sprints_dir / f'sprint-{sprint_num:02d}.json'

    sprint_data = {}
    if sprint_file.exists():
        sprint_data = json.loads(sprint_file.read_text())

    lines = [
        f"# 🔄 Sprint {sprint_num} Retro — {project_name}",
        f"**日期**: {datetime.now().strftime('%Y-%m-%d')}",
        f"**Sprint目标**: {sprint_data.get('goal', '—')}",
        f"**完成点数**: {sprint_data.get('completed_points', 0)} / {sprint_data.get('total_points', 0)}",
        "",
        "## ✅ 做得好 (Keep Doing)",
        "1. ",
        "2. ",
        "3. ",
        "",
        "## ⚠️ 待改进 (Start Doing)",
        "1. ",
        "2. ",
        "3. ",
        "",
        "## ❌ 停止做 (Stop Doing)",
        "1. ",
        "2. ",
        "",
        "## 📈 数据",
        f"- 计划点数: {sprint_data.get('total_points', '—')}",
        f"- 完成点数: {sprint_data.get('completed_points', '—')}",
        f"- 达成率: {round(sprint_data.get('completed_points', 0) / max(sprint_data.get('total_points', 1), 1) * 100)}%",
        f"- 速率: {sprint_data.get('velocity', '—')} pts/sprint",
        "",
        "## 🎯 下个Sprint目标",
        "...",
        "",
        "## 🏃 行动项",
        "| 序号 | 行动 | 负责人 | 截止 |",
        "|------|------|--------|------|",
        "| 1 | | | |",
        "| 2 | | | |",
    ]

    return '\n'.join(lines)


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: reports.py <standup|weekly|sprint-retro> [args...]")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == 'standup':
        project = sys.argv[2] if len(sys.argv) > 2 else None
        print(generate_standup(project))

    elif cmd == 'weekly':
        print(generate_weekly())

    elif cmd == 'sprint-retro':
        if len(sys.argv) < 4:
            print("Usage: reports.py sprint-retro <project> <sprint-num>")
            sys.exit(1)
        print(generate_sprint_retro(sys.argv[2], int(sys.argv[3])))

    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)
