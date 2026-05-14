#!/usr/bin/env python3
"""
Dashboard Data Collector
Scans projects/ directory and generates aggregated dashboard data.
Runs via hooks and monitors to keep dashboards fresh.
"""
import os
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

PROJECT_DIR = os.environ.get('CLAUDE_PROJECT_DIR', os.getcwd())
PROJECTS_DIR = Path(PROJECT_DIR) / 'projects'
DATA_FILE = Path(PROJECT_DIR) / '.claude' / 'dashboard-data.json'


def parse_status_file(project_path: Path) -> dict:
    """Parse a project's status.md and extract structured data."""
    status_file = project_path / 'status.md'
    if not status_file.exists():
        return None

    data = {
        'name': project_path.name,
        'direction': 'Unknown',
        'tech_lead': 'Unassigned',
        'team_size': 0,
        'start_date': '',
        'target_date': '',
        'phase': 'Unknown',
        'phase_progress': 0,
        'overall_progress': 0,
        'status': '🟢正常',
        'blockers': [],
        'last_updated': ''
    }

    try:
        content = status_file.read_text(encoding='utf-8')

        for line in content.split('\n'):
            line = line.strip()
            if line.startswith('- 方向:'):
                data['direction'] = line.split(':', 1)[1].strip()
            elif line.startswith('- Tech Lead:'):
                data['tech_lead'] = line.split(':', 1)[1].strip()
            elif line.startswith('- 团队规模:'):
                try:
                    data['team_size'] = int(line.split(':', 1)[1].strip().replace('人', ''))
                except ValueError:
                    pass
            elif line.startswith('- 开始日期:'):
                data['start_date'] = line.split(':', 1)[1].strip()
            elif line.startswith('- 预计交付:'):
                data['target_date'] = line.split(':', 1)[1].strip()
            elif line.startswith('- 阶段:'):
                data['phase'] = line.split(':', 1)[1].strip()
            elif line.startswith('- 阶段进度:'):
                try:
                    data['phase_progress'] = int(line.split(':', 1)[1].strip().replace('%', ''))
                except ValueError:
                    pass
            elif line.startswith('- 完成度:'):
                try:
                    data['overall_progress'] = int(line.split(':', 1)[1].strip().replace('%', ''))
                except ValueError:
                    pass
            elif line.startswith('- 状态:'):
                data['status'] = line.split(':', 1)[1].strip()
            elif line.startswith('- [ ]') or line.startswith('- []'):
                data['blockers'].append(line.split(']', 1)[1].strip() if ']' in line else line[4:].strip())
            elif line.startswith('**最后更新**:'):
                data['last_updated'] = line.replace('**最后更新**:', '').strip()

    except Exception as e:
        data['parse_error'] = str(e)

    return data


def parse_review_files(project_path: Path) -> list:
    """Parse review gate statuses for a project."""
    reviews = []
    reviews_dir = project_path / 'reviews'
    if not reviews_dir.exists():
        return reviews

    for gate in ['dg1', 'dg2', 'dg3', 'dg4']:
        review_file = reviews_dir / f'{gate}.md'
        if review_file.exists():
            content = review_file.read_text(encoding='utf-8')
            review = {
                'gate': gate.upper(),
                'file': f'reviews/{gate}.md',
                'status': '⏳待评审',
                'date': '',
                'r1_vote': '—',
                'r2_vote': '—',
                'r3_vote': '—',
                'result': '—'
            }
            # Parse result
            if '**结果**: ✅ 通过' in content or '✅ PASS' in content:
                review['status'] = '✅通过'
                review['result'] = 'PASS'
            elif '**结果**: 🔄 修改后重审' in content or 'CHANGES REQUIRED' in content:
                review['status'] = '🔄需修改'
                review['result'] = 'CHANGES'
            elif '**结果**: ❌ 驳回' in content or '❌ REJECT' in content:
                review['status'] = '❌驳回'
                review['result'] = 'REJECT'

            # Parse votes
            for line in content.split('\n'):
                if 'R1' in line and ('✅' in line or '🔄' in line or '❌' in line):
                    if '✅' in line: review['r1_vote'] = '✅'
                    elif '🔄' in line: review['r1_vote'] = '🔄'
                    elif '❌' in line: review['r1_vote'] = '❌'
                elif 'R2' in line and ('✅' in line or '🔄' in line or '❌' in line):
                    if '✅' in line: review['r2_vote'] = '✅'
                    elif '🔄' in line: review['r2_vote'] = '🔄'
                    elif '❌' in line: review['r2_vote'] = '❌'
                elif 'R3' in line and ('✅' in line or '🔄' in line or '❌' in line):
                    if '✅' in line: review['r3_vote'] = '✅'
                    elif '🔄' in line: review['r3_vote'] = '🔄'
                    elif '❌' in line: review['r3_vote'] = '❌'

            reviews.append(review)
        else:
            reviews.append({
                'gate': gate.upper(),
                'status': '⏳未开始',
                'result': '—'
            })

    return reviews


def parse_tasks_file(project_path: Path) -> dict:
    """Parse tasks.md for task counts."""
    tasks_file = project_path / 'tasks.md'
    if not tasks_file.exists():
        return {'blocked': 0, 'in_progress': 0, 'todo': 0, 'done': 0}

    content = tasks_file.read_text(encoding='utf-8')
    sections = {'blocked': 0, 'in_progress': 0, 'todo': 0, 'done': 0}
    current_section = None

    for line in content.split('\n'):
        if '🔴 Blocked' in line:
            current_section = 'blocked'
        elif '🟡 In Progress' in line:
            current_section = 'in_progress'
        elif '🔵 Todo' in line:
            current_section = 'todo'
        elif '🟢 Done' in line:
            current_section = 'done'
        elif current_section and line.strip().startswith('|') and not line.strip().startswith('| ID'):
            sections[current_section] += 1

    return sections


def collect_from_index() -> dict:
    """Collect all project data from .index.json (primary source)."""
    index_file = PROJECTS_DIR / '.index.json'
    if not index_file.exists():
        return None
    index = json.loads(index_file.read_text())
    projects = []
    for pname, pdata in index.get('projects', {}).items():
        tasks = pdata.get('tasks', [])
        tasks_by_status = {'blocked': 0, 'in_progress': 0, 'todo': 0, 'done': 0}
        for t in tasks:
            s = t.get('status', 'todo')
            tasks_by_status[s] = tasks_by_status.get(s, 0) + 1

        reviews = pdata.get('reviews', {})
        review_list = []
        for gate in ['DG1', 'DG2', 'DG3', 'DG4']:
            gate_data = reviews.get(gate, {})
            r1 = gate_data.get('R1', {}); r2 = gate_data.get('R2', {}); r3 = gate_data.get('R3', {})
            votes = [r1.get('vote'), r2.get('vote'), r3.get('vote')]
            approve = votes.count('approve')
            if approve >= 2:
                status = '✅通过'
            elif votes.count('reject') >= 2:
                status = '❌驳回'
            elif any(v for v in votes if v):
                status = '🔄评审中'
            else:
                status = '⏳未开始'
            review_list.append({
                'gate': gate,
                'status': status,
                'r1_vote': r1.get('vote', '—'),
                'r2_vote': r2.get('vote', '—'),
                'r3_vote': r3.get('vote', '—'),
            })

        projects.append({
            'name': pname,
            'direction': pdata.get('direction', 'Unknown'),
            'tech_lead': pdata.get('tech_lead', 'Unassigned'),
            'phase': pdata.get('phase', 'Unknown'),
            'overall_progress': pdata.get('overall_progress', 0),
            'status': pdata.get('status', '🟢正常'),
            'blockers': pdata.get('blockers', []),
            'tasks': tasks_by_status,
            'reviews': review_list,
        })

    stats = {
        'total_projects': len(projects),
        'active_projects': len([p for p in projects if p.get('overall_progress', 0) < 100]),
        'total_blockers': sum(len(p.get('blockers', [])) for p in projects),
        'at_risk': [p['name'] for p in projects if '🔴' in p.get('status', '')],
        'delayed': [p['name'] for p in projects if '延迟' in p.get('status', '')],
        'avg_progress': sum(p.get('overall_progress', 0) for p in projects) / max(len(projects), 1),
    }
    return {'source': 'index', 'projects': projects, 'stats': stats, 'generated_at': datetime.now().isoformat()}


def collect_all() -> dict:
    """Collect all project data. Prefers .index.json, falls back to markdown parsing."""
    if not PROJECTS_DIR.exists():
        return {'projects': [], 'generated_at': datetime.now().isoformat(), 'error': 'No projects directory'}

    # Primary: read from MCP-maintained .index.json
    result = collect_from_index()
    if result:
        return result

    # Fallback: parse markdown files
    projects = []
    for item in sorted(PROJECTS_DIR.iterdir()):
        if item.is_dir() and not item.name.startswith('.'):
            status = parse_status_file(item)
            if status is None:
                status = {'name': item.name, 'status': '⚠️无status.md'}
            status['reviews'] = parse_review_files(item)
            status['tasks'] = parse_tasks_file(item)
            projects.append(status)

    total_blockers = sum(p.get('tasks', {}).get('blocked', 0) for p in projects)
    at_risk = [p['name'] for p in projects if '🔴' in p.get('status', '')]
    delayed = [p['name'] for p in projects if '延迟' in p.get('status', '')]

    return {
        'source': 'markdown',
        'projects': projects,
        'stats': {
            'total_projects': len(projects),
            'active_projects': len([p for p in projects if p.get('overall_progress', 0) < 100]),
            'total_blockers': total_blockers,
            'at_risk': at_risk,
            'delayed': delayed,
            'avg_progress': sum(p.get('overall_progress', 0) for p in projects) / max(len(projects), 1)
        },
        'generated_at': datetime.now().isoformat()
    }


if __name__ == '__main__':
    data = collect_all()
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    DATA_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2))
    print(f"Dashboard data → {DATA_FILE}")
    print(json.dumps(data['stats'], ensure_ascii=False, indent=2))
