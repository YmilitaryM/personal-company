#!/usr/bin/env python3
"""
Analytics Engine — Quality trends, cycle time, predictive alerts.

Usage:
  python3 analytics.py [--project <name>] [--alert]
"""

import fcntl
import json
import os
import sys
import time
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path

PROJECT_DIR = Path(os.environ.get('CLAUDE_PROJECT_DIR', os.getcwd()))
PROJECTS_DIR = PROJECT_DIR / 'projects'
INDEX_FILE = PROJECTS_DIR / '.index.json'
ALERTS_FILE = PROJECT_DIR / '.claude' / 'alerts.json'
ALERTS_LOCK = PROJECT_DIR / '.claude' / '.alerts.lock'


@contextmanager
def _file_lock(lock_path):
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    fd = open(lock_path, 'w')
    deadline = time.time() + 5
    while True:
        try:
            fcntl.flock(fd.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            break
        except BlockingIOError:
            if time.time() > deadline:
                fd.close()
                raise TimeoutError('Could not acquire alerts lock')
            time.sleep(0.05)
    try:
        yield
    finally:
        fcntl.flock(fd.fileno(), fcntl.LOCK_UN)
        fd.close()


# ─── Core Analytics ───

def calculate_quality(project_name: str = None) -> dict:
    """Calculate quality metrics from review scores and bugs."""
    index = _load_index()
    projects = index.get('projects', {})

    quality = {}
    target = [project_name] if project_name else projects.keys()

    for pname in target:
        pdata = projects.get(pname, {})
        reviews = pdata.get('reviews', {})

        scores = []
        for gate_data in reviews.values():
            for r in ['R1', 'R2', 'R3']:
                s = gate_data.get(r, {}).get('score')
                if s:
                    scores.append(s)

        tasks = pdata.get('tasks', [])
        done = sum(1 for t in tasks if t.get('status') == 'done')
        total = len(tasks)

        quality[pname] = {
            'avg_review_score': sum(scores) / max(len(scores), 1),
            'total_reviews': len(scores),
            'gates_passed': sum(
                1 for g in ['DG1', 'DG2', 'DG3', 'DG4']
                if _gate_passed(reviews.get(g, {}))
            ),
            'completion_rate': (done / max(total, 1)) * 100,
            'score_trend': _score_trend(scores),
        }

    return quality


def calculate_cycle_time(project_name: str = None) -> dict:
    """Calculate average cycle time from task creation to completion."""
    index = _load_index()
    projects = index.get('projects', {})

    cycles = {}
    target = [project_name] if project_name else projects.keys()

    for pname in target:
        pdata = projects.get(pname, {})
        tasks = pdata.get('tasks', [])
        done_tasks = [t for t in tasks if t.get('status') == 'done']

        if done_tasks:
            times = []
            for t in done_tasks:
                created = t.get('created_at', '')
                updated = t.get('updated_at', '')
                if created and updated:
                    try:
                        c = datetime.fromisoformat(created)
                        u = datetime.fromisoformat(updated)
                        times.append((u - c).total_seconds() / 3600)  # hours
                    except ValueError:
                        pass

            if times:
                cycles[pname] = {
                    'avg_cycle_hours': sum(times) / len(times),
                    'median_cycle_hours': sorted(times)[len(times) // 2],
                    'fastest_hours': min(times),
                    'slowest_hours': max(times),
                }
            else:
                cycles[pname] = {'avg_cycle_hours': 0}
        else:
            cycles[pname] = {'avg_cycle_hours': 0, 'note': 'No completed tasks yet'}

    return cycles


def calculate_team_health() -> dict:
    """Calculate overall project health metrics."""
    index = _load_index()
    projects = index.get('projects', {})

    # Project health
    total = len(projects)
    at_risk = sum(1 for p in projects.values() if '🔴' in p.get('status', ''))
    delayed = sum(1 for p in projects.values() if '延迟' in p.get('status', ''))
    blocked = sum(len(p.get('blockers', [])) for p in projects.values())

    return {
        'projects': {
            'total': total,
            'at_risk': at_risk,
            'delayed': delayed,
            'total_blockers': blocked,
        },
    }


# ─── Predictive Alerts ───

def check_alerts() -> list:
    """Generate alerts for risks that need attention."""
    alerts = []
    today = datetime.now()

    index = _load_index()
    projects = index.get('projects', {})

    for pname, pdata in projects.items():
        # Deadline alert
        target = pdata.get('target_date', '')
        if target:
            try:
                dt = datetime.strptime(target, '%Y-%m-%d')
                days_left = (dt - today).days
                if days_left < 0:
                    alerts.append({
                        'project': pname,
                        'type': 'deadline',
                        'severity': 'critical',
                        'message': f'交付超期 {-days_left} 天',
                        'date': today.strftime('%Y-%m-%d'),
                    })
                elif days_left <= 3 and pdata.get('overall_progress', 0) < 80:
                    alerts.append({
                        'project': pname,
                        'type': 'deadline',
                        'severity': 'high',
                        'message': f'仅剩 {days_left} 天，进度 {pdata["overall_progress"]}%',
                        'date': today.strftime('%Y-%m-%d'),
                    })
                elif days_left <= 7 and pdata.get('overall_progress', 0) < 60:
                    alerts.append({
                        'project': pname,
                        'type': 'deadline',
                        'severity': 'medium',
                        'message': f'仅剩 {days_left} 天，进度 {pdata["overall_progress"]}%',
                        'date': today.strftime('%Y-%m-%d'),
                    })
            except ValueError:
                pass

        # Stale status alert
        updated = pdata.get('updated_at', '')
        if updated:
            try:
                dt = datetime.fromisoformat(updated)
                if (today - dt).days > 3:
                    alerts.append({
                        'project': pname,
                        'type': 'stale',
                        'severity': 'low',
                        'message': f'状态 { (today - dt).days } 天未更新',
                        'date': today.strftime('%Y-%m-%d'),
                    })
            except ValueError:
                pass

        # Blocker alert
        blockers = pdata.get('blockers', [])
        if blockers:
            alerts.append({
                'project': pname,
                'type': 'blocker',
                'severity': 'high' if len(blockers) > 2 else 'medium',
                'message': f'{len(blockers)} 个阻塞项',
                'date': today.strftime('%Y-%m-%d'),
            })

        # Review gate stuck alert
        phase = pdata.get('phase', '')
        expected_gate = {'方案设计': 'DG1', '开发实现': 'DG2', '测试评审': 'DG3', '交付验收': 'DG4'}.get(phase)
        if expected_gate:
            gate_data = pdata.get('reviews', {}).get(expected_gate, {})
            if not gate_data:
                alerts.append({
                    'project': pname,
                    'type': 'gate_missing',
                    'severity': 'high',
                    'message': f'{expected_gate} 评审未触发，当前阶段: {phase}',
                    'date': today.strftime('%Y-%m-%d'),
                })

    # Save alerts (deduplicate within same day)
    with _file_lock(ALERTS_LOCK):
        ALERTS_FILE.parent.mkdir(parents=True, exist_ok=True)
        existing = []
        if ALERTS_FILE.exists():
            existing = json.loads(ALERTS_FILE.read_text())
        existing = [a for a in existing if a['date'] >= (today - timedelta(days=7)).strftime('%Y-%m-%d')]
        seen = {(a['project'], a['type'], a['date']) for a in existing}
        for alert in alerts:
            key = (alert['project'], alert['type'], alert['date'])
            if key not in seen:
                seen.add(key)
                existing.append(alert)
        ALERTS_FILE.write_text(json.dumps(existing, ensure_ascii=False, indent=2))

    return alerts


# ─── Helpers ───

def _load_index() -> dict:
    if INDEX_FILE.exists():
        return json.loads(INDEX_FILE.read_text())
    return {'projects': {}, 'team': {}}


def _gate_passed(gate_data: dict) -> bool:
    votes = [gate_data.get(r, {}).get('vote') for r in ['R1', 'R2', 'R3']]
    return votes.count('approve') >= 2


def _score_trend(scores: list) -> str:
    if len(scores) < 3:
        return 'insufficient_data'
    recent_avg = sum(scores[-3:]) / 3
    earlier_avg = sum(scores[:3]) / 3 if len(scores) >= 6 else sum(scores[:-3]) / max(len(scores[:-3]), 1)
    if recent_avg > earlier_avg + 1:
        return 'improving'
    elif recent_avg < earlier_avg - 1:
        return 'declining'
    return 'stable'


# ─── Main ───

if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='AI Team Analytics Engine')
    parser.add_argument('--project', type=str, help='Specific project name')
    parser.add_argument('--alert', action='store_true', help='Run alert checks')
    parser.add_argument('--quality', action='store_true', help='Show quality metrics')
    parser.add_argument('--cycle', action='store_true', help='Show cycle time metrics')
    parser.add_argument('--health', action='store_true', help='Show project health')
    parser.add_argument('--all', action='store_true', help='Show all metrics')

    args = parser.parse_args()

    if args.alert or args.all:
        alerts = check_alerts()
        print('\n=== 智能预警 ===')
        for a in alerts:
            sev = {'critical': '🔴', 'high': '🟠', 'medium': '🟡', 'low': '⚪'}.get(a['severity'], '—')
            print(f"{sev} [{a['type']}] {a['project']}: {a['message']}")
        if not alerts:
            print('✅ 无告警')

    if args.quality or args.all:
        q = calculate_quality(args.project)
        print('\n=== 质量指标 ===')
        for pname, data in q.items():
            print(f"  {pname}: score={data['avg_review_score']:.1f}/10 "
                  f"gates={data['gates_passed']}/4 "
                  f"completion={data['completion_rate']:.0f}% "
                  f"trend={data.get('score_trend', 'N/A')}")

    if args.cycle or args.all:
        c = calculate_cycle_time(args.project)
        print('\n=== 交付周期 ===')
        for pname, data in c.items():
            print(f"  {pname}: avg={data['avg_cycle_hours']:.1f}h "
                  f"median={data.get('median_cycle_hours', 0):.1f}h")

    if args.health or args.all:
        h = calculate_team_health()
        print('\n=== 项目健康 ===')
        print(f"  项目: {h['projects']['total']}总 / {h['projects']['at_risk']}风险 / {h['projects']['delayed']}延迟 / {h['projects']['total_blockers']}阻塞")
