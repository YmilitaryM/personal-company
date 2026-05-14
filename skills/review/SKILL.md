---
name: review
description: Invoke the independent Review Board — 3 reviewers independently assess, then debate and cross-examine each other's findings, then produce a synthesized final verdict. Majority vote required to pass.
when_to_use: When a project reaches a stage gate (DG1-DG4) and needs independent review. Also use for ad-hoc quality audits.
argument-hint: "[project-name] [gate: dg1|dg2|dg3|dg4]"
user-invocable: true
allowed-tools: Read, Write, Edit, Bash, Agent, WebFetch, WebSearch, mcp__ai-team-db__get_project, mcp__ai-team-db__get_review, mcp__ai-team-db__create_review
context: fork
model: opus
effort: high
---

# Review Board — 独立评审 + 交叉辩论 + 合议裁决

You orchestrate a three-round review process. Quality comes from SYNTHESIS of perspectives, not just the sum of individual reviews.

## The Three Rounds

```
Round 1: 独立评审  — R1/R2/R3 review independently in parallel (isolated)
Round 2: 交叉辩论  — Reviewers see each other's findings, challenge and debate
Round 3: 合议裁决  — Revised final scores, consensus areas, dissenting opinions
```

**Why debate matters**: Without cross-examination, each reviewer only catches what their specialty notices. An architecture flaw might have product implications R2 would spot. An engineering shortcut R3 approves might create tech debt R1 would flag. Debate surfaces these intersections — the quality comes from the COLLISION of perspectives.

## Process (MANDATORY — follow exactly)

### Round 1: Independent Review (并行独立评审)

**Step 1.1 — Gather Materials**
Use `mcp__ai-team-db__get_project(project_name="<name>")` to get project state. Read the relevant project files (PRD, Tech Spec, status, tasks) to prepare a review brief.

**Step 1.2 — Spawn 3 Reviewers IN PARALLEL**
Spawn `reviewer-r1`, `reviewer-r2`, `reviewer-r3` simultaneously in ONE message. They must NOT see each other's work.

Each reviewer's prompt MUST include:
- Gate being reviewed (DG1/DG2/DG3/DG4) and what that gate evaluates
- Project name and summary of materials
- Instruction: "Review ALL aspects of the project (not just your specialty), but weigh your specialty more heavily. For each dimension, assign a score (0-10) with specific evidence. Return JSON with: vote (approve/changes_requested/reject), overall_score, dimensions (name→{score, evidence}), findings (list of {finding, severity, evidence}), recommendations (list)."

Use `run_in_background: false` — send all 3 Agent calls in ONE message.

**Step 1.3 — Collect Round 1 Results**
Once all 3 return, compile their findings into a Round 1 Summary. Do NOT announce results yet.

### Round 2: Cross-Examination Debate (交叉辩论)

**Step 2.1 — Prepare Debate Brief**
Combine all three Round 1 reviews into a single debate brief:

```
Round 1 Results — All Three Reviewers:

=== R1 (Architecture) ===
Vote: X, Overall Score: X.X
Findings: [list each with severity and evidence]
Recommendations: [list each]

=== R2 (Product Quality) ===
Vote: X, Overall Score: X.X
Findings: [list each with severity and evidence]
Recommendations: [list each]

=== R3 (Engineering Efficiency) ===
Vote: X, Overall Score: X.X
Findings: [list each with severity and evidence]
Recommendations: [list each]
```

**Step 2.2 — Cross-Examination Rules**
Spawn all 3 reviewers AGAIN in parallel. Each receives the FULL debate brief and is told:

```
You are in a CROSS-EXAMINATION debate. You have read all three Round 1 reviews.

Your job as <R1/R2/R3>:

1. CHALLENGE at least one finding from each other reviewer:
   - Where do you DISAGREE with their assessment? Why?
   - What did they OVERLOOK that your specialty catches?
   - What did they flag as CRITICAL that you think is MINOR?

2. IDENTIFY CONFLICTS between perspectives:
   - Does R1's architecture recommendation conflict with R3's engineering approach?
   - Does R2's product requirement create technical debt R1 would reject?
   - Does R3's implementation shortcut undermine R1's architecture integrity?

3. ACKNOWLEDGE what others caught that you MISSED:
   - What did another reviewer find that you didn't notice?
   - Should you revise your own score based on their findings?

4. DEFEND or CONCEDE your own findings:
   - For each of your findings that others challenge, either:
     a) DEFEND with stronger evidence, or
     b) CONCEDE and explain why you were wrong

Return JSON:
{
  "challenges_to_R1": [{"finding": "...", "challenge": "...", "severity_change": "up/down/same"}],
  "challenges_to_R2": [...],
  "challenges_to_R3": [...],
  "conflicts_identified": [{"perspectives": ["R1", "R3"], "issue": "...", "resolution_suggestion": "..."}],
  "findings_i_missed": ["...", "..."],
  "my_concessions": [{"finding": "...", "reason": "..."}],
  "my_defenses": [{"finding": "...", "defense": "..."}],
  "revised_vote": "approve/changes_requested/reject",
  "revised_overall_score": X.X,
  "debate_summary": "1-2 sentence synthesis of what the debate revealed"
}
```

### Round 3: Synthesis & Final Verdict (合议裁决)

**Step 3.1 — Synthesize**
Read all three debate responses. Produce the final verdict:

**Areas of Consensus** (all three agree):
- Findings where all reviewers converge — these are the most reliable insights

**Areas of Dissent** (disagreement remains):
- Findings where reviewers disagreed even after debate — document both sides with rationale
- These are areas of genuine uncertainty that may need stakeholder input

**Conflict Resolution**:
- For each conflict identified in debate, state how it was resolved (or why it remains unresolved)

**Revised Scores**:
- Use each reviewer's FINAL scores (after debate) — not their Round 1 scores
- If a reviewer changed their vote, note the change and why

**Step 3.2 — Decision**
Tabulate FINAL (Round 2 revised) votes:
- ≥2 `approve` → **PASS**
- ≥2 `reject` → **REJECT**
- ≥2 `changes_requested` → **CHANGES REQUIRED**
- 1 each → tie → **CHANGES REQUIRED**

**Step 3.3 — Record**
Call `mcp__ai-team-db__create_review` for each reviewer with their FINAL scores and full debate record.

## Output Format

```markdown
# Review Report — [Project] — [Gate]

**Date**: YYYY-MM-DD
**Decision**: ✅ PASS / 🔄 CHANGES REQUIRED / ❌ REJECT

---

## Round 1: Independent Reviews

### R1: Architecture Expert
**Vote**: X | **Score**: X.X/10
| Dimension | Score | Evidence |
|-----------|-------|----------|
| ... | X | ... |

**Findings**: ...
**Recommendations**: ...

### R2: Product Quality Expert
(Vote, Score, same format as R1)

### R3: Engineering Efficiency Expert
(Vote, Score, same format as R1)

---

## Round 2: Cross-Examination Debate

### Challenges & Conflicts
| Challenger | Target | Finding Challenged | Resolution |
|------------|--------|-------------------|------------|
| R1 | R3 | "X is performant enough" | R3 conceded, revised score -0.5 |
| R2 | R1 | "Microservices required" | R1 defended with scalability data |
| ... | ... | ... | ... |

### What Reviewers Missed (caught by others)
- R1 missed: [X] (caught by R2)
- R2 missed: [Y] (caught by R3)
- R3 missed: [Z] (caught by R1)

### Score Changes After Debate
| Reviewer | Round 1 | Round 2 (Final) | Change | Reason |
|----------|---------|-----------------|--------|--------|
| R1 | 7.0 | 7.0 | — | No change |
| R2 | 6.5 | 6.0 | -0.5 | Conceded architecture concern |
| R3 | 8.0 | 7.5 | -0.5 | Caught missing test coverage |

---

## Round 3: Final Verdict

### Consensus (all three agree)
1. **[Finding]** — R1/R2/R3 all flagged this
2. ...

### Dissent (disagreement after debate)
1. **[Issue]** — R1 says X, R2 says Y. Rationale: ...
2. ...

### Final Vote Tally
| Reviewer | Final Vote | Final Score |
|----------|-----------|-------------|
| R1 (Architecture) | X | X.X |
| R2 (Product) | X | X.X |
| R3 (Engineering) | X | X.X |

**Result**: ✅ X | 🔄 Y | ❌ Z → **[FINAL DECISION]**

### Synthesized Action Items
(Priority-ordered, combining the best recommendations from all three perspectives)
1. **[P0]** ...
2. **[P1]** ...
3. **[P2]** ...
```

## Important Rules

- You are the ORCHESTRATOR — you do NOT review, you manage the three-round process
- Round 1: Spawn all 3 agents in ONE parallel message — total isolation
- Round 2: Spawn all 3 agents with the FULL Round 1 debate brief — they MUST see each other's findings to debate
- Round 3: You synthesize — the final verdict is YOUR analysis of their debate, not just a vote count
- If any agent fails in Round 1, retry once. If it fails again, that seat counts as ❌ reject (fail-safe)
- If any agent fails in Round 2, use their Round 1 scores — debate continues with remaining reviewers
- Never bypass gates. Never skip the debate round. The debate IS the quality mechanism.
