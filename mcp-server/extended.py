"""
Extended MCP Tools — Sprint management, meeting notes, knowledge base, reports.

Imported and registered by server.py's list_tools() and call_tool().
"""

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Optional


# ─── Sprint Management ───

SPRINTS_DIR_NAME = '.sprints'
MEETINGS_DIR_NAME = '.meetings'
KB_FILE_NAME = '.knowledge_base.json'


def _sprints_dir(project_path: Path) -> Path:
    d = project_path / SPRINTS_DIR_NAME
    d.mkdir(parents=True, exist_ok=True)
    return d


def _meetings_dir(project_path: Path) -> Path:
    d = project_path / MEETINGS_DIR_NAME
    d.mkdir(parents=True, exist_ok=True)
    return d


def _kb_file(project_dir: Path) -> Path:
    return project_dir / KB_FILE_NAME


def create_sprint(project_path: Path, sprint_num: int, start_date: str,
                  end_date: str, goal: str = '') -> dict:
    sprint = {
        'sprint_num': sprint_num,
        'start_date': start_date,
        'end_date': end_date,
        'goal': goal,
        'status': 'active',
        'total_points': 0,
        'completed_points': 0,
        'velocity': 0.0,
        'burndown': [],
        'retrospective': '',
        'created_at': datetime.now().isoformat(),
    }
    sprint_file = _sprints_dir(project_path) / f'sprint-{sprint_num:02d}.json'
    if sprint_file.exists():
        existing = json.loads(sprint_file.read_text())
        existing.update(sprint)
        sprint = existing
    sprint_file.write_text(json.dumps(sprint, ensure_ascii=False, indent=2))
    return sprint


def update_sprint(project_path: Path, sprint_num: int, **kwargs) -> dict:
    sprint_file = _sprints_dir(project_path) / f'sprint-{sprint_num:02d}.json'
    if not sprint_file.exists():
        return {'error': f'Sprint {sprint_num} not found'}

    sprint = json.loads(sprint_file.read_text())
    for key in ['status', 'total_points', 'completed_points', 'velocity',
                'goal', 'retrospective']:
        if key in kwargs and kwargs[key] is not None:
            sprint[key] = kwargs[key]
    if 'burndown_point' in kwargs:
        sprint.setdefault('burndown', []).append({
            'date': datetime.now().strftime('%Y-%m-%d'),
            'remaining': kwargs['burndown_point']
        })
    sprint['updated_at'] = datetime.now().isoformat()
    sprint_file.write_text(json.dumps(sprint, ensure_ascii=False, indent=2))
    return sprint


def list_sprints(project_path: Path) -> list:
    d = _sprints_dir(project_path)
    sprints = []
    for f in sorted(d.glob('sprint-*.json')):
        sprints.append(json.loads(f.read_text()))
    return sprints


# ─── Meeting Notes ───

def log_meeting(project_path: Path, meeting_type: str, summary: str,
                decisions: list = None, action_items: list = None,
                attendees: list = None) -> dict:
    meeting = {
        'type': meeting_type,
        'date': datetime.now().strftime('%Y-%m-%d'),
        'timestamp': datetime.now().isoformat(),
        'summary': summary,
        'decisions': decisions or [],
        'action_items': action_items or [],
        'attendees': attendees or [],
    }
    d = _meetings_dir(project_path)
    count = len(list(d.glob(f'{meeting_type}-*.json'))) + 1
    meeting_file = d / f'{meeting_type}-{count:03d}.json'
    meeting_file.write_text(json.dumps(meeting, ensure_ascii=False, indent=2))
    return meeting


def list_meetings(project_path: Path, meeting_type: str = None) -> list:
    d = _meetings_dir(project_path)
    meetings = []
    pattern = f'{meeting_type}-*.json' if meeting_type else '*.json'
    for f in sorted(d.glob(pattern)):
        meetings.append(json.loads(f.read_text()))
    return meetings


# ─── Knowledge Base ───

def add_knowledge(project_dir: Path, topic: str, content: str,
                  tags: list = None, author: str = '',
                  related_project: str = '') -> dict:
    kb_file = _kb_file(project_dir)
    kb = []
    if kb_file.exists():
        kb = json.loads(kb_file.read_text())

    entry = {
        'id': f'KB-{len(kb) + 1:04d}',
        'topic': topic,
        'content': content,
        'tags': tags or [],
        'author': author,
        'related_project': related_project,
        'created_at': datetime.now().isoformat(),
    }
    kb.append(entry)
    kb_file.write_text(json.dumps(kb, ensure_ascii=False, indent=2))
    return entry


def search_knowledge(project_dir: Path, query: str = '',
                     tags: list = None) -> list:
    kb_file = _kb_file(project_dir)
    if not kb_file.exists():
        return []
    kb = json.loads(kb_file.read_text())
    results = []
    query_lower = query.lower() if query else ''
    for entry in kb:
        match = False
        if query_lower:
            if (query_lower in entry.get('topic', '').lower() or
                    query_lower in entry.get('content', '').lower()):
                match = True
        if tags:
            entry_tags = entry.get('tags', [])
            if any(t in entry_tags for t in tags):
                match = True
        if match:
            results.append(entry)
    # Return at most 50 results, newest first
    results.reverse()
    return results[:50]


# ─── Handoff ───

HANDOFFS_DIR_NAME = '.handoffs'


def _handoffs_dir(project_path: Path) -> Path:
    d = project_path / HANDOFFS_DIR_NAME
    d.mkdir(parents=True, exist_ok=True)
    return d


def create_handoff(project_path: Path, from_role: str, to_role: str,
                   content: str, deliverable: str = '',
                   acceptance_criteria: list = None) -> dict:
    """Record a formal handoff between roles/departments."""
    d = _handoffs_dir(project_path)
    count = len(list(d.glob('handoff-*.json'))) + 1
    handoff = {
        'id': f'HANDOFF-{count:03d}',
        'from': from_role,
        'to': to_role,
        'content': content,
        'deliverable': deliverable,
        'acceptance_criteria': acceptance_criteria or [],
        'status': 'pending',  # pending | accepted | rejected
        'created_at': datetime.now().isoformat(),
        'resolved_at': None,
    }
    hf = d / f'handoff-{count:03d}.json'
    hf.write_text(json.dumps(handoff, ensure_ascii=False, indent=2))
    return handoff


def list_handoffs(project_path: Path, status: str = None) -> list:
    d = _handoffs_dir(project_path)
    results = []
    for f in sorted(d.glob('handoff-*.json')):
        h = json.loads(f.read_text())
        if status and h.get('status') != status:
            continue
        results.append(h)
    return results


def update_handoff(project_path: Path, handoff_id: str,
                   status: str = None, note: str = None) -> dict:
    d = _handoffs_dir(project_path)
    # handoff_id is like "HANDOFF-003"
    num = handoff_id.split('-')[-1]
    hf = d / f'handoff-{num}.json'
    if not hf.exists():
        return {'error': f'Handoff {handoff_id} not found'}
    h = json.loads(hf.read_text())
    if status:
        h['status'] = status
        if status in ('accepted', 'rejected'):
            h['resolved_at'] = datetime.now().isoformat()
    if note:
        h.setdefault('notes', []).append({
            'text': note,
            'timestamp': datetime.now().isoformat(),
        })
    hf.write_text(json.dumps(h, ensure_ascii=False, indent=2))
    return h


# ─── Git Operations ───

import subprocess


def _run_git(project_dir: Path, *args) -> dict:
    """Run a git command and return structured result."""
    try:
        result = subprocess.run(
            ['git'] + list(args),
            cwd=str(project_dir),
            capture_output=True,
            text=True,
            timeout=30,
        )
        return {
            'success': result.returncode == 0,
            'stdout': result.stdout.strip(),
            'stderr': result.stderr.strip(),
            'returncode': result.returncode,
        }
    except subprocess.TimeoutExpired:
        return {'success': False, 'error': 'Git command timed out (30s)'}
    except FileNotFoundError:
        return {'success': False, 'error': 'Git not available'}


def git_create_branch(project_dir: Path, branch_name: str, base_branch: str = 'main') -> dict:
    """Create a new feature branch from base."""
    # Validate branch name
    if not re.match(r'^[a-zA-Z0-9_\-/.]+$', branch_name):
        return {'error': f'Invalid branch name: {branch_name}'}

    # Ensure we're on base branch first
    checkout = _run_git(project_dir, 'checkout', base_branch)
    if not checkout['success']:
        return {'error': f'Failed to checkout {base_branch}', 'details': checkout.get('stderr', '')}

    # Pull latest
    _run_git(project_dir, 'pull', 'origin', base_branch)

    # Create branch
    result = _run_git(project_dir, 'checkout', '-b', branch_name)
    if result['success']:
        return {'success': True, 'branch': branch_name, 'base': base_branch}
    return {'error': 'Failed to create branch', 'details': result.get('stderr', '')}


def git_commit(project_dir: Path, message: str, files: list = None,
               author: str = '') -> dict:
    """Stage and commit changes."""
    if not message.strip():
        return {'error': 'Commit message is required'}

    status = _run_git(project_dir, 'status', '--porcelain')
    if not status['stdout']:
        return {'error': 'No changes to commit'}

    # Stage files (or all)
    if files:
        for f in files:
            add_result = _run_git(project_dir, 'add', f)
            if not add_result['success']:
                return {'error': f'Failed to stage {f}', 'details': add_result.get('stderr', '')}
    else:
        _run_git(project_dir, 'add', '-A')

    # Commit
    cmd = ['commit', '-m', message]
    if author:
        cmd.extend(['--author', author])
    result = _run_git(project_dir, *cmd)

    if result['success']:
        # Get the commit hash
        log = _run_git(project_dir, 'log', '-1', '--format=%H %s')
        return {
            'success': True,
            'commit': log['stdout'] if log['success'] else 'unknown',
            'message': message,
            'files_changed': len(status['stdout'].strip().split('\n')) if status['stdout'] else 0,
        }
    return {'error': 'Commit failed', 'details': result.get('stderr', '')}


def git_get_status(project_dir: Path) -> dict:
    """Get current git status: branch, changes, ahead/behind."""
    branch_result = _run_git(project_dir, 'branch', '--show-current')
    branch = branch_result['stdout'] if branch_result['success'] else 'unknown'

    status_result = _run_git(project_dir, 'status', '--porcelain')
    changed_files = []
    if status_result['stdout']:
        for line in status_result['stdout'].split('\n'):
            if line.strip():
                status_code = line[:2].strip()
                filename = line[3:].strip()
                changed_files.append({'status': status_code, 'file': filename})

    # Recent commits
    log_result = _run_git(project_dir, 'log', '--oneline', '-5')

    return {
        'branch': branch,
        'changed_files': changed_files,
        'uncommitted_count': len(changed_files),
        'recent_commits': log_result['stdout'].split('\n') if log_result['success'] and log_result['stdout'] else [],
    }


def git_merge_branch(project_dir: Path, source_branch: str,
                     target_branch: str = 'main', no_ff: bool = False) -> dict:
    """Merge source branch into target branch."""
    # Checkout target
    checkout = _run_git(project_dir, 'checkout', target_branch)
    if not checkout['success']:
        return {'error': f'Failed to checkout {target_branch}', 'details': checkout.get('stderr', '')}

    # Pull latest
    _run_git(project_dir, 'pull', 'origin', target_branch)

    # Merge
    args = ['merge', source_branch]
    if no_ff:
        args.append('--no-ff')
    args.append('-m')
    args.append(f'Merge {source_branch} into {target_branch}')
    result = _run_git(project_dir, *args)

    if result['success']:
        return {
            'success': True,
            'source': source_branch,
            'target': target_branch,
            'message': result['stdout'],
        }

    # Check for conflicts
    if 'CONFLICT' in result.get('stdout', '') or 'CONFLICT' in result.get('stderr', ''):
        conflict_files = _run_git(project_dir, 'diff', '--name-only', '--diff-filter=U')
        return {
            'success': False,
            'conflict': True,
            'conflict_files': conflict_files['stdout'].split('\n') if conflict_files['stdout'] else [],
            'message': 'Merge conflicts detected. Resolve manually then commit.',
            'details': result.get('stdout', '') or result.get('stderr', ''),
        }

    return {'error': 'Merge failed', 'details': result.get('stderr', '')}


# ─── Report Generation ───

def generate_report(project_dir: Path, projects_index: dict,
                    report_type: str = 'status',
                    project_name: str = None,
                    date_range: str = None) -> dict:
    """Generate various report types from project data."""

    if report_type == 'status':
        projects = projects_index.get('projects', {})
        if project_name and project_name in projects:
            p = projects[project_name]
            # Count tasks by status
            tasks = p.get('tasks', [])
            task_counts = {'blocked': 0, 'in_progress': 0, 'todo': 0, 'done': 0}
            for t in tasks:
                s = t.get('status', 'todo')
                task_counts[s] = task_counts.get(s, 0) + 1

            reviews = p.get('reviews', {})
            review_status = {}
            for gate in ['DG1', 'DG2', 'DG3', 'DG4']:
                gate_data = reviews.get(gate, {})
                votes = [gate_data.get(r, {}).get('vote') for r in ['R1', 'R2', 'R3']]
                approve = votes.count('approve')
                if approve >= 2:
                    review_status[gate] = '✅ 通过'
                elif votes.count('reject') >= 2:
                    review_status[gate] = '❌ 驳回'
                elif any(v for v in votes if v):
                    review_status[gate] = '🔄 评审中'
                else:
                    review_status[gate] = '⏳ 未开始'

            return {
                'type': 'status',
                'project': project_name,
                'phase': p.get('phase'),
                'progress': p.get('overall_progress', 0),
                'status': p.get('status'),
                'task_counts': task_counts,
                'review_status': review_status,
                'blockers': p.get('blockers', []),
            }

        # Company-wide status
        project_summaries = []
        for n, p in projects.items():
            project_summaries.append({
                'name': n,
                'direction': p.get('direction'),
                'progress': p.get('overall_progress', 0),
                'phase': p.get('phase'),
                'status': p.get('status'),
                'blockers': len(p.get('blockers', [])),
            })
        return {
            'type': 'company_status',
            'total_projects': len(project_summaries),
            'active': [p for p in project_summaries if p['progress'] < 100],
            'completed': [p for p in project_summaries if p['progress'] >= 100],
            'at_risk': [p for p in project_summaries if '🔴' in p.get('status', '')],
        }

    elif report_type == 'velocity':
        projects = projects_index.get('projects', {})
        velocity_data = {}
        if project_name and project_name in projects:
            pdir = project_dir / 'projects' / project_name
            sprints = list_sprints(pdir)
            velocity_data[project_name] = {
                'sprints': len(sprints),
                'total_points': sum(s.get('completed_points', 0) for s in sprints),
                'avg_velocity': (sum(s.get('completed_points', 0) for s in sprints) /
                                 max(len(sprints), 1)),
            }
        return {'type': 'velocity', 'data': velocity_data}

    elif report_type == 'quality':
        projects = projects_index.get('projects', {})
        quality_data = {}
        if project_name and project_name in projects:
            p = projects[project_name]
            reviews = p.get('reviews', {})
            scores = []
            for gate_data in reviews.values():
                for r in ['R1', 'R2', 'R3']:
                    s = gate_data.get(r, {}).get('score')
                    if s:
                        scores.append(s)
            quality_data[project_name] = {
                'avg_review_score': sum(scores) / max(len(scores), 1),
                'review_count': len(scores),
                'gates_passed': sum(1 for g in ['DG1', 'DG2', 'DG3', 'DG4']
                                    if reviews.get(g, {}).get('R1', {}).get('vote') == 'approve'
                                    and reviews.get(g, {}).get('R2', {}).get('vote') == 'approve'),
            }
        return {'type': 'quality', 'data': quality_data}

    return {'error': f'Unknown report type: {report_type}'}


# ─── MCP Tool Definitions ───

EXTENDED_TOOL_DEFS = [
    {
        'name': 'create_sprint',
        'description': 'Create a new sprint for a project',
        'inputSchema': {
            'type': 'object',
            'properties': {
                'project_name': {'type': 'string'},
                'sprint_num': {'type': 'integer'},
                'start_date': {'type': 'string'},
                'end_date': {'type': 'string'},
                'goal': {'type': 'string'},
            },
            'required': ['project_name', 'sprint_num', 'start_date', 'end_date']
        }
    },
    {
        'name': 'update_sprint',
        'description': 'Update sprint status, points, or burndown',
        'inputSchema': {
            'type': 'object',
            'properties': {
                'project_name': {'type': 'string'},
                'sprint_num': {'type': 'integer'},
                'status': {'type': 'string', 'enum': ['active', 'completed', 'cancelled']},
                'total_points': {'type': 'integer'},
                'completed_points': {'type': 'integer'},
                'burndown_point': {'type': 'integer', 'description': 'Remaining points today'},
                'retrospective': {'type': 'string'},
            },
            'required': ['project_name', 'sprint_num']
        }
    },
    {
        'name': 'list_sprints',
        'description': 'List all sprints for a project',
        'inputSchema': {
            'type': 'object',
            'properties': {
                'project_name': {'type': 'string'},
            },
            'required': ['project_name']
        }
    },
    {
        'name': 'log_meeting',
        'description': 'Record a meeting with summary, decisions, and action items',
        'inputSchema': {
            'type': 'object',
            'properties': {
                'project_name': {'type': 'string'},
                'meeting_type': {'type': 'string',
                                 'enum': ['standup', 'planning', 'review', 'retrospective', 'design_review', 'ad_hoc']},
                'summary': {'type': 'string'},
                'decisions': {'type': 'array', 'items': {'type': 'string'}},
                'action_items': {'type': 'array', 'items': {'type': 'string'}},
                'attendees': {'type': 'array', 'items': {'type': 'string'}},
            },
            'required': ['project_name', 'meeting_type', 'summary']
        }
    },
    {
        'name': 'list_meetings',
        'description': 'List meeting records for a project',
        'inputSchema': {
            'type': 'object',
            'properties': {
                'project_name': {'type': 'string'},
                'meeting_type': {'type': 'string'},
            },
            'required': ['project_name']
        }
    },
    {
        'name': 'add_knowledge',
        'description': 'Add an entry to the team knowledge base',
        'inputSchema': {
            'type': 'object',
            'properties': {
                'topic': {'type': 'string'},
                'content': {'type': 'string'},
                'tags': {'type': 'array', 'items': {'type': 'string'}},
                'author': {'type': 'string'},
                'related_project': {'type': 'string'},
            },
            'required': ['topic', 'content']
        }
    },
    {
        'name': 'search_knowledge',
        'description': 'Search the team knowledge base',
        'inputSchema': {
            'type': 'object',
            'properties': {
                'query': {'type': 'string'},
                'tags': {'type': 'array', 'items': {'type': 'string'}},
            },
            'required': []
        }
    },
    {
        'name': 'create_handoff',
        'description': 'Create a formal handoff record between roles/departments',
        'inputSchema': {
            'type': 'object',
            'properties': {
                'project_name': {'type': 'string'},
                'from_role': {'type': 'string', 'description': 'Role handing off, e.g. PM, TL, Designer'},
                'to_role': {'type': 'string', 'description': 'Role receiving, e.g. TL, Senior Engineer, DevOps'},
                'content': {'type': 'string', 'description': 'What is being handed off'},
                'deliverable': {'type': 'string', 'description': 'Concrete deliverable, e.g. PRD, Tech Spec, Design Spec'},
                'acceptance_criteria': {'type': 'array', 'items': {'type': 'string'}, 'description': 'Criteria for the receiver to accept'},
            },
            'required': ['project_name', 'from_role', 'to_role', 'content']
        }
    },
    {
        'name': 'list_handoffs',
        'description': 'List handoff records for a project, optionally filtered by status',
        'inputSchema': {
            'type': 'object',
            'properties': {
                'project_name': {'type': 'string'},
                'status': {'type': 'string', 'enum': ['pending', 'accepted', 'rejected']},
            },
            'required': ['project_name']
        }
    },
    {
        'name': 'update_handoff',
        'description': 'Accept or reject a handoff, or add a note',
        'inputSchema': {
            'type': 'object',
            'properties': {
                'project_name': {'type': 'string'},
                'handoff_id': {'type': 'string', 'description': 'e.g. HANDOFF-001'},
                'status': {'type': 'string', 'enum': ['accepted', 'rejected']},
                'note': {'type': 'string', 'description': 'Acceptance note or rejection reason'},
            },
            'required': ['project_name', 'handoff_id']
        }
    },
    {
        'name': 'git_create_branch',
        'description': 'Create a new git feature branch for a task',
        'inputSchema': {
            'type': 'object',
            'properties': {
                'project_name': {'type': 'string', 'description': 'Project name (uses project directory as git root)'},
                'branch_name': {'type': 'string', 'description': 'Branch name, e.g. feature/task-001'},
                'base_branch': {'type': 'string', 'description': 'Base branch (default: main)', 'default': 'main'},
            },
            'required': ['project_name', 'branch_name']
        }
    },
    {
        'name': 'git_commit',
        'description': 'Stage and commit changes with a message',
        'inputSchema': {
            'type': 'object',
            'properties': {
                'project_name': {'type': 'string'},
                'message': {'type': 'string', 'description': 'Commit message'},
                'files': {'type': 'array', 'items': {'type': 'string'}, 'description': 'Specific files to commit (omit for all)'},
                'author': {'type': 'string', 'description': 'Author string, e.g. "Name <email>"'},
            },
            'required': ['project_name', 'message']
        }
    },
    {
        'name': 'git_get_status',
        'description': 'Get current git status: branch, changed files, recent commits',
        'inputSchema': {
            'type': 'object',
            'properties': {
                'project_name': {'type': 'string'},
            },
            'required': ['project_name']
        }
    },
    {
        'name': 'git_merge_branch',
        'description': 'Merge a feature branch into target branch (detects conflicts)',
        'inputSchema': {
            'type': 'object',
            'properties': {
                'project_name': {'type': 'string'},
                'source_branch': {'type': 'string', 'description': 'Feature branch to merge from'},
                'target_branch': {'type': 'string', 'description': 'Branch to merge into (default: main)', 'default': 'main'},
                'no_ff': {'type': 'boolean', 'description': 'Disable fast-forward merge'},
            },
            'required': ['project_name', 'source_branch']
        }
    },
    {
        'name': 'generate_report',
        'description': 'Generate a report (status, velocity, or quality)',
        'inputSchema': {
            'type': 'object',
            'properties': {
                'report_type': {'type': 'string',
                                'enum': ['status', 'velocity', 'quality']},
                'project_name': {'type': 'string'},
                'date_range': {'type': 'string'},
            },
            'required': ['report_type']
        }
    },
]
