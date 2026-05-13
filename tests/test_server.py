"""
Unit tests for MCP Server core — server.py and extended.py.

Run: python3 -m pytest tests/ -v  or  python3 tests/test_server.py
"""

import json
import os
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

# Add project paths so imports work
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'mcp-server'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

# Set a temp project dir so tests don't touch real data
TMP_DIR = Path(tempfile.mkdtemp(prefix='ai-team-test-'))
os.environ['CLAUDE_PROJECT_DIR'] = str(TMP_DIR)

from server import (
    ensure_dirs, load_index, save_index,
    _validate_project_name, _build_company_dashboard,
    _build_project_dashboard, _build_department_dashboard,
    _default_team,
)
from extended import (
    create_sprint, update_sprint, list_sprints,
    log_meeting, list_meetings,
    add_knowledge, search_knowledge,
    create_handoff, list_handoffs, update_handoff,
)
from init_project import init_project, _validate_project_name as _init_validate


class TestProjectNameValidation(unittest.TestCase):
    """Path traversal and injection protection."""

    def test_valid_names(self):
        for name in ['my-project', 'project_v2', 'IoT.App', 'test123']:
            self.assertTrue(_validate_project_name(name), f"Should accept: {name}")

    def test_traversal_rejected(self):
        for name in ['../etc', 'a/b', '..', '.', '/']:
            self.assertFalse(_validate_project_name(name), f"Should reject: {name}")

    def test_special_chars_rejected(self):
        for name in ['proj;rm', '$(whoami)', 'proj|cat', 'a b']:
            self.assertFalse(_validate_project_name(name), f"Should reject: {name}")


class TestIndexOperations(unittest.TestCase):
    """Core index.json read/write."""

    def setUp(self):
        ensure_dirs()
        self.index = load_index()

    def test_default_index_structure(self):
        self.assertIn('projects', self.index)
        self.assertIn('team', self.index)
        self.assertIn('members', self.index['team'])
        self.assertIn('pools', self.index['team'])

    def test_save_and_reload(self):
        self.index['projects']['test-proj'] = {
            'name': 'test-proj',
            'direction': 'ML',
            'overall_progress': 50,
        }
        self.index['updated_at'] = 'test'
        save_index(self.index)
        reloaded = load_index()
        self.assertIn('test-proj', reloaded['projects'])
        self.assertEqual(reloaded['projects']['test-proj']['overall_progress'], 50)

    def test_default_team_has_required_members(self):
        team = _default_team()
        self.assertIn('cto', team['members'])
        self.assertIn('senior_engineer', team['pools'])
        self.assertEqual(team['pools']['senior_engineer']['total'], 12)


class TestDashboardBuilders(unittest.TestCase):
    """Dashboard data aggregation."""

    def setUp(self):
        self.index = {
            'projects': {
                'proj-a': {
                    'name': 'proj-a', 'direction': 'ML',
                    'overall_progress': 80, 'phase': '开发实现',
                    'tech_lead': 'TL-A', 'pm': 'PM-A',
                    'status': '🟢正常', 'start_date': '2026-01-01',
                    'target_date': '2026-06-01', 'blockers': [],
                    'tasks': [
                        {'id': 'T-1', 'status': 'done', 'title': 'Setup'},
                        {'id': 'T-2', 'status': 'in_progress', 'title': 'Build'},
                    ],
                    'reviews': {'DG1': {'R1': {'vote': 'approve'}, 'R2': {'vote': 'approve'}, 'R3': {'vote': 'approve'}}},
                },
                'proj-b': {
                    'name': 'proj-b', 'direction': 'IoT',
                    'overall_progress': 20, 'phase': '方案设计',
                    'tech_lead': 'TL-B', 'pm': 'PM-B',
                    'status': '🔴严重延迟', 'start_date': '2026-02-01',
                    'target_date': '2026-04-01', 'blockers': ['HW delay'],
                    'tasks': [{'id': 'T-3', 'status': 'blocked', 'title': 'Setup HW'}],
                    'reviews': {},
                },
            },
            'team': _default_team(),
        }

    def test_company_dashboard(self):
        dash = _build_company_dashboard(self.index)
        self.assertEqual(dash['stats']['total_projects'], 2)
        self.assertEqual(dash['stats']['at_risk'], ['proj-b'])
        self.assertAlmostEqual(dash['stats']['avg_progress'], 50.0)

    def test_project_dashboard(self):
        dash = _build_project_dashboard(self.index, 'proj-a')
        self.assertEqual(dash['name'], 'proj-a')
        self.assertEqual(len(dash['tasks']['done']), 1)
        self.assertEqual(len(dash['tasks']['in_progress']), 1)

    def test_department_dashboard(self):
        dash = _build_department_dashboard(self.index, 'AI/ML')
        self.assertEqual(dash['total_projects'], 1)
        self.assertEqual(dash['projects'][0]['name'], 'proj-a')


class TestSprintOperations(unittest.TestCase):
    """Sprint CRUD in extended.py."""

    def setUp(self):
        self.project_dir = TMP_DIR / 'test-sprint-proj'
        self.project_dir.mkdir(parents=True, exist_ok=True)

    def test_create_and_list_sprints(self):
        s = create_sprint(self.project_dir, 1, '2026-01-01', '2026-01-07', 'Setup infra')
        self.assertEqual(s['sprint_num'], 1)
        self.assertEqual(s['goal'], 'Setup infra')
        self.assertEqual(s['status'], 'active')

        sprints = list_sprints(self.project_dir)
        self.assertEqual(len(sprints), 1)

    def test_update_sprint(self):
        create_sprint(self.project_dir, 1, '2026-01-01', '2026-01-07', 'Goal')
        updated = update_sprint(self.project_dir, 1, status='completed', completed_points=13)
        self.assertEqual(updated['status'], 'completed')
        self.assertEqual(updated['completed_points'], 13)

    def test_update_nonexistent_sprint(self):
        result = update_sprint(self.project_dir, 99)
        self.assertIn('error', result)

    def test_burndown_tracking(self):
        create_sprint(self.project_dir, 1, '2026-01-01', '2026-01-07')
        updated = update_sprint(self.project_dir, 1, burndown_point=20)
        self.assertEqual(len(updated['burndown']), 1)
        self.assertEqual(updated['burndown'][0]['remaining'], 20)


class TestMeetingOperations(unittest.TestCase):
    """Meeting notes in extended.py."""

    def setUp(self):
        self.project_dir = TMP_DIR / 'test-meeting-proj'
        if self.project_dir.exists():
            import shutil
            shutil.rmtree(self.project_dir)
        self.project_dir.mkdir(parents=True, exist_ok=True)

    def test_log_and_list_meetings(self):
        m = log_meeting(self.project_dir, 'standup', 'Daily sync',
                        decisions=['P0 first'], action_items=['Fix auth'],
                        attendees=['TL-A', 'SE-1'])
        self.assertEqual(m['type'], 'standup')
        self.assertEqual(len(m['decisions']), 1)

        meetings = list_meetings(self.project_dir)
        self.assertEqual(len(meetings), 1)

    def test_filter_by_type(self):
        log_meeting(self.project_dir, 'standup', 'Standup 1')
        log_meeting(self.project_dir, 'planning', 'Sprint plan')
        standups = list_meetings(self.project_dir, 'standup')
        self.assertEqual(len(standups), 1)


class TestKnowledgeBase(unittest.TestCase):
    """Knowledge base operations."""

    def setUp(self):
        self.project_dir = TMP_DIR / 'test-kb-proj'
        self.project_dir.mkdir(parents=True, exist_ok=True)
        # Clean KB file
        kb_file = self.project_dir / '.knowledge_base.json'
        if kb_file.exists():
            kb_file.unlink()

    def test_add_and_search(self):
        add_knowledge(self.project_dir, 'Python tips',
                      'Use dataclasses for DTOs',
                      tags=['python', 'best-practice'],
                      author='SE-1')
        add_knowledge(self.project_dir, 'Go patterns',
                      'Use interfaces for testing',
                      tags=['go', 'testing'])

        results = search_knowledge(self.project_dir, query='dataclasses')
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['topic'], 'Python tips')

    def test_search_by_tags(self):
        add_knowledge(self.project_dir, 'Topic A', 'Content A', tags=['ml'])
        add_knowledge(self.project_dir, 'Topic B', 'Content B', tags=['iot'])

        results = search_knowledge(self.project_dir, tags=['ml'])
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['topic'], 'Topic A')

    def test_empty_search_returns_nothing(self):
        add_knowledge(self.project_dir, 'Topic', 'Content', tags=['test'])
        results = search_knowledge(self.project_dir)
        self.assertEqual(len(results), 0)  # No query, no tags → no results


class TestHandoffOperations(unittest.TestCase):
    """Cross-role handoff mechanism."""

    def setUp(self):
        self.project_dir = TMP_DIR / 'test-handoff-proj'
        if self.project_dir.exists():
            import shutil
            shutil.rmtree(self.project_dir)
        self.project_dir.mkdir(parents=True, exist_ok=True)

    def test_create_and_list_handoffs(self):
        h = create_handoff(self.project_dir, 'PM', 'TL',
                           'PRD for auth module',
                           deliverable='prd.md',
                           acceptance_criteria=['All user stories covered'])
        self.assertEqual(h['from'], 'PM')
        self.assertEqual(h['to'], 'TL')
        self.assertEqual(h['status'], 'pending')

        handoffs = list_handoffs(self.project_dir)
        self.assertEqual(len(handoffs), 1)

    def test_accept_handoff(self):
        create_handoff(self.project_dir, 'TL', 'Senior Engineer',
                       'Implement auth API', deliverable='tech-spec.md')
        result = update_handoff(self.project_dir, 'HANDOFF-001', status='accepted')
        self.assertEqual(result['status'], 'accepted')
        self.assertIsNotNone(result['resolved_at'])

    def test_reject_with_note(self):
        create_handoff(self.project_dir, 'Designer', 'TL', 'Design spec')
        result = update_handoff(self.project_dir, 'HANDOFF-001',
                                status='rejected', note='Missing responsive specs')
        self.assertEqual(result['status'], 'rejected')
        self.assertEqual(len(result['notes']), 1)

    def test_filter_by_status(self):
        create_handoff(self.project_dir, 'PM', 'TL', 'PRD')
        update_handoff(self.project_dir, 'HANDOFF-001', status='accepted')
        create_handoff(self.project_dir, 'TL', 'SE', 'Tech spec')

        pending = list_handoffs(self.project_dir, status='pending')
        accepted = list_handoffs(self.project_dir, status='accepted')
        self.assertEqual(len(pending), 1)
        self.assertEqual(len(accepted), 1)


class TestProjectInit(unittest.TestCase):
    """Project template initialization."""

    def setUp(self):
        self.project_name = 'test-init-' + datetime.now().strftime('%H%M%S')
        # Create minimal templates in the temp project dir so init works
        templates_dir = Path(os.environ['CLAUDE_PROJECT_DIR']) / 'templates' / 'projects'
        templates_dir.mkdir(parents=True, exist_ok=True)
        for tpl in ['prd-template.md', 'tech-spec-template.md', 'test-plan-template.md']:
            tpl_file = templates_dir / tpl
            if not tpl_file.exists():
                tpl_file.write_text('# {{PROJECT_NAME}}\n\nTemplate for {{PROJECT_NAME}}\nDate: {{DATE}}\n')

    def test_init_creates_all_files(self):
        result = init_project(self.project_name, 'ML', 'Test project',
                              pm='PM-A', tl='TL-A', target_date='2026-12-31')
        self.assertTrue(result.get('success'), f"Init failed: {result}")
        self.assertIn('README.md', result['files_created'])

    def test_rejects_invalid_name(self):
        result = init_project('bad/name', 'ML', 'Test')
        self.assertIn('error', result)

    def test_rejects_duplicate(self):
        name = 'dup-' + datetime.now().strftime('%H%M%S')
        init_project(name, 'ML', 'First')
        result = init_project(name, 'ML', 'Second')
        self.assertIn('error', result)
        self.assertIn('already exists', result['error'])


if __name__ == '__main__':
    # Clean test dir after run
    import shutil
    try:
        unittest.main(verbosity=2, exit=False)
    finally:
        if TMP_DIR.exists():
            shutil.rmtree(TMP_DIR)
            print(f"\nCleaned up: {TMP_DIR}")
