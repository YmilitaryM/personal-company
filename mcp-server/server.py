#!/usr/bin/env python3
"""
AI Team MCP Server — Structured data storage and querying for the AI dev team plugin.

Provides tools for:
- Project CRUD
- Task management
- Review records
- Dashboard data aggregation

Data is stored alongside the existing projects/ markdown files for dual compatibility.
"""

import fcntl
import json
import os
import re
import sys
import time
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Optional

from mcp.server import Server, InitializationOptions
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent, ServerCapabilities, ToolsCapability

# Import extended tools from same directory
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from extended import (EXTENDED_TOOL_DEFS, add_knowledge, search_knowledge,
                      generate_report,
                      git_create_branch, git_commit, git_get_status, git_merge_branch)

# Import project initializer
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scripts'))
from init_project import init_project as _init_project

# --- Configuration ---
PROJECT_DIR = Path(os.environ.get('CLAUDE_PROJECT_DIR', os.getcwd()))
PROJECTS_DIR = PROJECT_DIR / 'projects'
INDEX_FILE = PROJECTS_DIR / '.index.json'
LOCK_FILE = PROJECTS_DIR / '.index.lock'
LOCK_TIMEOUT = 5  # seconds
REVIEW_DIR_TEMPLATE = 'reviews'
SAFE_NAME_RE = re.compile(r'^[a-zA-Z0-9_\-.]+$')


# --- Auto-register project dir for the web dashboard ---
REGISTRY_FILE = Path.home() / '.ai-dev-team' / 'project-dirs'

def _register_project_dir():
    """Write the current PROJECT_DIR to a registry file so the web dashboard
    can discover projects across all directories where Claude Code was started."""
    try:
        registry_dir = REGISTRY_FILE.parent
        registry_dir.mkdir(parents=True, exist_ok=True)
        cwd = str(PROJECT_DIR.resolve())
        existing = set()
        if REGISTRY_FILE.exists():
            existing = set(line.strip() for line in REGISTRY_FILE.read_text().splitlines() if line.strip())
        if cwd not in existing:
            with open(REGISTRY_FILE, 'a') as f:
                f.write(cwd + '\n')
    except Exception:
        pass  # Never block startup for registry writes

_register_project_dir()


def _validate_project_name(name: str) -> bool:
    """Validate that a project name is safe (no path traversal)."""
    if name in ('.', '..'):
        return False
    return bool(SAFE_NAME_RE.match(name)) and '..' not in name and '/' not in name


# --- File Lock ---
@contextmanager
def _index_lock():
    """Context manager for exclusive access to the index file."""
    ensure_dirs()
    lock_fd = open(LOCK_FILE, 'w')
    deadline = time.time() + LOCK_TIMEOUT
    while True:
        try:
            fcntl.flock(lock_fd.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            break
        except BlockingIOError:
            if time.time() > deadline:
                lock_fd.close()
                raise TimeoutError(f'Could not acquire index lock within {LOCK_TIMEOUT}s')
            time.sleep(0.05)
    try:
        yield
    finally:
        fcntl.flock(lock_fd.fileno(), fcntl.LOCK_UN)
        lock_fd.close()


# --- Helpers ---
def ensure_dirs():
    PROJECTS_DIR.mkdir(parents=True, exist_ok=True)


def load_index() -> dict:
    ensure_dirs()
    with _index_lock():
        if INDEX_FILE.exists():
            return json.loads(INDEX_FILE.read_text())
        return {'projects': {}, 'team': _default_team()}


def save_index(data: dict):
    ensure_dirs()
    data['updated_at'] = datetime.now().isoformat()
    with _index_lock():
        INDEX_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2))


def _default_team():
    return {
        'members': {
            'cto': {'name': 'CTO', 'status': 'active', 'assigned_projects': []},
            'pm_a': {'name': 'PM-A (AI/ML)', 'status': 'active', 'assigned_projects': []},
            'pm_b': {'name': 'PM-B (IoT)', 'status': 'active', 'assigned_projects': []},
            'pm_c': {'name': 'PM-C (App&Web)', 'status': 'active', 'assigned_projects': []},
            'tl_a': {'name': 'TL-A (AI/ML)', 'status': 'active', 'assigned_projects': []},
            'tl_b': {'name': 'TL-B (IoT)', 'status': 'active', 'assigned_projects': []},
            'tl_c': {'name': 'TL-C (App&Web)', 'status': 'active', 'assigned_projects': []},
            'market': {'name': 'Market Manager', 'status': 'active', 'assigned_projects': []},
            'devops_1': {'name': 'DevOps-1', 'status': 'active', 'assigned_projects': []},
            'devops_2': {'name': 'DevOps-2', 'status': 'active', 'assigned_projects': []},
        },
        'agent_roles': ['senior_engineer', 'ml_engineer', 'iot_engineer', 'agent_engineer', 'designer', 'reviewer'],
    }


# --- Server Setup ---
server = Server("ai-team-db")


@server.list_tools()
async def list_tools() -> list[Tool]:
    tools = [
        Tool(
            name="list_projects",
            description="List all projects with basic status information",
            inputSchema={"type": "object", "properties": {}, "required": []}
        ),
        Tool(
            name="get_project",
            description="Get detailed information for a specific project",
            inputSchema={
                "type": "object",
                "properties": {
                    "project_name": {"type": "string", "description": "Project directory name"}
                },
                "required": ["project_name"]
            }
        ),
        Tool(
            name="create_project",
            description="Create a new project and initialize its structure",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Project name (used as directory name)"},
                    "direction": {"type": "string", "description": "Product direction: ML, IoT, Agent, or App&Web"},
                    "description": {"type": "string", "description": "Brief project description"},
                    "tech_lead": {"type": "string", "description": "Assigned Tech Lead"},
                    "pm": {"type": "string", "description": "Assigned PM"},
                    "target_date": {"type": "string", "description": "Target delivery date (YYYY-MM-DD)"}
                },
                "required": ["name", "direction", "description"]
            }
        ),
        Tool(
            name="update_project_status",
            description="Update a project's status",
            inputSchema={
                "type": "object",
                "properties": {
                    "project_name": {"type": "string"},
                    "phase": {"type": "string", "description": "Current phase: 需求分析, 方案设计, 开发实现, 测试评审, 交付验收"},
                    "phase_progress": {"type": "integer", "minimum": 0, "maximum": 100},
                    "overall_progress": {"type": "integer", "minimum": 0, "maximum": 100},
                    "status": {"type": "string", "description": "🟢正常, 🟡有风险, or 🔴严重延迟"},
                    "blockers": {"type": "array", "items": {"type": "string"}},
                    "this_week_done": {"type": "array", "items": {"type": "string"}},
                    "next_week_plan": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["project_name"]
            }
        ),
        Tool(
            name="create_task",
            description="Create a new task in a project. Optionally specify files to claim ownership and prevent conflicts.",
            inputSchema={
                "type": "object",
                "properties": {
                    "project_name": {"type": "string"},
                    "title": {"type": "string"},
                    "assignee": {"type": "string"},
                    "estimated_hours": {"type": "number"},
                    "priority": {"type": "string", "enum": ["P0", "P1", "P2", "P3"]},
                    "status": {"type": "string", "enum": ["todo", "assigned", "in_progress", "submitted", "in_review", "reviewed_pass", "reviewed_fail", "blocked", "done"], "default": "todo"},
                    "blocked_reason": {"type": "string"},
                    "files": {"type": "array", "items": {"type": "string"}, "description": "Source files this task claims. Conflicts with files in other active tasks are rejected."},
                },
                "required": ["project_name", "title"]
            }
        ),
        Tool(
            name="update_task",
            description="Update a task's status",
            inputSchema={
                "type": "object",
                "properties": {
                    "project_name": {"type": "string"},
                    "task_id": {"type": "string"},
                    "status": {"type": "string", "enum": ["todo", "assigned", "in_progress", "submitted", "in_review", "reviewed_pass", "reviewed_fail", "blocked", "done"]},
                    "assignee": {"type": "string"},
                    "blocked_reason": {"type": "string"},
                },
                "required": ["project_name", "task_id"]
            }
        ),
        Tool(
            name="list_tasks",
            description="List all tasks for a project",
            inputSchema={
                "type": "object",
                "properties": {
                    "project_name": {"type": "string"},
                    "status_filter": {"type": "string", "enum": ["todo", "assigned", "in_progress", "submitted", "in_review", "reviewed_pass", "reviewed_fail", "blocked", "done"]}
                },
                "required": ["project_name"]
            }
        ),
        Tool(
            name="create_review",
            description="Record a review for a project stage gate (Round 1 independent or Round 2 debate)",
            inputSchema={
                "type": "object",
                "properties": {
                    "project_name": {"type": "string"},
                    "gate": {"type": "string", "enum": ["DG1", "DG2", "DG3", "DG4"]},
                    "reviewer": {"type": "string", "enum": ["R1", "R2", "R3"]},
                    "vote": {"type": "string", "enum": ["approve", "changes_requested", "reject"]},
                    "score": {"type": "number", "minimum": 0, "maximum": 10},
                    "round": {"type": "integer", "enum": [1, 2], "description": "1 = independent review, 2 = post-debate revised"},
                    "dimensions": {"type": "object", "description": "Map of dimension_name → {score, evidence}"},
                    "findings": {"type": "array", "items": {"type": "object", "properties": {
                        "finding": {"type": "string"}, "severity": {"type": "string", "enum": ["blocker", "major", "minor"]},
                        "evidence": {"type": "string"}, "dimension": {"type": "string"}
                    }}},
                    "recommendations": {"type": "array", "items": {"type": "string"}},
                    "revised_score": {"type": "number", "minimum": 0, "maximum": 10, "description": "Score after debate revision (Round 2 only)"},
                    "challenges": {"type": "array", "items": {"type": "object", "properties": {
                        "target": {"type": "string"}, "finding": {"type": "string"},
                        "challenge": {"type": "string"}, "evidence": {"type": "string"}
                    }}},
                    "concessions": {"type": "array", "items": {"type": "object", "properties": {
                        "finding": {"type": "string"}, "concession": {"type": "string"}, "score_impact": {"type": "string"}
                    }}},
                    "defenses": {"type": "array", "items": {"type": "object", "properties": {
                        "finding": {"type": "string"}, "defense": {"type": "string"}
                    }}},
                    "conflicts_identified": {"type": "array", "items": {"type": "object", "properties": {
                        "perspectives": {"type": "array", "items": {"type": "string"}},
                        "issue": {"type": "string"}, "my_position": {"type": "string"},
                        "resolution_suggestion": {"type": "string"}
                    }}},
                    "findings_missed": {"type": "array", "items": {"type": "string"}},
                    "debate_summary": {"type": "string"}
                },
                "required": ["project_name", "gate", "reviewer", "vote"]
            }
        ),
        Tool(
            name="get_review",
            description="Get review status for a project",
            inputSchema={
                "type": "object",
                "properties": {
                    "project_name": {"type": "string"},
                    "gate": {"type": "string", "enum": ["DG1", "DG2", "DG3", "DG4"]}
                },
                "required": ["project_name"]
            }
        ),
        Tool(
            name="get_dashboard",
            description="Get aggregated dashboard data (company, department, or project level)",
            inputSchema={
                "type": "object",
                "properties": {
                    "level": {"type": "string", "enum": ["company", "department", "project"]},
                    "name": {"type": "string", "description": "Department or project name (required for department/project level)"}
                },
                "required": ["level"]
            }
        ),
        Tool(
            name="update_team_member",
            description="Update team member status and project assignment",
            inputSchema={
                "type": "object",
                "properties": {
                    "member_id": {"type": "string"},
                    "status": {"type": "string", "enum": ["active", "standby", "idle", "overload", "leave"]},
                    "assigned_projects": {"type": "array", "items": {"type": "string"}}
                },
                "required": ["member_id"]
            }
        ),
        Tool(
            name="list_team",
            description="List all team members and their status",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
    ]
    # Append extended tools (Sprint, Meetings, Knowledge Base, Reports)
    for td in EXTENDED_TOOL_DEFS:
        tools.append(Tool(**td))
    return tools


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    index = load_index()

    if name == "list_projects":
        projects = []
        for pname, pdata in index.get('projects', {}).items():
            projects.append({
                'name': pname,
                'direction': pdata.get('direction', 'Unknown'),
                'phase': pdata.get('phase', 'Unknown'),
                'progress': pdata.get('overall_progress', 0),
                'status': pdata.get('status', '🟢正常'),
                'tech_lead': pdata.get('tech_lead', 'Unassigned'),
                'target_date': pdata.get('target_date', ''),
                'blockers': len(pdata.get('blockers', [])),
            })
        return [TextContent(type="text", text=json.dumps(projects, ensure_ascii=False, indent=2))]

    elif name == "get_project":
        pname = arguments['project_name']
        pdata = index['projects'].get(pname, {})
        if not pdata:
            return [TextContent(type="text", text=json.dumps({'error': f'Project {pname} not found'}, ensure_ascii=False))]
        return [TextContent(type="text", text=json.dumps(pdata, ensure_ascii=False, indent=2))]

    elif name == "create_project":
        pname = arguments['name']
        if not _validate_project_name(pname):
            return [TextContent(type="text", text=json.dumps({'error': 'Invalid project name: use only letters, numbers, hyphens, underscores, dots'}, ensure_ascii=False))]
        if pname in index['projects']:
            return [TextContent(type="text", text=json.dumps({'error': f'Project {pname} already exists'}, ensure_ascii=False))]

        # Initialize template files via init_project
        init_result = _init_project(
            name=pname,
            direction=arguments.get('direction', 'Unknown'),
            description=arguments.get('description', ''),
            pm=arguments.get('pm', 'Unassigned'),
            tl=arguments.get('tech_lead', 'Unassigned'),
            target_date=arguments.get('target_date', ''),
        )
        if 'error' in init_result:
            return [TextContent(type="text", text=json.dumps(init_result, ensure_ascii=False))]

        # Ensure reviews directory
        reviews_dir = PROJECTS_DIR / pname / REVIEW_DIR_TEMPLATE
        reviews_dir.mkdir(parents=True, exist_ok=True)

        now = datetime.now().isoformat()
        pdata = {
            'name': pname,
            'direction': arguments.get('direction', 'Unknown'),
            'description': arguments.get('description', ''),
            'tech_lead': arguments.get('tech_lead', 'Unassigned'),
            'pm': arguments.get('pm', 'Unassigned'),
            'target_date': arguments.get('target_date', ''),
            'start_date': datetime.now().strftime('%Y-%m-%d'),
            'phase': '需求分析',
            'phase_progress': 0,
            'overall_progress': 0,
            'status': '🟢正常',
            'blockers': [],
            'this_week_done': [],
            'next_week_plan': [],
            'tasks': [],
            'reviews': {'DG1': {}, 'DG2': {}, 'DG3': {}, 'DG4': {}},
            'created_at': now,
            'updated_at': now,
        }
        index['projects'][pname] = pdata
        save_index(index)

        return [TextContent(type="text", text=json.dumps({'success': True, 'project': pdata, 'files_created': init_result.get('files_created', [])}, ensure_ascii=False, indent=2))]

    elif name == "update_project_status":
        pname = arguments['project_name']
        if pname not in index['projects']:
            return [TextContent(type="text", text=json.dumps({'error': f'Project {pname} not found'}, ensure_ascii=False))]

        pdata = index['projects'][pname]
        for field in ['phase', 'phase_progress', 'overall_progress', 'status', 'blockers', 'this_week_done', 'next_week_plan']:
            if field in arguments:
                pdata[field] = arguments[field]
        pdata['updated_at'] = datetime.now().isoformat()

        save_index(index)
        _write_status_md(PROJECTS_DIR / pname, pdata)

        return [TextContent(type="text", text=json.dumps({'success': True, 'project': pdata}, ensure_ascii=False, indent=2))]

    elif name == "create_task":
        pname = arguments['project_name']
        if pname not in index['projects']:
            return [TextContent(type="text", text=json.dumps({'error': f'Project {pname} not found'}, ensure_ascii=False))]

        # File conflict detection
        task_files = arguments.get('files', [])
        if task_files:
            conflicts = []
            for existing in index['projects'][pname].get('tasks', []):
                if existing.get('status') in ('todo', 'in_progress', 'blocked'):
                    existing_files = existing.get('files', [])
                    overlap = set(task_files) & set(existing_files)
                    if overlap:
                        conflicts.append({
                            'task_id': existing['id'],
                            'task_title': existing['title'],
                            'assignee': existing.get('assignee', '—'),
                            'conflicting_files': list(overlap),
                        })
            if conflicts:
                return [TextContent(type="text", text=json.dumps({
                    'error': 'File conflict detected',
                    'conflicts': conflicts,
                    'hint': 'These files are already owned by active tasks. Reassign or close those tasks first.',
                }, ensure_ascii=False, indent=2))]

        task = {
            'id': f"TASK-{datetime.now().strftime('%Y%m%d%H%M%S')}-{len(index['projects'][pname].get('tasks', [])) + 1:03d}",
            'title': arguments['title'],
            'assignee': arguments.get('assignee', 'Unassigned'),
            'estimated_hours': arguments.get('estimated_hours', 0),
            'priority': arguments.get('priority', 'P2'),
            'status': arguments.get('status', 'todo'),
            'blocked_reason': arguments.get('blocked_reason', ''),
            'files': task_files,
            'created_at': datetime.now().isoformat(),
        }
        index['projects'][pname].setdefault('tasks', []).append(task)
        save_index(index)
        _write_tasks_md(PROJECTS_DIR / pname, index['projects'][pname]['tasks'])

        return [TextContent(type="text", text=json.dumps({'success': True, 'task': task}, ensure_ascii=False, indent=2))]

    elif name == "update_task":
        pname = arguments['project_name']
        if pname not in index['projects']:
            return [TextContent(type="text", text=json.dumps({'error': f'Project {pname} not found'}, ensure_ascii=False))]

        task_id = arguments['task_id']
        for task in index['projects'][pname].get('tasks', []):
            if task['id'] == task_id:
                for field in ['status', 'assignee', 'blocked_reason']:
                    if field in arguments:
                        task[field] = arguments[field]
                task['updated_at'] = datetime.now().isoformat()
                save_index(index)
                _write_tasks_md(PROJECTS_DIR / pname, index['projects'][pname]['tasks'])
                return [TextContent(type="text", text=json.dumps({'success': True, 'task': task}, ensure_ascii=False, indent=2))]

        return [TextContent(type="text", text=json.dumps({'error': f'Task {task_id} not found'}, ensure_ascii=False))]

    elif name == "list_tasks":
        pname = arguments['project_name']
        if pname not in index['projects']:
            return [TextContent(type="text", text=json.dumps({'error': f'Project {pname} not found'}, ensure_ascii=False))]

        tasks = index['projects'][pname].get('tasks', [])
        status_filter = arguments.get('status_filter')
        if status_filter:
            tasks = [t for t in tasks if t.get('status') == status_filter]

        return [TextContent(type="text", text=json.dumps(tasks, ensure_ascii=False, indent=2))]

    elif name == "create_review":
        pname = arguments['project_name']
        if pname not in index['projects']:
            return [TextContent(type="text", text=json.dumps({'error': f'Project {pname} not found'}, ensure_ascii=False))]

        gate = arguments['gate']
        reviewer = arguments['reviewer']

        review_entry = {
            'reviewer': reviewer,
            'vote': arguments['vote'],
            'score': arguments.get('score', 0),
            'round': arguments.get('round', 1),
            'dimensions': arguments.get('dimensions', {}),
            'findings': arguments.get('findings', []),
            'recommendations': arguments.get('recommendations', []),
            'date': datetime.now().isoformat(),
        }
        # Round 2 debate fields
        if arguments.get('round') == 2:
            review_entry['revised_score'] = arguments.get('revised_score')
            review_entry['challenges'] = arguments.get('challenges', [])
            review_entry['concessions'] = arguments.get('concessions', [])
            review_entry['defenses'] = arguments.get('defenses', [])
            review_entry['conflicts_identified'] = arguments.get('conflicts_identified', [])
            review_entry['findings_missed'] = arguments.get('findings_missed', [])
            review_entry['debate_summary'] = arguments.get('debate_summary', '')
        index['projects'][pname].setdefault('reviews', {}).setdefault(gate, {})[reviewer] = review_entry
        save_index(index)
        _write_review_md(PROJECTS_DIR / pname, gate, index['projects'][pname]['reviews'][gate])

        return [TextContent(type="text", text=json.dumps({'success': True, 'review': review_entry}, ensure_ascii=False, indent=2))]

    elif name == "get_review":
        pname = arguments['project_name']
        if pname not in index['projects']:
            return [TextContent(type="text", text=json.dumps({'error': f'Project {pname} not found'}, ensure_ascii=False))]

        reviews = index['projects'][pname].get('reviews', {})
        gate = arguments.get('gate')
        if gate:
            reviews = {gate: reviews.get(gate, {})}

        return [TextContent(type="text", text=json.dumps(reviews, ensure_ascii=False, indent=2))]

    elif name == "get_dashboard":
        level = arguments['level']
        if level == 'company':
            dashboard = _build_company_dashboard(index)
        elif level == 'project':
            pname = arguments.get('name', '')
            dashboard = _build_project_dashboard(index, pname)
        elif level == 'department':
            dname = arguments.get('name', '')
            dashboard = _build_department_dashboard(index, dname)
        else:
            dashboard = {'error': f'Unknown level: {level}'}

        return [TextContent(type="text", text=json.dumps(dashboard, ensure_ascii=False, indent=2))]

    elif name == "update_team_member":
        member_id = arguments['member_id']
        member = index['team']['members'].get(member_id)
        if not member:
            return [TextContent(type="text", text=json.dumps({'error': f'Member {member_id} not found'}, ensure_ascii=False))]

        for field in ['status', 'assigned_projects']:
            if field in arguments:
                member[field] = arguments[field]
        save_index(index)
        return [TextContent(type="text", text=json.dumps({'success': True, 'member': member}, ensure_ascii=False, indent=2))]

    elif name == "list_team":
        return [TextContent(type="text", text=json.dumps(index.get('team', {}), ensure_ascii=False, indent=2))]

    # ─── Extended Tools: KB, Reports, Git ───
    elif name == "add_knowledge":
        result = add_knowledge(PROJECT_DIR, arguments['topic'], arguments['content'],
                               arguments.get('tags', []), arguments.get('author', ''),
                               arguments.get('related_project', ''))
        return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False, indent=2))]

    elif name == "search_knowledge":
        result = search_knowledge(PROJECT_DIR, arguments.get('query', ''),
                                  arguments.get('tags'))
        return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False, indent=2))]

    elif name == "git_create_branch":
        pname = arguments['project_name']
        if pname not in index['projects']:
            return [TextContent(type="text", text=json.dumps({'error': f'Project {pname} not found'}, ensure_ascii=False))]
        result = git_create_branch(PROJECTS_DIR / pname, arguments['branch_name'],
                                   arguments.get('base_branch', 'main'))
        return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False, indent=2))]

    elif name == "git_commit":
        pname = arguments['project_name']
        if pname not in index['projects']:
            return [TextContent(type="text", text=json.dumps({'error': f'Project {pname} not found'}, ensure_ascii=False))]
        result = git_commit(PROJECTS_DIR / pname, arguments['message'],
                            arguments.get('files'), arguments.get('author', ''))
        return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False, indent=2))]

    elif name == "git_get_status":
        pname = arguments['project_name']
        if pname not in index['projects']:
            return [TextContent(type="text", text=json.dumps({'error': f'Project {pname} not found'}, ensure_ascii=False))]
        result = git_get_status(PROJECTS_DIR / pname)
        return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False, indent=2))]

    elif name == "git_merge_branch":
        pname = arguments['project_name']
        if pname not in index['projects']:
            return [TextContent(type="text", text=json.dumps({'error': f'Project {pname} not found'}, ensure_ascii=False))]
        result = git_merge_branch(PROJECTS_DIR / pname, arguments['source_branch'],
                                  arguments.get('target_branch', 'main'),
                                  arguments.get('no_ff', False))
        return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False, indent=2))]

    elif name == "generate_report":
        result = generate_report(PROJECT_DIR, index, arguments['report_type'],
                                 arguments.get('project_name'),
                                 arguments.get('date_range'))
        return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False, indent=2))]

    return [TextContent(type="text", text=json.dumps({'error': f'Unknown tool: {name}'}, ensure_ascii=False))]


# --- Dashboard Builders ---
def _build_company_dashboard(index: dict) -> dict:
    projects = []
    for pname, pdata in index.get('projects', {}).items():
        projects.append({
            'name': pname,
            'direction': pdata.get('direction'),
            'progress': pdata.get('overall_progress', 0),
            'phase': pdata.get('phase'),
            'tech_lead': pdata.get('tech_lead'),
            'status': pdata.get('status', '🟢正常'),
            'start_date': pdata.get('start_date'),
            'target_date': pdata.get('target_date'),
            'blockers': len(pdata.get('blockers', [])),
        })

    team = index.get('team', {})
    at_risk = [p['name'] for p in projects if '🔴' in p.get('status', '')]
    delayed = [p['name'] for p in projects if '延迟' in p.get('status', '')]

    return {
        'projects': projects,
        'stats': {
            'total_projects': len(projects),
            'active_projects': len([p for p in projects if p.get('progress', 0) < 100]),
            'at_risk': at_risk,
            'delayed': delayed,
            'avg_progress': sum(p.get('progress', 0) for p in projects) / max(len(projects), 1),
        },
        'team': team,
        'generated_at': datetime.now().isoformat(),
    }


def _build_department_dashboard(index: dict, dept_name: str) -> dict:
    dept_map = {
        'AI/ML': ['ML', 'Agent'],
        'IoT': ['IoT'],
        'App&Web': ['App', 'Web'],
    }
    directions = dept_map.get(dept_name, [dept_name])

    dept_projects = []
    for pname, pdata in index.get('projects', {}).items():
        if pdata.get('direction') in directions:
            dept_projects.append({
                'name': pname,
                'direction': pdata.get('direction'),
                'progress': pdata.get('overall_progress', 0),
                'phase': pdata.get('phase'),
                'tech_lead': pdata.get('tech_lead'),
                'status': pdata.get('status', '🟢正常'),
            })

    return {
        'department': dept_name,
        'projects': dept_projects,
        'total_projects': len(dept_projects),
        'avg_progress': sum(p.get('progress', 0) for p in dept_projects) / max(len(dept_projects), 1),
        'generated_at': datetime.now().isoformat(),
    }


def _build_project_dashboard(index: dict, pname: str) -> dict:
    if pname not in index.get('projects', {}):
        return {'error': f'Project {pname} not found'}

    pdata = index['projects'][pname]
    tasks = pdata.get('tasks', [])

    return {
        'name': pname,
        'direction': pdata.get('direction'),
        'tech_lead': pdata.get('tech_lead'),
        'pm': pdata.get('pm'),
        'phase': pdata.get('phase'),
        'phase_progress': pdata.get('phase_progress', 0),
        'overall_progress': pdata.get('overall_progress', 0),
        'status': pdata.get('status', '🟢正常'),
        'start_date': pdata.get('start_date'),
        'target_date': pdata.get('target_date'),
        'blockers': pdata.get('blockers', []),
        'reviews': pdata.get('reviews', {}),
        'tasks': {
            'blocked': [t for t in tasks if t.get('status') == 'blocked'],
            'in_progress': [t for t in tasks if t.get('status') == 'in_progress'],
            'assigned': [t for t in tasks if t.get('status') == 'assigned'],
            'submitted': [t for t in tasks if t.get('status') == 'submitted'],
            'in_review': [t for t in tasks if t.get('status') == 'in_review'],
            'reviewed_pass': [t for t in tasks if t.get('status') == 'reviewed_pass'],
            'reviewed_fail': [t for t in tasks if t.get('status') == 'reviewed_fail'],
            'todo': [t for t in tasks if t.get('status') == 'todo'],
            'done': [t for t in tasks if t.get('status') == 'done'],
        },
        'generated_at': datetime.now().isoformat(),
    }


# --- File Writers (dual compatibility with markdown files) ---
def _write_status_md(project_dir: Path, pdata: dict):
    status_file = project_dir / 'status.md'
    content = f"""# {pdata['name']} — 状态

**最后更新**: {pdata.get('updated_at', datetime.now().strftime('%Y-%m-%d %H:%M'))}

## 基本信息
- 方向: {pdata.get('direction', 'Unknown')}
- Tech Lead: {pdata.get('tech_lead', 'Unassigned')}
- PM: {pdata.get('pm', 'Unassigned')}
- 开始日期: {pdata.get('start_date', '')}
- 预计交付: {pdata.get('target_date', '')}

## 当前阶段
- 阶段: {pdata.get('phase', 'Unknown')}
- 阶段进度: {pdata.get('phase_progress', 0)}%

## 整体进度
- 完成度: {pdata.get('overall_progress', 0)}%
- 状态: {pdata.get('status', '🟢正常')}

## 当前阻塞
"""
    for blocker in pdata.get('blockers', []):
        content += f"- [ ] {blocker}\n"

    content += """
## 本周完成
"""
    for item in pdata.get('this_week_done', []):
        content += f"- [x] {item}\n"

    content += """
## 下周计划
"""
    for item in pdata.get('next_week_plan', []):
        content += f"- [ ] {item}\n"

    status_file.write_text(content, encoding='utf-8')


def _write_tasks_md(project_dir: Path, tasks: list):
    tasks_file = project_dir / 'tasks.md'
    content = f"""# 任务面板

## 🔴 Blocked
| ID | 任务 | 负责人 | 阻塞原因 | 天数 |
|----|------|--------|----------|------|
"""
    for t in tasks:
        if t.get('status') == 'blocked':
            content += f"| {t['id']} | {t['title']} | {t.get('assignee', '—')} | {t.get('blocked_reason', '—')} | — |\n"

    content += """
## 🟡 In Progress
| ID | 任务 | 负责人 | 预计完成 | 优先级 |
|----|------|--------|----------|--------|
"""
    for t in tasks:
        if t.get('status') in ('in_progress', 'reviewed_fail'):
            fail_mark = ' ❌需要返工' if t.get('status') == 'reviewed_fail' else ''
            content += f"| {t['id']} | {t['title']}{fail_mark} | {t.get('assignee', '—')} | {t.get('estimated_hours', '—')}h | {t.get('priority', '—')} |\n"

    content += """
## 📋 Assigned
| ID | 任务 | 负责人 | 预计工时 | 优先级 |
|----|------|--------|----------|--------|
"""
    for t in tasks:
        if t.get('status') == 'assigned':
            content += f"| {t['id']} | {t['title']} | {t.get('assignee', '—')} | {t.get('estimated_hours', '—')}h | {t.get('priority', '—')} |\n"

    content += """
## 📤 Submitted (Awaiting Review)
| ID | 任务 | 负责人 | 提交时间 | 审查人 |
|----|------|--------|----------|--------|
"""
    for t in tasks:
        if t.get('status') == 'submitted':
            content += f"| {t['id']} | {t['title']} | {t.get('assignee', '—')} | {t.get('updated_at', '—')[:10]} | TL |\n"

    content += """
## 🔍 In Review
| ID | 任务 | 负责人 | 审查人 | 状态 |
|----|------|--------|--------|------|
"""
    for t in tasks:
        if t.get('status') == 'in_review':
            content += f"| {t['id']} | {t['title']} | {t.get('assignee', '—')} | TL | 审查中... |\n"

    content += """
## 🔵 Todo
| ID | 任务 | 负责人 | 预计工时 | 优先级 |
|----|------|--------|----------|--------|
"""
    for t in tasks:
        if t.get('status') == 'todo':
            content += f"| {t['id']} | {t['title']} | {t.get('assignee', '—')} | {t.get('estimated_hours', '—')}h | {t.get('priority', '—')} |\n"

    content += """
## 🟢 Done
| ID | 任务 | 负责人 | 日期 |
|----|------|--------|------|
"""
    for t in tasks:
        if t.get('status') in ('done', 'reviewed_pass'):
            content += f"| {t['id']} | {t['title']} | {t.get('assignee', '—')} | {t.get('updated_at', t.get('created_at', '—'))[:10]} |\n"

    tasks_file.write_text(content, encoding='utf-8')


def _write_review_md(project_dir: Path, gate: str, review_data: dict):
    reviews_dir = project_dir / REVIEW_DIR_TEMPLATE
    reviews_dir.mkdir(parents=True, exist_ok=True)
    review_file = reviews_dir / f'{gate.lower()}.md'

    content = f"""# 评审记录 — {gate}

"""
    for reviewer_id in ['R1', 'R2', 'R3']:
        rdata = review_data.get(reviewer_id, {})
        if not rdata:
            content += f"## {reviewer_id}: —\n未评审\n\n"
            continue

        vote_emoji = {'approve': '✅', 'changes_requested': '🔄', 'reject': '❌'}.get(rdata.get('vote', ''), '—')
        round_label = f" (Round {rdata.get('round', 1)})" if rdata.get('round') else ""
        score = rdata.get('revised_score') or rdata.get('score', 0)
        original_score = rdata.get('score', 0)
        score_display = f"{score}/10"
        if rdata.get('revised_score') is not None and rdata['revised_score'] != original_score:
            score_display += f" (原始: {original_score}, 变化: {rdata['revised_score'] - original_score:+.1f})"

        content += f"""## {reviewer_id}{round_label}
**投票**: {vote_emoji} {rdata.get('vote', '—')}
**评分**: {score_display}
**日期**: {rdata.get('date', '—')[:10]}

"""
        # Dimensions with scores
        dims = rdata.get('dimensions', {})
        if dims:
            content += "### 评分维度\n| 维度 | 得分 | 证据 |\n|------|------|------|\n"
            for dname, ddata in dims.items():
                if isinstance(ddata, dict):
                    content += f"| {dname} | {ddata.get('score', '—')} | {ddata.get('evidence', '—')} |\n"
                else:
                    content += f"| {dname} | {ddata} | — |\n"
            content += "\n"

        # Findings
        findings = rdata.get('findings', [])
        if findings:
            content += "### 发现\n"
            for f in findings:
                if isinstance(f, dict):
                    sev = f.get('severity', '—')
                    sev_icon = {'blocker': '🔴', 'major': '🟡', 'minor': '🟢'}.get(sev, '—')
                    content += f"- {sev_icon} [{sev}] **{f.get('finding', '')}** — {f.get('evidence', '—')} ({f.get('dimension', '—')})\n"
                else:
                    content += f"- {f}\n"
            content += "\n"

        # Recommendations
        recs = rdata.get('recommendations', [])
        if recs:
            content += "### 建议\n"
            for r in recs:
                content += f"- {r}\n"
            content += "\n"

        # Round 2 debate fields
        if rdata.get('round') == 2:
            # Challenges
            challenges = rdata.get('challenges', [])
            if challenges:
                content += "### 辩论挑战\n"
                for c in challenges:
                    if isinstance(c, dict):
                        content += f"- 挑战 {c.get('target', '—')}: **{c.get('finding', '—')}** — {c.get('challenge', '—')}\n"
                content += "\n"

            # Concessions
            concessions = rdata.get('concessions', [])
            if concessions:
                content += "### 让步\n"
                for c in concessions:
                    if isinstance(c, dict):
                        impact = c.get('score_impact', '')
                        content += f"- **{c.get('finding', '—')}**: {c.get('concession', '—')} (分数影响: {impact})\n"
                content += "\n"

            # Defenses
            defenses = rdata.get('defenses', [])
            if defenses:
                content += "### 辩护\n"
                for d in defenses:
                    if isinstance(d, dict):
                        content += f"- **{d.get('finding', '—')}**: {d.get('defense', '—')}\n"
                content += "\n"

            # Conflicts identified
            conflicts = rdata.get('conflicts_identified', [])
            if conflicts:
                content += "### 识别到的冲突\n"
                for c in conflicts:
                    if isinstance(c, dict):
                        perspectives = ', '.join(c.get('perspectives', []))
                        content += f"- {perspectives}: {c.get('issue', '—')} → {c.get('resolution_suggestion', '—')}\n"
                content += "\n"

            # Findings missed
            missed = rdata.get('findings_missed', [])
            if missed:
                content += "### 遗漏的发现\n"
                for m in missed:
                    content += f"- {m}\n"
                content += "\n"

            # Debate summary
            summary = rdata.get('debate_summary', '')
            if summary:
                content += f"### 辩论摘要\n{summary}\n\n"

    # Calculate final result
    votes = [review_data.get(r, {}).get('vote') for r in ['R1', 'R2', 'R3']]
    approve_count = votes.count('approve')
    reject_count = votes.count('reject')
    changes_count = votes.count('changes_requested')

    if approve_count >= 2:
        result = '✅ 通过'
    elif reject_count >= 2:
        result = '❌ 驳回'
    elif approve_count == 1 and reject_count == 1 and changes_count == 1:
        result = '⚖️ 僵局 — 需CTO仲裁'
    else:
        result = '🔄 修改后重审'

    content += f"""
## 最终裁决
**结果**: {result}
**投票统计**: ✅ {approve_count} | 🔄 {changes_count} | ❌ {reject_count}
"""

    review_file.write_text(content, encoding='utf-8')


# --- Main ---
async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="ai-team-db",
                server_version="0.3.0",
                capabilities=ServerCapabilities(
                    tools=ToolsCapability(),
                ),
            ),
        )


if __name__ == '__main__':
    import asyncio as _asyncio
    _asyncio.run(main())
