# CLAUDE.md

This file provides guidance to Claude Code when working with code in this repository.

## Overview

This is an AI-powered development team plugin (`ai-dev-team`) v0.3.0 — a complete 33-person software organization that runs inside Claude Code. The human stakeholder provides requirements and accepts deliverables; the AI team self-organizes to execute.

**Product scope**: ML algorithms, IoT applications, Agent/Knowledge Base, App & Web.

## Model Configuration

Edit `config/models.json` to assign models per role, then sync:

```bash
python3 scripts/sync-models.py            # apply changes
python3 scripts/sync-models.py --dry-run  # preview only
```

Available models: `opus` (strongest reasoning), `sonnet` (cost-effective), `haiku` (fastest), `inherit` (no overhead, uses caller's model).

## Quick Start

```bash
# Install MCP dependencies
pip install -r mcp-server/requirements.txt

# Test plugin locally
claude --plugin-dir .

# Install permanently
claude plugin install --scope user .
```

## Plugin Architecture

| Component | Path | What It Does |
|-----------|------|--------------|
| **11 Skills** | `skills/` | Slash commands: `/cto` `/pm` `/tech-lead` `/designer` `/review` `/dashboard` `/project` `/pipeline` `/market` `/devops` |
| **10 Agents** | `agents/` | Subagent definitions: cto, pm, tech-lead, senior-engineer, designer (×1), reviewer-r1/r2/r3, devops, market-manager |
| **MCP Server** | `mcp-server/` | 23 tools: project CRUD, tasks, reviews, sprints, meetings, knowledge base, reports, dashboard, handoffs |
| **Hooks** | `hooks/` | Quality gates, analytics alerts, auto-collection, session init |
| **Monitors** | `monitors/` | Dashboard refresh, deadline tracking |
| **Analytics** | `scripts/` | Velocity, quality, cycle time metrics + predictive alerts |
| **Reports** | `scripts/reports.py` | Daily standup, weekly status, sprint retro auto-generation |
| **Templates** | `templates/` | PRD, Tech Spec, Test Plan, CI/CD (GitHub Actions, Docker) |
| **Docs** | `docs/` | 8 documents covering org structure, roles, workflows, reviews, permissions |

## Stakeholder Commands

| Command | Purpose |
|---------|---------|
| `/pipeline start <name>` | Full automation: intake→market research→PRD→architecture→planning→dev→quality→delivery |
| `/pipeline resume <name>` | Resume interrupted pipeline from last completed phase |
| `/pipeline status <name>` | Check pipeline progress |
| `/dashboard company` | All projects at a glance |
| `/dashboard project <name>` | Single project details + review status |
| `/project new <name>` | Submit new requirement → auto-initializes with templates |
| `/review <project> <gate>` | Trigger independent 3-person review |
| `/cto <directive>` | Direct CTO technical decision |
| `/architect <standards\|review\|adr>` | Technology standards governance, pre-DG1 architecture review |
| `/pm <direction>` | Product requirements analysis |
| `/devops ci <project>` | Set up CI/CD pipeline for project |

## AI Team Workflow

### Automated Pipeline (recommended)

`/pipeline start <project>` runs all 7 phases without manual intervention:

1. Intake → CTO creates project, assigns PM
2. Market Research → Market Manager analyzes competitors, produces competitive matrix
3. Requirements → PM writes PRD informed by market research
4. Architecture → Architect reviews tech choices against `config/tech-standards.json`
5. Planning → Tech Lead designs spec, breaks down tasks
6. Development → Engineers implement tasks (git branch → code → commit → merge)
7. Quality → DG1→DG2→DG3→DG4 gate reviews (3 independent reviewers per gate)
8. Delivery → Final report, stakeholder handoff

Pipeline state is saved to `projects/<name>/.pipeline-state.json` — resume with `/pipeline resume <name>`.

### Web Dashboard + Model Gateway

```bash
bash scripts/start.sh
# Opens http://localhost:8080 (dashboard) + http://localhost:4000 (model gateway)
# Model config UI: http://localhost:8080/config
# Start Claude Code: ANTHROPIC_BASE_URL=http://localhost:4000 claude --plugin-dir .
```

### Manual Workflow

## Organization (33 people, 10 Agent types)

- **Management (Agents)**: CTO, PM×3, Market Manager (5)
- **Execution (Agents)**: Tech Lead×3, Senior Engineer×12, Domain Engineer×6 (ML/IoT/Agent), Designer×4 (25)
- **Operations (Agents)**: DevOps/SRE×2 (2)
- **Governance (Agents)**: Independent Reviewer R1/R2/R3 (3) — spawned in parallel, truly isolated
- **Sub-leads**: ML专业组长, Agent专业组长, 嵌入式专业组长, 前端专业组长

## MCP Server Tools (27 total)

**Core (12)**: list_projects, get_project, create_project, update_project_status, create_task (with file ownership & conflict detection), update_task, list_tasks, create_review, get_review, get_dashboard, update_team_member, list_team

**Extended (15)**: create_sprint, update_sprint, list_sprints, log_meeting, list_meetings, add_knowledge, search_knowledge, generate_report, create_handoff, list_handoffs, update_handoff, git_create_branch, git_commit, git_get_status, git_merge_branch

## Cross-Role Handoff

Formal handoffs between roles/departments via MCP tools: `create_handoff` (records from_role→to_role, deliverable, acceptance criteria), `update_handoff` (accept/reject with notes), `list_handoffs` (filter by pending/accepted/rejected). Handoffs stored per-project in `.handoffs/`.

## Designer + Figma

Designer has full Figma MCP access (`use_figma`, `search_design_system`, `get_design_context`, etc.) to draw UI directly in Figma. Design tokens live in `design-system/tokens.json` and in Figma variables. Fallback: markdown Design Spec.

## Review System

3 truly independent reviewer agents spawned in parallel (context: fork). Each has its own node, scoring rubric, and vote. ≥2/3 votes to pass.

- **R1** (`reviewer-r1`): Architecture Expert — technical rationality, scalability, security
- **R2** (`reviewer-r2`): Product Quality Expert — requirements conformance, UX, completeness
- **R3** (`reviewer-r3`): Engineering Efficiency Expert — code quality, tests, maintainability, risk

| Gate | Trigger | Pass Threshold | Rubric |
|------|---------|---------------|--------|
| DG1 | Design complete | ≥6.0/10 | Architecture, UX, Task decomposition |
| DG2 | Core dev done | ≥7.0/10 | Code quality, Design fidelity, Tests |
| DG3 | QA complete | ≥7.5/10 | Performance, Security, Bug rate |
| DG4 | Ready for delivery | ≥8.0/10 | Deployment, Docs, AC compliance |

Full rubrics: `docs/review-rubric.md`

## Key Documents

| Document | Content |
|----------|---------|
| `docs/org-structure-v2.md` | Complete org chart with departments, sub-leads, DevOps |
| `docs/roles.md` | All role definitions and responsibilities |
| `docs/workflows.md` | 5-stage development workflow |
| `docs/review-process.md` | Review board process and voting |
| `docs/review-rubric.md` | Detailed 3-reviewer scoring rubrics per gate |
| `docs/review-template.md` | Standardized review record template |
| `docs/permissions.md` | Role-based permission matrix |
| `docs/deployment-runbook.md` | Deployment operations template |

## Scripts

| Script | Purpose |
|--------|---------|
| `scripts/init_project.py` | Auto-initialize new project with all templates |
| `scripts/collect-dashboard.py` | Aggregate dashboard data (prefers .index.json, falls back to parsing .md files). Also generates dashboards/*.md |
| `scripts/web_dashboard.py` | Web-based real-time dashboard (stdlib http.server, port 8080, reads .index.json and .pipeline-state.json) |
| `scripts/analytics.py` | Velocity, quality, cycle time + predictive alerts (reads .index.json directly) |
| `scripts/reports.py` | Daily standup, weekly report, sprint retro |
| `scripts/sync-models.py` | Sync config/models.json → agents/*.md frontmatter |

## Project Data Structure

```
projects/<name>/
├── README.md              # Auto-generated overview
├── intake-brief.md        # CTO intake brief (pipeline Phase 0 output)
├── market-research.md     # Competitive analysis (pipeline Phase 1 output)
├── prd.md                 # PM fills from template (informed by market research)
├── architecture-review.md # Architect compliance report
├── tech-spec.md           # TL technical spec + task breakdown
├── test-plan.md           # Test plan from template
├── tasks.md               # Task board (MCP-synced)
├── status.md              # Status (MCP-synced)
├── delivery-report.md     # Pipeline delivery report
├── .pipeline-state.json   # Pipeline progress (for resume)
├── reviews/               # DG1-DG4 review records
├── .sprints/              # Sprint data (JSON)
└── .meetings/             # Meeting notes (JSON)
```
