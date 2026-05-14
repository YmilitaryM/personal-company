#!/usr/bin/env python3
"""
Web Dashboard Server — browser-based real-time dashboard for AI Dev Team.
Zero dependencies (Python stdlib only). Reads .index.json directly.
Usage: python3 scripts/web_dashboard.py [--port 8080] [--project-dir .]
"""
import json
import os
import re
import sys
import time
import argparse
from datetime import datetime
from pathlib import Path
from typing import Optional
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn
from urllib.parse import urlparse, parse_qs
import socketserver
socketserver.TCPServer.allow_reuse_address = True

class ThreadingHTTPServer(ThreadingMixIn, HTTPServer):
    """Handle requests in separate threads."""
    daemon_threads = True

# Valid project name pattern — prevents path traversal
_VALID_NAME_RE = re.compile(r'^[a-zA-Z0-9][-a-zA-Z0-9_]*$')


def _is_status(status: str, check: str) -> bool:
    """Check if a Chinese status field indicates risk or delay."""
    s = status.lower()
    if check == 'risk':
        return any(kw in s for kw in ['风险', '严重', '🔴', 'risk', '高危', 'blocker'])
    elif check == 'delay':
        return any(kw in s for kw in ['延迟', '延期', 'delay', '超期', '逾期', '严重'])
    return False


def _get_all_project_dirs(base_dir: Path) -> list[Path]:
    """Get all project directories: base dir + any registered via MCP server."""
    dirs = [base_dir]
    registry = Path.home() / '.ai-dev-team' / 'project-dirs'
    if registry.exists():
        for line in registry.read_text().splitlines():
            line = line.strip()
            if line:
                p = Path(line) / 'projects'
                if p.exists() and p not in dirs:
                    dirs.append(p)
    return dirs


def _infer_direction(pipe: dict) -> str:
    """Try to infer product direction from pipeline decisions (TL/PM assignment)."""
    if pipe.get('product_direction'):
        return pipe['product_direction']
    for d in pipe.get('decisions', []):
        text = d.get('decision', '') + d.get('context', '')
        if 'TL-C' in text or 'PM-C' in text or 'App&Web' in text:
            return 'App&Web'
        if 'TL-A' in text or 'PM-A' in text or 'AI/ML' in text:
            return 'AI/ML'
        if 'TL-B' in text or 'PM-B' in text or 'IoT' in text:
            return 'IoT'
    return 'General'


def _infer_tech_lead(pipe: dict) -> Optional[str]:
    """Try to infer tech lead from pipeline planning decision."""
    for d in pipe.get('decisions', []):
        text = d.get('decision', '')
        if 'TL-C' in text: return 'TL-C (App&Web)'
        if 'TL-A' in text: return 'TL-A (AI/ML)'
        if 'TL-B' in text: return 'TL-B (IoT)'
    return None


def _calc_progress(pipe: dict) -> int:
    """Calculate overall progress from pipeline phases."""
    phases = pipe.get('phases', {})
    if not phases:
        return 0
    done = sum(1 for p in phases.values() if isinstance(p, dict) and p.get('status') == 'done')
    return round(done / len(phases) * 100)


_TASK_RE = re.compile(r'^####\s+(TASK-\d+):\s*(.+)$')
_PHASE_RE = re.compile(r'^###\s+(Phase\s+\d+):?\s*(.+)$')
_ASSIGN_RE = re.compile(r'-\s*\*\*Assignee\*\*:\s*(.+)$')
_ESTIMATE_RE = re.compile(r'-\s*\*\*Estimated\*\*:\s*(.+)$')

def _parse_tasks_md(project_dir: Path) -> list:
    """Parse tasks.md to extract structured task data."""
    tasks_file = project_dir / 'tasks.md'
    if not tasks_file.exists():
        return []
    try:
        lines = tasks_file.read_text().splitlines()
    except (IOError, UnicodeDecodeError):
        return []
    tasks = []
    current_phase = ''
    current_task = None
    for line in lines:
        pm = _PHASE_RE.match(line)
        if pm:
            current_phase = pm.group(2).strip()
            continue
        tm = _TASK_RE.match(line)
        if tm:
            if current_task:
                tasks.append(current_task)
            current_task = {'id': tm.group(1), 'title': tm.group(2).strip(),
                           'phase': current_phase, 'assignee': '', 'estimate': ''}
            continue
        if current_task:
            am = _ASSIGN_RE.match(line)
            if am:
                current_task['assignee'] = am.group(1).strip()
                continue
            em = _ESTIMATE_RE.match(line)
            if em:
                current_task['estimate'] = em.group(1).strip()
                continue
    if current_task:
        tasks.append(current_task)
    return tasks


def _extract_tasks(pipe: dict, project_dir: Path = None) -> list:
    """Extract tasks from tasks.md if available, otherwise from pipeline counts."""
    if project_dir:
        parsed = _parse_tasks_md(project_dir)
        if parsed:
            dev = pipe.get('phases', {}).get('development', {})
            tasks_done = dev.get('tasks_done', 0)
            for i, t in enumerate(parsed):
                t['status'] = 'done' if i < tasks_done else 'todo'
            return parsed
    dev = pipe.get('phases', {}).get('development', {})
    done = dev.get('tasks_done', 0)
    total = dev.get('tasks_total', 0)
    if total > 0:
        return [{'status': 'done'} for _ in range(done)] + \
               [{'status': 'todo'} for _ in range(total - done)]
    return []


def _extract_reviews(pipe: dict) -> dict:
    """Extract review gate status from pipeline quality phase."""
    gates = {}
    quality = pipe.get('phases', {}).get('quality', {})
    pipe_gates = quality.get('gates', {})
    for gate in ['DG1', 'DG2', 'DG3', 'DG4']:
        gd = pipe_gates.get(gate, {})
        if gd.get('status') == 'done':
            gates[gate] = {
                'R1': {'vote': 'approve', 'score': 8.0},
                'R2': {'vote': 'approve', 'score': 8.0},
                'R3': {'vote': 'approve', 'score': 8.0},
            }
    return gates


def _scan_dir_for_projects(projects_dir: Path, extra_projects: dict, index_project_names: set):
    """Scan a single projects_dir for directories with .pipeline-state.json not in index."""
    if not projects_dir.exists():
        return
    for item in sorted(projects_dir.iterdir()):
        if not item.is_dir() or item.name.startswith('.'):
            continue
        if item.name in index_project_names or item.name in extra_projects:
            continue
        pipe_file = item / '.pipeline-state.json'
        if pipe_file.exists():
            try:
                pipe = json.loads(pipe_file.read_text())
            except (json.JSONDecodeError, IOError):
                pipe = {}
            task_list = _extract_tasks(pipe, item)
            extra_projects[item.name] = {
                'direction': _infer_direction(pipe),
                'tech_lead': pipe.get('tech_lead') or _infer_tech_lead(pipe) or 'Unassigned',
                'phase': pipe.get('current_phase', 'Unknown'),
                'overall_progress': pipe.get('overall_progress') or _calc_progress(pipe),
                'status': pipe.get('status', 'ok'),
                'blockers': pipe.get('blockers', []),
                'tasks': task_list,
                'reviews': _extract_reviews(pipe),
                'start_date': pipe.get('started_at', ''),
                'target_date': pipe.get('target_date', ''),
            }


def load_dashboard_data(projects_dir: Path) -> dict:
    """Load aggregated dashboard data from .index.json across all registered dirs."""
    all_dirs = _get_all_project_dirs(projects_dir)

    all_index_projects = {}
    extra_projects = {}
    index_project_names = set()

    for d in all_dirs:
        index_file = d / '.index.json'
        if index_file.exists():
            try:
                index = json.loads(index_file.read_text())
                for pname, pdata in index.get('projects', {}).items():
                    if pname not in all_index_projects:
                        all_index_projects[pname] = pdata
                        index_project_names.add(pname)
            except (json.JSONDecodeError, IOError):
                pass

    if not all_index_projects and not extra_projects:
        # Check if any directories have projects at all
        has_any = any(
            d.exists() and any(i.is_dir() and not i.name.startswith('.') for i in d.iterdir())
            for d in all_dirs
        )
        if not has_any:
            return {'projects': [], 'stats': {'total_projects': 0, 'active_projects': 0,
                    'total_blockers': 0, 'at_risk': [], 'delayed': [], 'avg_progress': 0},
                    'generated_at': datetime.now().isoformat(), 'source': 'empty'}

    for d in all_dirs:
        _scan_dir_for_projects(d, extra_projects, index_project_names)

    all_projects = {**extra_projects, **all_index_projects}
    projects = []
    for pname, pdata in all_projects.items():
        tasks = pdata.get('tasks', [])
        tasks_by_status = {'blocked': 0, 'in_progress': 0, 'assigned': 0, 'submitted': 0, 'in_review': 0, 'reviewed_pass': 0, 'reviewed_fail': 0, 'todo': 0, 'done': 0}
        for t in tasks:
            s = t.get('status', 'todo')
            tasks_by_status[s] = tasks_by_status.get(s, 0) + 1

        reviews = pdata.get('reviews', {})
        review_list = []
        for gate in ['DG1', 'DG2', 'DG3', 'DG4']:
            gate_data = reviews.get(gate, {})
            r1 = gate_data.get('R1', {})
            r2 = gate_data.get('R2', {})
            r3 = gate_data.get('R3', {})
            votes = [r1.get('vote'), r2.get('vote'), r3.get('vote')]
            approve = votes.count('approve')
            if approve >= 2:
                status = 'passed'
            elif votes.count('reject') >= 2:
                status = 'rejected'
            elif any(v for v in votes if v):
                status = 'in_review'
            else:
                status = 'pending'
            review_list.append({
                'gate': gate,
                'status': status,
                'r1_vote': r1.get('vote', '—'),
                'r2_vote': r2.get('vote', '—'),
                'r3_vote': r3.get('vote', '—'),
                'r1_score': r1.get('score'),
                'r2_score': r2.get('score'),
                'r3_score': r3.get('score'),
            })

        projects.append({
            'name': pname,
            'direction': pdata.get('direction', 'Unknown'),
            'tech_lead': pdata.get('tech_lead', 'Unassigned'),
            'phase': pdata.get('phase', 'Unknown'),
            'overall_progress': pdata.get('overall_progress', 0),
            'status': pdata.get('status', 'ok'),
            'blockers': pdata.get('blockers', []),
            'tasks': tasks_by_status,
            'task_list': tasks if any(t.get('id') for t in tasks) else [],
            'reviews': review_list,
            'start_date': pdata.get('start_date', ''),
            'target_date': pdata.get('target_date', ''),
        })

    stats = {
        'total_projects': len(projects),
        'active_projects': len([p for p in projects if p.get('overall_progress', 0) < 100]),
        'total_blockers': sum(len(p.get('blockers', [])) for p in projects),
        'at_risk': [p['name'] for p in projects if _is_status(p.get('status', ''), 'risk')],
        'delayed': [p['name'] for p in projects if _is_status(p.get('status', ''), 'delay')],
        'avg_progress': round(sum(p.get('overall_progress', 0) for p in projects) / max(len(projects), 1), 1),
        'total_tasks_done': sum(p.get('tasks', {}).get('done', 0) for p in projects),
        'total_tasks': sum(sum(p.get('tasks', {}).values()) for p in projects),
    }
    return {'projects': projects, 'stats': stats, 'generated_at': datetime.now().isoformat(), 'source': 'index'}


def load_pipeline_state(projects_dir: Path, project_name: str) -> dict:
    """Load pipeline state for a specific project, searching all registered dirs."""
    for d in _get_all_project_dirs(projects_dir):
        state_file = d / project_name / '.pipeline-state.json'
        if state_file.exists():
            try:
                return json.loads(state_file.read_text())
            except (json.JSONDecodeError, IOError):
                return None
    return None


def load_all_pipelines(projects_dir: Path) -> dict:
    """Load pipeline states for all projects across all registered dirs."""
    pipelines = {}
    for d in _get_all_project_dirs(projects_dir):
        if not d.exists():
            continue
        for item in d.iterdir():
            if item.is_dir() and not item.name.startswith('.'):
                if item.name in pipelines:
                    continue
                state_file = item / '.pipeline-state.json'
                if state_file.exists():
                    try:
                        pipelines[item.name] = json.loads(state_file.read_text())
                    except (json.JSONDecodeError, IOError):
                        pass
    return pipelines


# ── HTML template (inline, dark theme SPA) ──

PAGE_HTML = r'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>AI Dev Team — Dashboard</title>
<style>
:root {
  --bg: #0d1117;
  --surface: #161b22;
  --border: #30363d;
  --text: #c9d1d9;
  --text-muted: #8b949e;
  --accent: #58a6ff;
  --green: #3fb950;
  --yellow: #d2991d;
  --red: #f85149;
  --purple: #a371f7;
}
* { margin: 0; padding: 0; box-sizing: border-box; }
body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif;
  background: var(--bg); color: var(--text); line-height: 1.5;
}
header {
  background: var(--surface); border-bottom: 1px solid var(--border);
  padding: 16px 24px; display: flex; align-items: center; justify-content: space-between;
}
header h1 { font-size: 18px; font-weight: 600; }
header h1 span { color: var(--accent); }
nav { display: flex; gap: 8px; }
nav button {
  background: var(--surface); color: var(--text); border: 1px solid var(--border);
  padding: 6px 16px; border-radius: 6px; cursor: pointer; font-size: 13px;
}
nav button:hover { background: #1c2838; }
nav button.active { background: var(--accent); color: #fff; border-color: var(--accent); }
main { max-width: 1200px; margin: 0 auto; padding: 24px; }
.stats-bar {
  display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
  gap: 12px; margin-bottom: 24px;
}
.stat-card {
  background: var(--surface); border: 1px solid var(--border);
  border-radius: 8px; padding: 16px;
}
.stat-card .label { font-size: 12px; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.5px; }
.stat-card .value { font-size: 28px; font-weight: 700; margin-top: 4px; }
.stat-card .value.green { color: var(--green); }
.stat-card .value.yellow { color: var(--yellow); }
.stat-card .value.red { color: var(--red); }
.stat-card .value.accent { color: var(--accent); }
.section-title {
  font-size: 16px; font-weight: 600; margin-bottom: 12px;
  padding-bottom: 8px; border-bottom: 1px solid var(--border);
}
.project-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(340px, 1fr)); gap: 16px; }
.project-card {
  background: var(--surface); border: 1px solid var(--border);
  border-radius: 8px; padding: 16px; cursor: pointer; transition: border-color 0.15s;
}
.project-card:hover { border-color: var(--accent); }
.project-card .card-header { display: flex; justify-content: space-between; align-items: start; margin-bottom: 8px; }
.project-card .card-header h3 { font-size: 15px; font-weight: 600; }
.project-card .direction-tag {
  font-size: 11px; padding: 2px 8px; border-radius: 12px;
  background: #1c2838; color: var(--accent);
}
.progress-bar {
  height: 6px; background: var(--border); border-radius: 3px; margin: 10px 0; overflow: hidden;
}
.progress-fill { height: 100%; border-radius: 3px; transition: width 0.5s; }
.progress-fill.green { background: var(--green); }
.progress-fill.yellow { background: var(--yellow); }
.progress-fill.red { background: var(--red); }
.progress-fill.accent { background: var(--accent); }
.card-meta { font-size: 12px; color: var(--text-muted); display: flex; gap: 16px; margin-top: 8px; }
.review-badges { display: flex; gap: 4px; margin-top: 8px; }
.badge {
  font-size: 10px; padding: 2px 6px; border-radius: 10px; font-weight: 600;
}
.badge.passed { background: #1a3a2a; color: var(--green); }
.badge.rejected { background: #3a1a1a; color: var(--red); }
.badge.in_review { background: #3a2a1a; color: var(--yellow); }
.badge.pending { background: #1c1c2a; color: var(--text-muted); }
.pipeline-bar {
  margin-top: 8px; padding: 6px 10px; background: #1c2838;
  border-radius: 6px; font-size: 11px; color: var(--accent);
}
#detail-panel { display: none; }
#detail-panel.visible { display: block; }
.back-btn {
  background: none; border: none; color: var(--accent); cursor: pointer;
  font-size: 13px; margin-bottom: 16px; padding: 4px 0;
}
.back-btn:hover { text-decoration: underline; }
.detail-header { margin-bottom: 20px; }
.detail-header h2 { font-size: 22px; }
.detail-header .subtitle { color: var(--text-muted); font-size: 13px; }
.detail-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
.detail-card {
  background: var(--surface); border: 1px solid var(--border);
  border-radius: 8px; padding: 16px;
}
.detail-card.full-width { grid-column: 1 / -1; }
.detail-card h4 { font-size: 14px; margin-bottom: 12px; color: var(--text-muted); }
.task-row { display: flex; justify-content: space-between; padding: 6px 0; font-size: 13px; }
.task-row .count { font-weight: 600; }
.review-table { width: 100%; font-size: 12px; border-collapse: collapse; }
.review-table th, .review-table td { padding: 6px 8px; text-align: left; border-bottom: 1px solid var(--border); }
.review-table th { color: var(--text-muted); font-weight: 500; }
.blocker-list { list-style: none; }
.blocker-list li { padding: 4px 0; font-size: 13px; color: var(--red); }
.blocker-list li::before { content: "⬤ "; font-size: 8px; }
.pipeline-phase-list { list-style: none; }
.pipeline-phase-list li {
  display: flex; align-items: center; gap: 10px; padding: 8px 0;
  border-bottom: 1px solid var(--border); font-size: 13px;
}
.pipeline-phase-list .phase-icon { font-size: 16px; width: 24px; text-align: center; }
.refresh-indicator { font-size: 11px; color: var(--text-muted); text-align: center; margin-top: 20px; }
.error-banner {
  background: #3a1a1a; color: var(--red); padding: 10px 16px;
  border-radius: 6px; margin-bottom: 16px; font-size: 13px;
}
.empty-state { text-align: center; padding: 48px 24px; color: var(--text-muted); }
.empty-state h3 { font-size: 18px; margin-bottom: 8px; }
footer { text-align: center; padding: 16px; color: var(--text-muted); font-size: 11px; }
</style>
</head>
<body>
<header>
  <h1>AI Dev Team <span>Dashboard</span></h1>
  <nav>
	    <a href="/config" style="color:var(--text-muted);text-decoration:none;font-size:13px;padding:6px 12px;border:1px solid var(--border);border-radius:6px;margin-left:4px;">Config</a>
    <button onclick="showCompany()" id="nav-company">Company</button>
    <button onclick="showDepartment('AI/ML')" id="nav-aiml">AI/ML</button>
    <button onclick="showDepartment('IoT')" id="nav-iot">IoT</button>
    <button onclick="showDepartment('App&Web')" id="nav-appweb">App&Web</button>
  </nav>
</header>
<main id="main"></main>
<footer>Auto-refresh every 30s · Last update: <span id="last-update">—</span></footer>

<script>
function escapeHtml(str) {
  if (!str) return '';
  const div = document.createElement('div');
  div.appendChild(document.createTextNode(String(str)));
  return div.innerHTML;
}

let currentView = 'company';
let currentDept = '';
let currentProject = '';
let dashboardData = null;
let pipelineData = null;

async function fetchData() {
  try {
    // For project detail view, always fetch company-level data
    // and filter client-side (avoids response format mismatch)
    const level = currentProject ? 'company' : currentView;
    const nameParam = (currentProject || !currentDept) ? '' : '&name=' + encodeURIComponent(currentDept);
    const dashResp = await fetch('/api/dashboard?level=' + level + nameParam);
    dashboardData = await dashResp.json();
    const pipeResp = await fetch('/api/pipelines');
    pipelineData = await pipeResp.json();
    document.getElementById('last-update').textContent = new Date().toLocaleTimeString();
    render();
  } catch (e) {
    document.getElementById('main').innerHTML = '<div class="error-banner">Connection error — is web_dashboard.py running?</div>';
  }
}

function render() {
  if (currentProject) renderProject();
  else if (currentDept) renderDepartment();
  else renderCompany();
}

function showCompany() {
  currentView = 'company'; currentDept = ''; currentProject = '';
  setActiveNav('nav-company'); fetchData();
}
function showDepartment(dept) {
  currentView = 'department'; currentDept = dept; currentProject = '';
  setActiveNav('nav-' + dept.toLowerCase().replace('&','').replace('/',''));
  fetchData();
}
function showProject(name) {
  currentView = 'project'; currentProject = name;
  setActiveNav(null); fetchData();
}
function backToList() {
  if (currentProject) { currentProject = ''; currentView = currentDept ? 'department' : 'company'; }
  else if (currentDept) { currentDept = ''; currentView = 'company'; }
  fetchData();
}
function setActiveNav(id) {
  document.querySelectorAll('nav button').forEach(b => b.classList.remove('active'));
  if (id) document.getElementById(id)?.classList.add('active');
}

function renderCompany() {
  const stats = dashboardData.stats || {};
  const projects = dashboardData.projects || [];
  const activePipe = Object.keys(pipelineData || {});

  let html = '<div class="stats-bar">' +
    statCard('Projects', stats.total_projects || 0, 'accent') +
    statCard('Active', stats.active_projects || 0, 'green') +
    statCard('At Risk', (stats.at_risk || []).length, (stats.at_risk || []).length > 0 ? 'red' : 'green') +
    statCard('Avg Progress', (stats.avg_progress || 0) + '%', 'accent') +
    statCard('Blockers', stats.total_blockers || 0, stats.total_blockers > 0 ? 'yellow' : 'green') +
    statCard('Tasks Done', (stats.total_tasks_done || 0) + '/' + (stats.total_tasks || 0), 'green') +
    '</div>';

  if (activePipe.length > 0) {
    html += '<div class="section-title">Active Pipelines</div>';
    html += '<div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:20px;">';
    activePipe.forEach(name => {
      const ps = pipelineData[name];
      const phases = ps ? Object.entries(ps.phases || {}) : [];
      const done = phases.filter(([k,v]) => v.status==='done').length;
      html += '<span style="background:#1c2838;padding:4px 12px;border-radius:12px;font-size:12px;color:var(--accent)">' +
        escapeHtml(name) + ' · Phase ' + done + '/' + phases.length + '</span>';
    });
    html += '</div>';
  }

  html += '<div class="section-title">All Projects</div>';
  if (projects.length === 0) {
    html += '<div class="empty-state"><h3>No projects yet</h3><p>Run /project new &lt;name&gt; in Claude Code to create one.</p></div>';
  } else {
    html += '<div class="project-grid">';
    projects.forEach(p => html += projectCard(p));
    html += '</div>';
  }
  html += '<div class="refresh-indicator">Auto-refresh every 30s · Last update: ' + new Date().toLocaleTimeString() + '</div>';
  document.getElementById('main').innerHTML = html;
}

function renderDepartment() {
  const projects = (dashboardData.projects || []).filter(p => {
    const d = p.direction || '';
    if (currentDept === 'AI/ML') return d === 'ML' || d === 'AI' || d === 'Agent';
    if (currentDept === 'IoT') return d === 'IoT' || d === 'Embedded';
    if (currentDept === 'App&Web') return d === 'App' || d === 'Web' || d === 'App&Web';
    return false;
  });
  const avg = projects.length > 0 ? Math.round(projects.reduce((s,p) => s + (p.overall_progress||0), 0) / projects.length) : 0;

  let html = '<button class="back-btn" onclick="showCompany()">← Company</button>';
  html += '<div class="stats-bar">' +
    statCard('Projects', projects.length, 'accent') +
    statCard('Avg Progress', avg + '%', 'accent') +
    statCard('Blockers', projects.reduce((s,p) => s + (p.blockers||[]).length, 0), 'yellow') +
    '</div>';
  html += '<div class="section-title">' + escapeHtml(currentDept) + ' Projects</div>';
  if (projects.length === 0) {
    html += '<div class="empty-state"><h3>No projects in ' + escapeHtml(currentDept) + '</h3></div>';
  } else {
    html += '<div class="project-grid">';
    projects.forEach(p => html += projectCard(p));
    html += '</div>';
  }
  html += '<div class="refresh-indicator">Auto-refresh every 30s</div>';
  document.getElementById('main').innerHTML = html;
}

function renderProject() {
  const p = (dashboardData.projects || []).find(x => x.name === currentProject);
  if (!p) { document.getElementById('main').innerHTML = '<div class="error-banner">Project not found: ' + escapeHtml(currentProject) + '</div>'; return; }
  const pipe = pipelineData ? pipelineData[currentProject] : null;

  const progressColor = (p.overall_progress || 0) >= 80 ? 'green' : (p.overall_progress || 0) >= 40 ? 'accent' : 'yellow';
  const reviewHtml = (p.reviews || []).map(r => '<tr>' +
    '<td>' + escapeHtml(r.gate) + '</td>' +
    '<td><span class="badge ' + escapeHtml(r.status) + '">' + escapeHtml(r.status.replace('_',' ')) + '</span></td>' +
    '<td>' + escapeHtml(r.r1_vote || '—') + (r.r1_score ? ' ('+escapeHtml(String(r.r1_score))+')' : '') + '</td>' +
    '<td>' + escapeHtml(r.r2_vote || '—') + (r.r2_score ? ' ('+escapeHtml(String(r.r2_score))+')' : '') + '</td>' +
    '<td>' + escapeHtml(r.r3_vote || '—') + (r.r3_score ? ' ('+escapeHtml(String(r.r3_score))+')' : '') + '</td>' +
    '</tr>').join('');

  const taskTotal = (p.tasks.done||0) + (p.tasks.in_progress||0) + (p.tasks.todo||0) + (p.tasks.blocked||0);
  const taskPct = taskTotal > 0 ? Math.round((p.tasks.done||0) / taskTotal * 100) : 0;

  let html = '<button class="back-btn" onclick="backToList()">← ' + escapeHtml(currentDept ? currentDept : 'Company') + '</button>';
  html += '<div class="detail-header"><h2>' + escapeHtml(p.name) + '</h2>';
  html += '<span class="subtitle">' + escapeHtml(p.direction||'—') + ' · TL: ' + escapeHtml(p.tech_lead||'—') + ' · Phase: ' + escapeHtml(p.phase||'—') + '</span></div>';

  html += '<div class="stats-bar">' +
    statCard('Progress', (p.overall_progress||0) + '%', progressColor) +
    statCard('Tasks', (p.tasks.done||0) + '/' + taskTotal, 'accent') +
    statCard('Blockers', (p.blockers||[]).length, (p.blockers||[]).length > 0 ? 'red' : 'green') +
    statCard('Status', p.status || 'ok', p.status === 'ok' || p.status === 'normal' ? 'green' : 'yellow') +
    '</div>';

  html += '<div class="progress-bar"><div class="progress-fill ' + progressColor + '" style="width:' + (p.overall_progress||0) + '%"></div></div>';

  html += '<div class="detail-grid">';

  // Tasks
  html += '<div class="detail-card"><h4>Tasks</h4>';
  html += taskRow('Done', (p.tasks.done||0) + (p.tasks.reviewed_pass||0), 'var(--green)');
  html += taskRow('In Progress', p.tasks.in_progress||0, 'var(--yellow)');
  html += taskRow('Submitted', p.tasks.submitted||0, 'var(--accent)');
  html += taskRow('In Review', p.tasks.in_review||0, 'var(--purple)');
  html += taskRow('Assigned', p.tasks.assigned||0, 'var(--text-muted)');
  html += taskRow('Todo', p.tasks.todo||0, 'var(--text-muted)');
  html += taskRow('Blocked', p.tasks.blocked||0, 'var(--red)');
  html += '<div class="progress-bar" style="margin-top:10px;"><div class="progress-fill green" style="width:' + taskPct + '%"></div></div>';
  html += '<span style="font-size:11px;color:var(--text-muted)">' + taskPct + '% complete</span>';
  html += '</div>';

  // Task detail table
  const taskList = p.task_list || [];
  if (taskList.length > 0) {
    html += '<div class="detail-card" style="grid-column:1/-1"><h4>Task Breakdown</h4>';
    html += '<table class="review-table"><thead><tr><th>ID</th><th>Title</th><th>Phase</th><th>Assignee</th><th>Status</th></tr></thead><tbody>';
    taskList.forEach(t => {
      const statusCls = t.status === 'done' ? 'passed' : t.status === 'in_progress' ? 'in_review' : 'pending';
      html += '<tr><td style="font-family:monospace;font-size:11px">' + escapeHtml(t.id||'') + '</td>' +
        '<td>' + escapeHtml(t.title||'') + '</td>' +
        '<td style="font-size:12px;color:var(--text-muted)">' + escapeHtml(t.phase||'') + '</td>' +
        '<td style="font-size:12px">' + escapeHtml(t.assignee||'') + '</td>' +
        '<td><span class="badge ' + statusCls + '">' + escapeHtml(t.status||'todo') + '</span></td></tr>';
    });
    html += '</tbody></table></div>';
  }

  // Review gates
  html += '<div class="detail-card"><h4>Review Gates</h4>';
  html += '<table class="review-table"><tr><th>Gate</th><th>Status</th><th>R1</th><th>R2</th><th>R3</th></tr>';
  html += reviewHtml || '<tr><td colspan="5" style="color:var(--text-muted)">No reviews yet</td></tr>';
  html += '</table></div>';

  // Pipeline progress
  if (pipe) {
    html += '<div class="detail-card"><h4>Pipeline Progress</h4><ul class="pipeline-phase-list">';
    const phaseNames = {intake:'Intake', market_research:'Market Research', requirements:'Requirements',
      architecture:'Architecture', cto_architecture_approval:'CTO Approval', design:'UI/UX Design',
      planning:'Planning', development:'Development', quality:'Quality Gates', delivery:'Delivery'};
    const phaseDocs = {intake:'intake-brief.md', market_research:'market-research.md', requirements:'prd.md',
      architecture:'architecture-review.md', design:'design-spec.md', planning:'tech-spec.md',
      development:'tasks.md', delivery:'delivery-report.md'};
    let phaseNum = 0;
    for (const [key, phase] of Object.entries(pipe.phases || {})) {
      const icon = phase.status === 'done' ? '✅' : phase.status === 'in_progress' ? '🔄' : phase.status === 'failed' ? '❌' : '⏳';
      html += '<li><span class="phase-icon">' + icon + '</span><span>' + phaseNum + '. ' + (phaseNames[key]||key) + '</span>';
      if (key === 'development' && phase.tasks_done !== undefined) {
        html += '<span style="font-size:11px;color:var(--text-muted);margin-left:auto">' + phase.tasks_done + '/' + phase.tasks_total + ' tasks</span>';
      }
      if (key === 'quality' && phase.gates) {
        const gates = phase.gates;
        html += '<span style="font-size:11px;margin-left:auto">';
        for (const [gk, gv] of Object.entries(gates)) {
          const gicon = gv === 'passed' ? '✅' : gv === 'failed' ? '❌' : gv === 'in_progress' ? '🔄' : '⏳';
          html += gk + ':' + gicon + ' ';
        }
        html += '</span>';
      }
      const doc = phaseDocs[key];
      if (doc && phase.status === 'done') {
        html += '<a href="/api/file?project=' + encodeURIComponent(currentProject) + '&file=' + encodeURIComponent(doc) + '" target="_blank" style="font-size:10px;margin-left:6px;color:var(--accent);text-decoration:none" title="View ' + escapeHtml(doc) + '">📄</a>';
      }
      html += '</li>';
      phaseNum++;
    }
    html += '</ul></div>';
  }

  // Blockers
  const blockers = p.blockers || [];
  if (blockers.length > 0) {
    html += '<div class="detail-card"><h4>Blockers</h4><ul class="blocker-list">';
    blockers.forEach(b => { html += '<li>' + escapeHtml(typeof b === 'string' ? b : JSON.stringify(b)) + '</li>'; });
    html += '</ul></div>';
  }

  // Documents section
  html += '<div class="detail-card"><h4>Project Documents</h4><div style="display:flex;flex-wrap:wrap;gap:6px">';
  const docs = [
    {file:'intake-brief.md', label:'Intake Brief'},
    {file:'market-research.md', label:'Market Research'},
    {file:'prd.md', label:'PRD'},
    {file:'architecture-review.md', label:'Architecture Review'},
    {file:'design-spec.md', label:'Design Spec'},
    {file:'tech-spec.md', label:'Tech Spec'},
    {file:'tasks.md', label:'Task Breakdown'},
    {file:'delivery-report.md', label:'Delivery Report'},
  ];
  docs.forEach(d => {
    html += '<a href="/api/file?project=' + encodeURIComponent(currentProject) + '&file=' + d.file + '" target="_blank" style="display:inline-block;padding:6px 12px;background:var(--surface);border:1px solid var(--border);border-radius:6px;color:var(--accent);text-decoration:none;font-size:12px">' + escapeHtml(d.label) + '</a>';
  });
  html += '</div></div>';

  html += '</div>';
  html += '<div class="refresh-indicator">Auto-refresh every 30s</div>';
  document.getElementById('main').innerHTML = html;
}

function statCard(label, value, color) {
  return '<div class="stat-card"><div class="label">' + escapeHtml(label) + '</div><div class="value ' + color + '">' + escapeHtml(String(value)) + '</div></div>';
}

function taskRow(label, count, color) {
  return '<div class="task-row"><span>' + escapeHtml(label) + '</span><span class="count" style="color:' + color + '">' + count + '</span></div>';
}

function projectCard(p) {
  const progressColor = (p.overall_progress || 0) >= 80 ? 'green' : (p.overall_progress || 0) >= 40 ? 'accent' : 'yellow';
  const badges = (p.reviews || []).map(r => {
    const cls = r.status === 'passed' ? 'passed' : r.status === 'rejected' ? 'rejected' : r.status === 'in_review' ? 'in_review' : 'pending';
    return '<span class="badge ' + cls + '">' + escapeHtml(r.gate) + '</span>';
  }).join('');
  const hasPipeline = pipelineData && pipelineData[p.name];
  let pipeHtml = '';
  if (hasPipeline) {
    const ps = pipelineData[p.name];
    const doneCount = Object.values(ps.phases || {}).filter(ph => ph.status === 'done').length;
    const phaseCount = Object.keys(ps.phases || {}).length || 8;
    pipeHtml = '<div class="pipeline-bar">Pipeline: Phase ' + doneCount + '/' + phaseCount + ' · ' + escapeHtml(ps.current_phase || '') + '</div>';
  }
  return '<div class="project-card" onclick="showProject(\'' + escapeHtml(p.name).replace(/'/g, '&#39;') + '\')">' +
    '<div class="card-header"><h3>' + escapeHtml(p.name) + '</h3><span class="direction-tag">' + escapeHtml(p.direction || '—') + '</span></div>' +
    '<div class="progress-bar"><div class="progress-fill ' + progressColor + '" style="width:' + (p.overall_progress||0) + '%"></div></div>' +
    '<div class="card-meta"><span>Phase: ' + escapeHtml(p.phase||'—') + '</span><span>' + (p.overall_progress||0) + '%</span><span>TL: ' + escapeHtml(p.tech_lead||'—') + '</span></div>' +
    '<div class="review-badges">' + badges + '</div>' +
    pipeHtml +
    '</div>';
}

// Auto-refresh
fetchData();
setInterval(fetchData, 30000);
</script>
</body>
</html>'''


CONFIG_HTML = r'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Model Config — AI Dev Team</title>
<style>
:root {
  --bg: #0d1117; --surface: #161b22; --border: #30363d;
  --text: #c9d1d9; --text-muted: #8b949e; --accent: #58a6ff;
  --green: #3fb950; --yellow: #d2991d; --red: #f85149;
}
* { margin:0; padding:0; box-sizing:border-box; }
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif;
  background: var(--bg); color: var(--text); line-height: 1.5; }
header { background: var(--surface); border-bottom: 1px solid var(--border);
  padding: 14px 24px; display: flex; align-items: center; justify-content: space-between; }
header h1 { font-size: 17px; } header h1 span { color: var(--accent); }
header nav a { color: var(--text-muted); text-decoration: none; font-size: 13px;
  padding: 4px 12px; border: 1px solid var(--border); border-radius: 6px; }
header nav a:hover { color: var(--accent); }
main { max-width: 800px; margin: 0 auto; padding: 24px; }
.section-title { font-size: 15px; font-weight: 600; margin-bottom: 14px; color: var(--accent); }
.alert { padding: 10px 16px; border-radius: 6px; margin-bottom: 16px; font-size: 13px; display: none; }
.alert.success { display: block; background: #1a3a2a; color: var(--green); }
.alert.error { display: block; background: #3a1a1a; color: var(--red); }
.config-form { background: var(--surface); border: 1px solid var(--border); border-radius: 8px; overflow: hidden; }
.config-row { display: flex; align-items: center; padding: 12px 16px; border-bottom: 1px solid var(--border); }
.config-row:last-child { border-bottom: none; }
.config-row .role-info { width: 200px; }
.config-row .role-name { font-weight: 600; font-size: 14px; }
.config-row .role-desc { font-size: 11px; color: var(--text-muted); }
.config-row .model-input { flex: 1; display: flex; gap: 8px; align-items: center; }
.config-row input {
  flex: 1; background: var(--bg); color: var(--text); border: 1px solid var(--border);
  padding: 6px 12px; border-radius: 6px; font-size: 13px; font-family: monospace;
}
.config-row input:focus { outline: none; border-color: var(--accent); }
.config-row .current-badge { font-size: 10px; padding: 2px 8px; border-radius: 10px;
  background: #1c2838; color: var(--accent); white-space: nowrap; }
.actions { display: flex; gap: 10px; margin-top: 16px; }
button {
  background: var(--accent); color: #fff; border: none;
  padding: 10px 20px; border-radius: 6px; cursor: pointer; font-size: 13px; font-weight: 600;
}
button:hover { opacity: 0.9; }
button.secondary { background: var(--surface); border: 1px solid var(--border); color: var(--text); }
button.danger { background: var(--red); }
.gateway-info { margin-top: 24px; background: var(--surface); border: 1px solid var(--border);
  border-radius: 8px; padding: 16px; font-size: 13px; }
.gateway-info h4 { margin-bottom: 8px; color: var(--text-muted); }
.gateway-info code { background: var(--bg); padding: 2px 6px; border-radius: 3px; font-size: 12px; }
.gateway-info .status { display: inline-block; width: 8px; height: 8px; border-radius: 50%; margin-right: 6px; }
.gateway-info .status.on { background: var(--green); }
.gateway-info .status.off { background: var(--red); }
.api-keys-section { margin-top: 24px; }
.api-keys-section .description { font-size: 12px; color: var(--text-muted); margin-bottom: 14px; }
.api-keys-section .description code { background: var(--bg); padding: 1px 5px; border-radius: 3px; font-size: 11px; }
.key-row { display: flex; align-items: center; padding: 10px 16px; border-bottom: 1px solid var(--border); gap: 12px; }
.key-row:last-child { border-bottom: none; }
.key-row .key-info { width: 180px; }
.key-row .key-name { font-size: 13px; font-weight: 600; font-family: monospace; }
.key-row .key-provider { font-size: 11px; color: var(--text-muted); margin-top: 2px; }
.key-row .key-value { flex: 1; font-size: 12px; font-family: monospace; color: var(--text-muted); }
.key-row .key-value.set { color: var(--green); }
.key-row .key-status { font-size: 10px; padding: 2px 8px; border-radius: 10px; font-weight: 600; white-space: nowrap; }
.key-row .key-status.set { background: #1a3a2a; color: var(--green); }
.key-row .key-status.missing { background: #3a2a1a; color: var(--yellow); }
.key-row .key-actions button { font-size: 11px; padding: 3px 12px; border-radius: 4px; cursor: pointer; background: var(--surface); color: var(--text); border: 1px solid var(--border); }
.key-row .key-actions button:hover { border-color: var(--accent); color: var(--accent); }
.key-row .key-actions button.save { background: var(--accent); color: #fff; border-color: var(--accent); }
.key-row .key-actions button.cancel { background: none; border: none; color: var(--text-muted); }
.key-row input { flex: 1; background: var(--bg); color: var(--text); border: 1px solid var(--accent); padding: 5px 10px; border-radius: 4px; font-size: 12px; font-family: monospace; }
.key-row input:focus { outline: none; }
.restart-hint { margin-top: 14px; padding: 10px 14px; background: #1c2838; border-radius: 6px; font-size: 12px; color: var(--accent); display: none; }
.restart-hint.visible { display: block; }
</style>
</head>
<body>
<header>
  <h1>Model <span>Config</span></h1>
  <nav>
	    <a href="/config" style="color:var(--text-muted);text-decoration:none;font-size:13px;padding:6px 12px;border:1px solid var(--border);border-radius:6px;margin-left:4px;">Config</a>
    <a href="/">← Dashboard</a>
  </nav>
</header>
<main>
<div id="alert" class="alert"></div>

<div class="section-title">Role Model Assignments</div>
<div class="config-form" id="config-form"></div>

<div class="actions">
  <button onclick="saveConfig()">Save Config</button>
  <button class="secondary" onclick="syncModels()">Sync to Agents</button>
</div>

	<div class="restart-hint" id="restart-hint">
	  Keys saved. Restart the gateway (<code>bash scripts/start.sh</code>) to apply changes.
	</div>

	<div class="section-title" style="margin-top:24px;">API Keys</div>
	<div class="api-keys-section">
	  <div class="description">
	    Configure API keys for each model provider. Keys are stored in <code>.env</code> and read by the LiteLLM gateway.
	    Empty keys will be commented out.
	  </div>
	  <div class="config-form" id="api-keys-form"></div>
	</div>

<div class="gateway-info">
  <h4>Gateway Status</h4>
  <p><span class="status off" id="gw-status"></span> <span id="gw-text">LiteLLM Gateway: checking...</span></p>
  <p style="margin-top:8px;color:var(--text-muted)">
    Start gateway: <code>bash scripts/start-gateway.sh</code><br>
    Claude Code env: <code>ANTHROPIC_BASE_URL=http://localhost:4000</code><br>
    API keys: edit <code>config/.env</code> (copy from <code>config/.env.example</code>)
  </p>
</div>
</main>

<script>
function escapeHtml(str) {
  if (!str) return '';
  const div = document.createElement('div');
  div.appendChild(document.createTextNode(String(str)));
  return div.innerHTML;
}

const ROLE_DESCRIPTIONS = {
  'cto': 'CTO — 立项审批、架构审批、僵局仲裁、交付签署',
  'architect': 'Architect — 架构治理',
  'pm': 'PM — 产品需求',
  'tech-lead': 'Tech Lead — 组建团队、任务分配、后台代码审查',
  'designer': 'Designer — UI/UX',
  'reviewer-r1': 'R1 评审员 — 架构专家（3轮辩论式）',
  'reviewer-r2': 'R2 评审员 — 产品质量专家（3轮辩论式）',
  'reviewer-r3': 'R3 评审员 — 工程效率专家（3轮辩论式）',
  'senior-engineer': 'Senior Engineer — 开发',
  'devops': 'DevOps — CI/CD',
  'market-manager': 'Market — 市场调研',
  'domain-engineer': 'Domain Eng — ML/IoT/Agent',
};

async function loadConfig() {
  const form = document.getElementById('config-form');
  form.innerHTML = '<div style="padding:20px;text-align:center;color:var(--text-muted)">Loading model configuration...</div>';
  try {
    const resp = await fetch('/api/models', {signal: AbortSignal.timeout(10000)});
    if (!resp.ok) throw new Error('Server returned ' + resp.status);
    const data = await resp.json();
    if (data.error) throw new Error(data.error);
    const models = data.models || {};
    const available = data.available || [];

    let html = '';
    for (const [role, desc] of Object.entries(ROLE_DESCRIPTIONS)) {
      const model = models[role] || 'inherit';
      const datalistId = 'dl-' + role;
      html += '<div class="config-row">' +
        '<div class="role-info"><div class="role-name">' + escapeHtml(role) + '</div><div class="role-desc">' + escapeHtml(desc) + '</div></div>' +
        '<div class="model-input">' +
        '<input list="' + datalistId + '" id="role-' + escapeHtml(role) + '" value="' + escapeHtml(model) + '" onchange="markChanged(\'' + escapeHtml(role) + '\')">' +
        '<datalist id="' + datalistId + '">' + available.map(m => '<option value="' + escapeHtml(m) + '">').join('') + '</datalist>' +
        '<span class="current-badge">' + escapeHtml(model) + '</span>' +
        '</div></div>';
    }
    form.innerHTML = html;
    // Attach click handlers for edit buttons
    form.querySelectorAll('.edit-key-btn').forEach(btn => {
      btn.addEventListener('click', function() {
        editKey(this.getAttribute('data-key'));
      });
    });
    configLoaded = true;
  } catch (e) {
    form.innerHTML = '<div style="padding:20px;color:var(--red);text-align:center">' +
      'Failed to load config: ' + escapeHtml(e.message) + '<br>' +
      '<span style="font-size:12px;color:var(--text-muted)">Is web_dashboard.py running? Check that config/models.json exists.</span><br>' +
      '<button onclick="loadConfig()" style="margin-top:10px;background:var(--surface);border:1px solid var(--border);color:var(--text);padding:6px 14px;border-radius:6px;cursor:pointer;font-size:12px;">Retry</button>' +
      '</div>';
  }
}

function markChanged(role) {
  const input = document.getElementById('role-' + role);
  const badge = input.nextElementSibling.nextElementSibling;
  badge.textContent = input.value;
  badge.style.background = '#3a2a1a';
  badge.style.color = 'var(--yellow)';
}

function showAlert(msg, type) {
  const el = document.getElementById('alert');
  el.textContent = msg; el.className = 'alert ' + type;
  setTimeout(() => { el.className = 'alert'; }, 4000);
}

let configLoaded = false;
async function saveConfig() {
  if (!configLoaded) {
    showAlert('Please wait for the form to load before saving.', 'error');
    return;
  }
  const roles = {};
  for (const role of Object.keys(ROLE_DESCRIPTIONS)) {
    const input = document.getElementById('role-' + role);
    if (input) roles[role] = input.value.trim();
  }
  const resp = await fetch('/api/models', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({roles})
  });
  const data = await resp.json();
  if (data.ok) {
    showAlert('Config saved. Run "Sync to Agents" to apply.', 'success');
    // restore badges
    document.querySelectorAll('.current-badge').forEach(b => {
      b.style.background = '#1c2838'; b.style.color = 'var(--accent)';
    });
  } else {
    showAlert('Error: ' + (data.error || 'unknown'), 'error');
  }
}

async function syncModels() {
  const resp = await fetch('/api/models/sync', {method: 'POST'});
  const data = await resp.json();
  if (data.ok) {
    showAlert('Synced! ' + (data.output || ''), 'success');
  } else {
    showAlert('Sync failed: ' + (data.error || 'unknown'), 'error');
  }
}

// ── API Keys management ──
const API_KEY_LABELS = {
  'ANTHROPIC_API_KEY': 'Anthropic Claude',
  'DEEPSEEK_API_KEY': 'DeepSeek',
  'OPENAI_API_KEY': 'OpenAI',
  'DASHSCOPE_API_KEY': 'Qwen (通义千问)',
  'LITELLM_MASTER_KEY': 'LiteLLM Admin',
};

async function loadApiKeys() {
  const form = document.getElementById('api-keys-form');
  form.innerHTML = '<div style="padding:12px;text-align:center;color:var(--text-muted);font-size:13px;">Loading...</div>';
  try {
    const resp = await fetch('/api/env');
    if (!resp.ok) throw new Error('Server returned ' + resp.status);
    const data = await resp.json();
    const keys = data.keys || {};

    let html = '';
    for (const [key, label] of Object.entries(API_KEY_LABELS)) {
      const info = keys[key] || {value: '', set: false};
      const masked = info.value || (info.set ? '***' : '');
      const statusCls = info.set ? 'set' : 'missing';
      const statusText = info.set ? 'Set' : 'Missing';
      html += '<div class="key-row" id="key-row-' + escapeHtml(key) + '">' +
        '<div class="key-info"><div class="key-name">' + escapeHtml(key) + '</div><div class="key-provider">' + escapeHtml(label) + '</div></div>' +
        '<span class="key-value ' + statusCls + '" id="key-val-' + escapeHtml(key) + '">' + (masked || '—') + '</span>' +
        '<span class="key-status ' + statusCls + '" id="key-badge-' + escapeHtml(key) + '">' + statusText + '</span>' +
        '<span class="key-actions"><button data-key="' + escapeHtml(key) + '" class="edit-key-btn">Edit</button></span>' +
        '</div>';
    }
    form.innerHTML = html;
    // Attach click handlers for edit buttons
    form.querySelectorAll('.edit-key-btn').forEach(btn => {
      btn.addEventListener('click', function() {
        editKey(this.getAttribute('data-key'));
      });
    });
  } catch (e) {
    form.innerHTML = '<div style="padding:12px;color:var(--red);text-align:center;font-size:13px;">' +
      'Failed to load API keys: ' + escapeHtml(e.message) +
      '<br><button onclick="loadApiKeys()" style="margin-top:6px;font-size:11px;background:var(--surface);border:1px solid var(--border);color:var(--text);padding:4px 12px;border-radius:4px;cursor:pointer;">Retry</button>' +
      '</div>';
  }
}

function editKey(key) {
  const row = document.getElementById('key-row-' + key);
  const valEl = document.getElementById('key-val-' + key);
  const badgeEl = document.getElementById('key-badge-' + key);
  const currentVal = valEl.textContent === '—' ? '' : valEl.textContent;
  row.innerHTML = '<div class="key-info"><div class="key-name">' + escapeHtml(key) + '</div><div class="key-provider">' + escapeHtml(API_KEY_LABELS[key] || '') + '</div></div>' +
    '<input type="text" id="edit-' + escapeHtml(key) + '" value="" placeholder="Enter API key...">' +
    '<span class="key-actions">' +
    '<button class="save save-key-btn" data-key="' + escapeHtml(key) + '">Save</button>' +
    '<button class="cancel cancel-edit-btn" data-key="' + escapeHtml(key) + '">Cancel</button>' +
    '</span>';
  document.getElementById('edit-' + key).focus();
  // Attach save/cancel handlers
  row.querySelector('.save-key-btn').addEventListener('click', function() {
    saveKey(this.getAttribute('data-key'));
  });
  row.querySelector('.cancel-edit-btn').addEventListener('click', function() {
    cancelEdit(this.getAttribute('data-key'));
  });
}

async function saveKey(key) {
  const input = document.getElementById('edit-' + key);
  const value = input ? input.value.trim() : '';
  try {
    const payload = {};
    payload[key] = value;
    const resp = await fetch('/api/env', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({keys: payload})
    });
    const data = await resp.json();
    if (data.ok) {
      document.getElementById('restart-hint').className = 'restart-hint visible';
      loadApiKeys();
    } else {
      showAlert('Error: ' + (data.error || 'unknown'), 'error');
    }
  } catch (e) {
    showAlert('Failed to save: ' + e.message, 'error');
  }
}

function cancelEdit(key) {
  loadApiKeys();
}

// Check gateway health
async function checkGateway() {
  try {
    const resp = await fetch('http://localhost:4000/health', {signal: AbortSignal.timeout(3000)});
    if (resp.ok) {
      document.getElementById('gw-status').className = 'status on';
      document.getElementById('gw-text').textContent = 'LiteLLM Gateway: running';
      return;
    }
  } catch(e) {}
  document.getElementById('gw-status').className = 'status off';
  document.getElementById('gw-text').textContent = 'LiteLLM Gateway: not running';
}

loadConfig();
loadApiKeys();
checkGateway();
</script>
</body>
</html>'''


class DashboardHandler(BaseHTTPRequestHandler):
    """HTTP request handler for the dashboard server."""

    projects_dir = Path.cwd() / 'projects'

    @property
    def project_root(self):
        return self.projects_dir.parent

    def log_message(self, format, *args):
        """Suppress default logging or keep it minimal."""
        if self.server.verbose:
            super().log_message(format, *args)

    def _send_json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False, indent=2).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', len(body))
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, html, status=200):
        body = html.encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', len(body))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip('/') or '/'
        params = parse_qs(parsed.query)

        if path == '/' or path == '/dashboard':
            self._send_html(PAGE_HTML)
            return

        if path == '/api/health':
            self._send_json({'status': 'ok', 'time': datetime.now().isoformat()})
            return

        if path == '/api/dashboard':
            level = params.get('level', ['company'])[0]
            name = params.get('name', [None])[0]

            data = load_dashboard_data(self.projects_dir)

            if level == 'company':
                self._send_json(data)
            elif level == 'department':
                dept_map = {
                    'AI/ML': ['ML', 'AI', 'Agent'],
                    'IoT': ['IoT', 'Embedded'],
                    'App&Web': ['App', 'Web', 'App&Web'],
                }
                directions = dept_map.get(name, [name])
                filtered = [p for p in data.get('projects', []) if p.get('direction') in directions]
                avg = round(sum(p.get('overall_progress', 0) for p in filtered) / max(len(filtered), 1), 1)
                self._send_json({
                    'department': name,
                    'projects': filtered,
                    'stats': {'total_projects': len(filtered), 'avg_progress': avg},
                    'generated_at': data.get('generated_at'),
                })
            elif level == 'project':
                proj = next((p for p in data.get('projects', []) if p['name'] == name), None)
                if proj:
                    pipe = load_pipeline_state(self.projects_dir, name)
                    self._send_json({'project': proj, 'pipeline': pipe, 'generated_at': data.get('generated_at')})
                else:
                    self._send_json({'error': 'Project not found', 'project': name}, 404)
            else:
                self._send_json({'error': 'Invalid level'}, 400)
            return

        if path == '/api/pipelines':
            pipelines = load_all_pipelines(self.projects_dir)
            self._send_json(pipelines)
            return

        if path == '/api/pipeline':
            project = params.get('project', [None])[0]
            if not project:
                self._send_json({'error': 'Missing project parameter'}, 400)
                return
            if not _VALID_NAME_RE.match(project):
                self._send_json({'error': 'Invalid project name'}, 400)
                return
            state = load_pipeline_state(self.projects_dir, project)
            if state:
                self._send_json(state)
            else:
                self._send_json({'error': 'No pipeline found for ' + project}, 404)
            return

        if path == '/api/models':
            config_file = Path(self.project_root) / 'config' / 'models.json'
            if config_file.exists():
                config = json.loads(config_file.read_text())
                # Also load available models from litellm.yaml
                available = self._load_available_models()
                self._send_json({'models': config.get('roles', {}), 'available': available})
            else:
                self._send_json({'error': 'models.json not found'}, 404)
            return

        if path == '/api/env':
            env_file = Path(self.project_root) / '.env'
            template_keys = self._env_keys_template()
            current = self._parse_env_file(env_file)
            keys_out = {}
            for key in template_keys:
                val = current.get(key, '')
                keys_out[key] = {
                    'value': self._mask_key(val),
                    'set': bool(val),
                }
            self._send_json({'keys': keys_out, 'masked': True})
            return

        if path == '/api/file':
            project = params.get('project', [None])[0]
            filename = params.get('file', [None])[0]
            if not project or not filename or not _VALID_NAME_RE.match(project):
                self._send_json({'error': 'Invalid project or file'}, 400)
                return
            if '..' in filename or '/' in filename:
                self._send_json({'error': 'Invalid filename'}, 400)
                return
            for d in _get_all_project_dirs(self.projects_dir):
                file_path = d / project / filename
                if file_path.exists() and file_path.suffix == '.md':
                    content = file_path.read_text()
                    # Simple markdown → HTML conversion for display
                    title = filename.replace('.md', '').replace('-', ' ').title()
                    self._send_html(f'<!DOCTYPE html><html lang="zh-CN"><head><meta charset="UTF-8">'
                        f'<title>{title}</title>'
                        f'<style>body{{font-family:-apple-system,BlinkMacSystemFont,sans-serif;max-width:900px;margin:0 auto;padding:20px;background:#0d1117;color:#c9d1d9;line-height:1.6}}'
                        f'pre{{background:#161b22;padding:16px;border-radius:6px;overflow-x:auto}}'
                        f'code{{background:#161b22;padding:2px 6px;border-radius:3px;font-size:13px}}'
                        f'h1,h2,h3,h4{{color:#58a6ff}}h1{{border-bottom:1px solid #30363d;padding-bottom:8px}}'
                        f'table{{border-collapse:collapse;width:100%}}th,td{{border:1px solid #30363d;padding:6px 12px;text-align:left}}'
                        f'th{{background:#161b22}}a{{color:#58a6ff}}</style></head><body>'
                        f'<a href="javascript:history.back()" style="color:var(--accent)">← Back</a>'
                        f'<div id="content"></div>'
                        f'<script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>'
                        f'<script>document.getElementById("content").innerHTML=marked.parse({json.dumps(content)});</script>'
                        f'</body></html>')
                    return
            self._send_json({'error': 'File not found'}, 404)
            return

        if path == '/config':
            self._send_html(self._config_page())
            return

        self._send_json({'error': 'Not found'}, 404)

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip('/') or '/'
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length) if content_length > 0 else b'{}'

        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            self._send_json({'error': 'Invalid JSON'}, 400)
            return

        if path == '/api/models':
            self._handle_save_models(data)
            return

        if path == '/api/models/sync':
            self._handle_sync_models()
            return

        if path == '/api/env':
            self._handle_save_env(data)
            return

        self._send_json({'error': 'Not found'}, 404)

    def _load_available_models(self):
        """Parse litellm.yaml for available model names."""
        litellm_config = Path(self.project_root) / 'config' / 'litellm.yaml'
        if not litellm_config.exists():
            return ['claude-opus-4-7', 'claude-sonnet-4-6', 'claude-haiku-4-5',
                    'deepseek-chat', 'deepseek-reasoner', 'gpt-4o', 'gpt-5-mini',
                    'qwen3-coder', 'opus', 'sonnet', 'haiku', 'inherit']
        try:
            import yaml
            config = yaml.safe_load(litellm_config.read_text())
            return [m['model_name'] for m in config.get('model_list', [])]
        except Exception:
            return [m['model_name'] for m in self._parse_yaml_models(litellm_config)]

    def _parse_yaml_models(self, path):
        """Fallback: simple YAML model name parser without pyyaml."""
        models = []
        with open(path) as f:
            content = f.read()
        import re
        for m in re.finditer(r'model_name:\s*(\S+)', content):
            models.append(m.group(1))
        return [{'model_name': n} for n in models]

    def _parse_env_file(self, path):
        """Parse .env file returning dict of key-value pairs."""
        result = {}
        if not path.exists():
            return result
        for line in path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            key, _, value = line.partition('=')
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            result[key] = value
        return result

    def _write_env_file(self, path, updates):
        """Write updated keys to .env, preserving existing structure.
        If .env doesn't exist, generate from .env.example template."""
        template = Path(self.project_root) / 'config' / '.env.example'
        if path.exists():
            lines = path.read_text().splitlines()
            updated_keys = set()
            new_lines = []
            for line in lines:
                stripped = line.strip()
                if stripped and not stripped.startswith('#') and '=' in stripped:
                    key = stripped.split('=', 1)[0].strip()
                    if key in updates:
                        new_lines.append(f'{key}={updates[key]}')
                        updated_keys.add(key)
                    else:
                        new_lines.append(line)
                else:
                    new_lines.append(line)
            # Add new keys not in file
            for key, value in updates.items():
                if key not in updated_keys and value:
                    new_lines.append(f'{key}={value}')
            path.write_text('\n'.join(new_lines) + '\n')
        else:
            # Generate from template
            if template.exists():
                lines = template.read_text().splitlines()
                new_lines = []
                for line in lines:
                    stripped = line.strip()
                    if stripped and not stripped.startswith('#') and '=' in stripped:
                        key = stripped.split('=', 1)[0].strip()
                        if key in updates and updates[key]:
                            new_lines.append(f'{key}={updates[key]}')
                        elif key in updates:
                            new_lines.append(f'#{key}=')
                        else:
                            new_lines.append(line)
                    else:
                        new_lines.append(line)
                path.write_text('\n'.join(new_lines) + '\n')
            else:
                # No template, just write keys
                path.write_text('\n'.join(f'{k}={v}' for k, v in updates.items() if v) + '\n')

    def _env_keys_template(self):
        """Return the set of expected API key names from .env.example."""
        template = Path(self.project_root) / 'config' / '.env.example'
        if not template.exists():
            return ['ANTHROPIC_API_KEY', 'DEEPSEEK_API_KEY', 'OPENAI_API_KEY',
                    'DASHSCOPE_API_KEY', 'LITELLM_MASTER_KEY']
        keys = []
        for line in template.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                keys.append(line.split('=', 1)[0].strip())
        return keys

    def _mask_key(self, value):
        """Mask an API key: show first 6 + *** + last 4."""
        if not value or len(value) < 10:
            return value[:3] + '***' if value else ''
        return value[:6] + '***' + value[-4:]

    def _handle_save_models(self, data):
        """Save model assignments to models.json."""
        config_file = Path(self.project_root) / 'config' / 'models.json'
        roles = data.get('roles', {})
        if not roles:
            self._send_json({'error': 'Missing roles data'}, 400)
            return
        try:
            config = json.loads(config_file.read_text())
            config['roles'].update(roles)
            config_file.write_text(json.dumps(config, ensure_ascii=False, indent=2) + '\n')
            self._send_json({'ok': True, 'message': f'Saved {len(roles)} role(s)'})
        except Exception as e:
            self._send_json({'error': str(e)}, 500)

    def _handle_sync_models(self):
        """Run sync-models.py to apply model changes to agents."""
        import subprocess
        sync_script = Path(self.project_root) / 'scripts' / 'sync-models.py'
        try:
            result = subprocess.run(
                [sys.executable, str(sync_script)],
                capture_output=True, text=True, timeout=15, cwd=str(self.project_root)
            )
            self._send_json({'ok': True, 'output': result.stdout.strip() or 'Synced successfully'})
        except FileNotFoundError:
            self._send_json({'error': f'Python not found at {sys.executable}'}, 500)
        except subprocess.TimeoutExpired:
            self._send_json({'error': 'Sync timed out after 15s'}, 500)
        except Exception as e:
            self._send_json({'error': str(e)}, 500)

    def _handle_save_env(self, data):
        """Save API keys to .env file."""
        keys = data.get('keys', {})
        if not keys:
            self._send_json({'error': 'Missing keys data'}, 400)
            return
        try:
            env_file = Path(self.project_root) / '.env'
            self._write_env_file(env_file, keys)
            self._send_json({
                'ok': True,
                'message': f'Saved {len(keys)} key(s). Restart the gateway (bash scripts/start.sh) to apply changes.'
            })
        except Exception as e:
            self._send_json({'error': str(e)}, 500)

    def _config_page(self):
        return CONFIG_HTML


def main():
    parser = argparse.ArgumentParser(description='AI Dev Team Web Dashboard')
    parser.add_argument('--port', type=int, default=8080, help='Server port (default: 8080)')
    parser.add_argument('--project-dir', type=str, default=os.getcwd(),
                        help='Project directory containing projects/ folder')
    parser.add_argument('--verbose', action='store_true', help='Enable request logging')
    args = parser.parse_args()

    projects_dir = Path(args.project_dir) / 'projects'
    DashboardHandler.projects_dir = projects_dir

    server = ThreadingHTTPServer(('0.0.0.0', args.port), DashboardHandler)
    server.verbose = args.verbose

    print(f'AI Dev Team Dashboard')
    print(f'Project dir: {projects_dir}')
    print(f'Open: http://localhost:{args.port}')
    print(f'Press Ctrl+C to stop.')

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\nShutting down.')
        server.shutdown()
    except OSError as e:
        if 'Address already in use' in str(e):
            print(f'Error: Port {args.port} is already in use.')
            print(f'  Try: WEB_PORT={args.port + 1} bash scripts/start.sh')
            sys.exit(1)
        raise


if __name__ == '__main__':
    main()
