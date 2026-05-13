---
name: dashboard
description: Display multi-level dashboards — Company (all projects), Department (team view), or Project (task tracking). The central visibility tool for the entire organization.
when_to_use: When you need to see project status, team workload, milestones, or any organizational overview. Use at start of sessions or when checking progress.
argument-hint: "[company|department <name>|project <name>]"
user-invocable: true
allowed-tools: Read, Write, Edit, Bash, Glob, Grep, mcp__ai-team-db__get_dashboard, mcp__ai-team-db__list_projects, mcp__ai-team-db__get_project, mcp__ai-team-db__list_team
model: sonnet
effort: medium
---

# Dashboard System

You provide real-time visibility into the entire organization at three levels.

## Usage

- `/dashboard company` — Overall company view
- `/dashboard department <name>` — Department-level view (AI/ML, IoT, App&Web)
- `/dashboard project <name>` — Single project detailed view
- `/dashboard` (no args) — Show all three levels summarized

## Data Sources (priority order)

1. **MCP Server** (primary): Call `mcp__ai-team-db__get_dashboard` for structured, real-time data
2. **MCP Tools**: `mcp__ai-team-db__list_projects`, `mcp__ai-team-db__get_project`, `mcp__ai-team-db__list_team` for specific queries
3. **File fallback**: Read `projects/.index.json` directly if MCP is unavailable
4. **Markdown fallback**: Parse `projects/*/status.md` files as last resort

## Company Dashboard

Always use MCP first: `mcp__ai-team-db__get_dashboard(level="company")`

```markdown
# 🏢 公司 Dashboard — YYYY-MM-DD

## 活跃项目总览
| 项目 | 方向 | 进度 | 阶段 | Tech Lead | 起止时间 | 状态 |
|------|------|------|------|-----------|----------|------|
{{from MCP: projects list}}

## 统计
- 总项目: N | 活跃: N | 有风险: N | 严重延迟: N
- 平均进度: X%

## 团队资源总览
| 角色 | 总数 | 已分配 | 空闲 | 利用率 |
|------|------|--------|------|--------|
{{from MCP: team pools}}

## 近期里程碑
| 日期 | 项目 | 里程碑 | 类型 |
|------|------|--------|------|
{{from project statuses}}

## 风险告警 🔴
{{from MCP: at_risk and delayed projects}}

## 评审团活跃度
{{from MCP: review data}}
```

## Project Dashboard

Always use MCP first: `mcp__ai-team-db__get_dashboard(level="project", name="<project>")`

```markdown
# 📊 [项目名称] Dashboard

## 基本信息
- **方向**: {{direction}} | **Tech Lead**: {{tl}} | **PM**: {{pm}}
- **时间**: {{start}} ~ {{target}}
- **当前阶段**: {{phase}} ({{phase_progress}}%)
- **整体进度**: ████████░░ {{overall_progress}}%
- **状态**: {{status}}

## 阶段评审状态
| 门禁 | 状态 | R1 | R2 | R3 | 结果 |
|------|------|-----|-----|-----|------|
{{from MCP: reviews object}}

## 任务面板
### 🔴 Blocked ({{blocked_count}})
{{from MCP: tasks with status=blocked}}

### 🟡 In Progress ({{in_progress_count}})
{{from MCP: tasks with status=in_progress}}

### 🔵 Todo ({{todo_count}})
{{from MCP: tasks with status=todo}}

### 🟢 Done (本周)
{{from MCP: tasks with status=done}}

## 团队负载
{{from MCP: team member load per project}}
```

## Department Dashboard

Use MCP: `mcp__ai-team-db__get_dashboard(level="department", name="<dept>")`

Depts: AI/ML (ML+Agent projects), IoT, App&Web

## Data Freshness

- MCP data is always current (fetched from `.index.json` in real-time)
- If MCP returns `generated_at` older than 1 day, trigger `scripts/collect-dashboard.py`
- If MCP is unavailable, fall back to file parsing with a warning: "⚠️ MCP不可用，使用文件数据"
- Flag any `status.md` that hasn't been updated in 3+ days
