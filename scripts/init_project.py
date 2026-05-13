#!/usr/bin/env python3
"""
Project Initializer — Automates the creation of a new project with all templates.
Triggered by MCP create_project or by the /project new command.
"""

import os
import re
import sys
from datetime import datetime
from pathlib import Path

PROJECT_DIR = Path(os.environ.get('CLAUDE_PROJECT_DIR', os.getcwd()))
TEMPLATES_DIR = PROJECT_DIR / 'templates' / 'projects'
SAFE_NAME_RE = re.compile(r'^[a-zA-Z0-9_\-.]+$')


def _validate_project_name(name: str) -> bool:
    return bool(SAFE_NAME_RE.match(name)) and '..' not in name and '/' not in name


def init_project(name: str, direction: str, description: str, pm: str = '', tl: str = '', target_date: str = '') -> dict:
    """Initialize a complete project structure with templates."""

    if not _validate_project_name(name):
        return {'error': f'Invalid project name: use only letters, numbers, hyphens, underscores, dots'}

    project_path = PROJECT_DIR / 'projects' / name
    if project_path.exists():
        return {'error': f'Project {name} already exists at {project_path}'}

    # Create directories
    (project_path / 'reviews').mkdir(parents=True, exist_ok=True)

    date = datetime.now().strftime('%Y-%m-%d')

    # 1. README.md
    readme = f"""# {name}

**方向**: {direction}
**PM**: {pm} | **Tech Lead**: {tl}
**创建**: {date} | **预计交付**: {target_date}

## 概述
{description}

## 状态
- 阶段: 需求分析
- 进度: 0%
- 状态: 🟢正常

## 团队
- PM: {pm}
- TL: {tl}
- 成员: (待分配)

## 文档索引
- [PRD](prd.md)
- [技术方案](tech-spec.md)
- [任务面板](tasks.md)
- [测试计划](test-plan.md)

## 评审历史
| 门禁 | 状态 | 日期 | 结果 |
|------|------|------|------|
| DG1 | ⏳未开始 | — | — |
| DG2 | ⏳未开始 | — | — |
| DG3 | ⏳未开始 | — | — |
| DG4 | ⏳未开始 | — | — |
"""
    (project_path / 'README.md').write_text(readme, encoding='utf-8')

    # 2. PRD (from template)
    prd_template = TEMPLATES_DIR / 'prd-template.md'
    if prd_template.exists():
        prd = prd_template.read_text(encoding='utf-8')
        prd = prd.replace('{{PROJECT_NAME}}', name)
        prd = prd.replace('{{PM_NAME}}', pm or '待分配')
        prd = prd.replace('{{DATE}}', date)
        (project_path / 'prd.md').write_text(prd, encoding='utf-8')

    # 3. Tech Spec (from template, empty)
    ts_template = TEMPLATES_DIR / 'tech-spec-template.md'
    if ts_template.exists():
        ts = ts_template.read_text(encoding='utf-8')
        ts = ts.replace('{{PROJECT_NAME}}', name)
        ts = ts.replace('{{TL_NAME}}', tl or '待分配')
        ts = ts.replace('{{DATE}}', date)
        (project_path / 'tech-spec.md').write_text(ts, encoding='utf-8')

    # 4. Test Plan (from template)
    tp_template = TEMPLATES_DIR / 'test-plan-template.md'
    if tp_template.exists():
        tp = tp_template.read_text(encoding='utf-8')
        tp = tp.replace('{{PROJECT_NAME}}', name)
        tp = tp.replace('{{QA_NAME}}', '待分配')
        tp = tp.replace('{{DATE}}', date)
        (project_path / 'test-plan.md').write_text(tp, encoding='utf-8')

    # 5. Status file
    status = f"""# {name} — 状态

**最后更新**: {datetime.now().strftime('%Y-%m-%d %H:%M')}

## 基本信息
- 方向: {direction}
- Tech Lead: {tl or 'Unassigned'}
- PM: {pm or 'Unassigned'}
- 开始日期: {date}
- 预计交付: {target_date}

## 当前阶段
- 阶段: 需求分析
- 阶段进度: 0%

## 整体进度
- 完成度: 0%
- 状态: 🟢正常

## 当前阻塞
(暂无)

## 本周完成
(暂无)

## 下周计划
- [ ] PM完成PRD初稿
"""
    (project_path / 'status.md').write_text(status, encoding='utf-8')

    # 6. Empty tasks
    tasks = """# 任务面板

## 🔴 Blocked
(暂无)

## 🟡 In Progress
(暂无)

## 🔵 Todo
(待PM和TL分解任务)

## 🟢 Done
(暂无)
"""
    (project_path / 'tasks.md').write_text(tasks, encoding='utf-8')

    return {
        'success': True,
        'project': name,
        'path': str(project_path),
        'files_created': [
            'README.md', 'prd.md', 'tech-spec.md',
            'test-plan.md', 'status.md', 'tasks.md'
        ],
        'next_steps': [
            f'PM ({pm or "待分配"}) 填写PRD: projects/{name}/prd.md',
            f'TL ({tl or "待分配"}) 准备技术方案: projects/{name}/tech-spec.md',
        ]
    }


if __name__ == '__main__':
    if len(sys.argv) < 3:
        print("Usage: init_project.py <name> <direction> [pm] [tl] [target_date]")
        sys.exit(1)

    result = init_project(
        name=sys.argv[1],
        direction=sys.argv[2],
        description=sys.argv[3] if len(sys.argv) > 3 else '',
        pm=sys.argv[4] if len(sys.argv) > 4 else '',
        tl=sys.argv[5] if len(sys.argv) > 5 else '',
        target_date=sys.argv[6] if len(sys.argv) > 6 else '',
    )
    import json
    print(json.dumps(result, ensure_ascii=False, indent=2))
