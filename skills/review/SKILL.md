---
name: review
description: Invoke the independent Review Board — 3 reviewers independently assess project deliverables at stage gates, majority vote required to pass.
when_to_use: When a project reaches a stage gate (DG1-DG4) and needs independent review. Also use for ad-hoc quality audits.
argument-hint: "[project-name] [gate: dg1|dg2|dg3|dg4]"
user-invocable: true
allowed-tools: Read, Write, Edit, Bash, Agent, WebFetch, WebSearch, mcp__ai-team-db__get_project, mcp__ai-team-db__get_review, mcp__ai-team-db__create_review
context: fork
model: opus
effort: high
---

# Review Board — 独立评审团

You orchestrate the independent Review Board. You do NOT review anything yourself. Instead, you spawn 3 independent reviewer agents (R1, R2, R3) in parallel, collect their individual votes, and render the final decision.

## Process (MANDATORY — follow exactly)

### Step 1: Gather Materials
Use `mcp__ai-team-db__get_project(project_name="<name>")` to get project state. Read the relevant project files (PRD, Tech Spec, status, tasks) to prepare a review brief.

### Step 2: Spawn 3 Independent Reviewers IN PARALLEL

You MUST spawn all 3 agents simultaneously in a single message — they must NOT see each other's work.

- Spawn `reviewer-r1` agent — Architecture Expert
- Spawn `reviewer-r2` agent — Product Quality Expert
- Spawn `reviewer-r3` agent — Engineering Efficiency Expert

Each agent's prompt must include:
- The gate being reviewed (DG1/DG2/DG3/DG4)
- The project name
- A summary of the materials to review
- The instruction: "Return your review as JSON with: vote, overall_score, dimensions (name→score mapping), findings (list), recommendations (list). Vote MUST be one of: approve, changes_requested, reject."

Use `run_in_background: false` and send all 3 Agent calls in ONE message for true parallel isolation.

### Step 3: Tabulate Results
Once all 3 reviewers return:

```
Vote tally: ✅ approve: X, 🔄 changes_requested: Y, ❌ reject: Z
```

Decision rule:
- ≥2 `approve` → **PASS** — project proceeds to next phase
- ≥2 `reject` → **REJECT** — project returns to phase start
- ≥2 `changes_requested` → **CHANGES REQUIRED** — fix and re-submit (no phase reset)
- 1 each → tie goes to **CHANGES REQUIRED** (conservative)

### Step 4: Record Votes
For EACH reviewer, call `mcp__ai-team-db__create_review`:
```
project_name="<project>"
gate="<DG1/DG2/DG3/DG4>"
reviewer="R1" / "R2" / "R3"
vote="approve" / "changes_requested" / "reject"
score=<overall_score>
findings=[...]
recommendations=[...]
```

### Step 5: Announce Decision
Render the review report in the format below.

## Output Format

```markdown
# Review Report — [Project] — [Gate]

**Date**: YYYY-MM-DD
**Decision**: ✅ PASS / 🔄 CHANGES REQUIRED / ❌ REJECT

## R1: Architecture Expert
**Vote**: ✅/🔄/❌ | **Score**: X.X/10
**Key Findings**: ...
**Recommendations**: ...

## R2: Product Quality Expert
**Vote**: ✅/🔄/❌ | **Score**: X.X/10
**Key Findings**: ...
**Recommendations**: ...

## R3: Engineering Efficiency Expert
**Vote**: ✅/🔄/❌ | **Score**: X.X/10
**Key Findings**: ...
**Recommendations**: ...

## Vote Summary
| Reviewer | Vote | Score |
|----------|------|-------|
| R1 (Architecture) | ✅/🔄/❌ | X.X |
| R2 (Product) | ✅/🔄/❌ | X.X |
| R3 (Engineering) | ✅/🔄/❌ | X.X |

**Result**: ✅ X | 🔄 Y | ❌ Z → [FINAL DECISION]

## Action Items
1. ...
```

## Important Rules
- You are the ORCHESTRATOR, not a reviewer. Only R1/R2/R3 agents produce reviews.
- Spawn all 3 agents in ONE parallel message — reviewers MUST be isolated.
- If any agent fails or times out, that counts as a ❌ reject vote (fail-safe).
- Never bypass gates — no exceptions, no shortcuts.
