---
name: project
description: Project lifecycle management — create new projects, update status, manage tasks, and track progress.
when_to_use: When creating a new project, updating project status, or managing project lifecycle operations.
argument-hint: "[new|status|update|close] [project-name]"
user-invocable: true
allowed-tools: Read, Write, Edit, Bash, Glob, TaskCreate, TaskUpdate, mcp__ai-team-db__create_project, mcp__ai-team-db__get_project, mcp__ai-team-db__update_project_status, mcp__ai-team-db__list_projects
model: sonnet
effort: medium
---

# Project Management

You manage the project lifecycle from creation to delivery.

## Usage

- `/project new <name>` — Initialize a new project
- `/project status <name>` — Show current project status
- `/project update <name>` — Update project status
- `/project close <name>` — Close a completed project

## Project Creation

When creating a new project, initialize the structure:

```bash
mkdir -p projects/<project-name>/reviews
```

Create these files:
1. `projects/<project-name>/README.md` — Project overview
2. `projects/<project-name>/status.md` — Current status (initialized to "需求分析" phase)
3. `projects/<project-name>/tasks.md` — Empty task board

## Status File Format

`projects/<project-name>/status.md`:
```markdown
# [项目名称] — 状态

**最后更新**: YYYY-MM-DD
**更新人**: [角色]

## 基本信息
- 方向: ML / IoT / Agent / App&Web
- Tech Lead: [TL名称]
- 团队规模: N人
- 开始日期: YYYY-MM-DD
- 预计交付: YYYY-MM-DD

## 当前阶段
- 阶段: 需求分析 / 方案设计 / 开发实现 / 测试评审 / 交付验收
- 阶段进度: X%
- 进入日期: YYYY-MM-DD

## 整体进度
- 完成度: X%
- 状态: 🟢正常 / 🟡有风险 / 🔴严重延迟

## 当前阻塞
- [ ] ...

## 本周完成
- [x] ...

## 下周计划
- [ ] ...

## 评审历史
| 门禁 | 日期 | 结果 | 详情 |
|------|------|------|------|
```

## Task File Format

`projects/<project-name>/tasks.md`:
```markdown
# [项目名称] — 任务面板

## 🔴 Blocked
| ID | 任务 | 负责人 | 阻塞原因 | 阻塞天数 |
|----|------|--------|----------|----------|

## 🟡 In Progress
| ID | 任务 | 负责人 | 预计完成 | 优先级 |
|----|------|--------|----------|--------|

## 🔵 Todo
| ID | 任务 | 负责人 | 预计工时 | 优先级 |
|----|------|--------|----------|--------|

## 🟢 Done
| ID | 任务 | 负责人 | 完成日期 |
|----|------|--------|----------|
```
