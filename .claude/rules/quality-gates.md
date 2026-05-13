---
paths:
  - "projects/**"
  - "src/**"
---

# Quality Gate Rules

These rules are enforced when working with project or source files.

## Code Quality Standards (mandatory for all engineers)
- All code must pass type checking before submission
- No hardcoded secrets, tokens, or credentials
- Error states must be handled — no silent failures
- Test coverage ≥80% for new code
- No `TODO` or `FIXME` in merged code — create a task instead

## Review Gate Enforcement
- No code enters a review gate without Tech Lead approval
- Stage gate reviews (DG1-DG4) are MANDATORY — never skip
- Review board decisions are binding — do not argue, fix and re-submit

## Project File Standards
- `status.md` must be updated at least every 3 days
- Task assignments must have clear owners
- Blocked tasks must include blocking reason and date
- All review records must follow the standard format

## Process Compliance
- Every project must go through all 5 stages in order
- Design review (DG1) required before any code is written
- Stakeholder acceptance required before project closure
