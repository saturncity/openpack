## Project closed (2026-11-01)

The owner closed OpenPack at the end of Phase 4 (digital design). It will not be built. Their verdict: "solid prototype", "cost on receiver too high", "needs new innovation at the highest level". Do not resume the master prompt or start new tickets.

For an audit, read in this order: `docs/report/REPORT.md` (the consolidated report; the verdict is in section D6), `docs/design-log.md` (every difficulty and choice, plus the open risks), `docs/adr/`, `SPEC.md` and `REQUIREMENTS.md`, `hw/REVIEW.md`, and `python3 audit.py` (needs `.ws/.venv`). `STATUS.md` holds the final state. Remaining issues were closed as "not planned".

## Start here (historical: Step 1 → Step 2 handoff, 2026-10-31)

Master agent kickoff: `docs/agents/MASTER-PROMPT.md`. Read in order: `docs/agents/hands-off.md` (how to work without the owner), `REQUIREMENTS.md` (owner's ranked requirements, the yardstick), `SPEC.md` (numbered requirements + verification), `PLAN.md` (phases, tools, gates), `QUESTIONS.md` (hands-off defaults → ADRs), `AUDIT.md` / `AUDIT-2.md` (feasibility). Numbers: `python3 audit.py`. Work is tracked as GitHub issues: spec is #1, phases #2–#8, tasks under them. Keep `STATUS.md` current.

## Design log

`docs/design-log.md` records every design difficulty and consideration for the owner's final audit. Every design PR (hw, fw, sim, RF, mech, sourcing, compliance, ADRs) adds or updates its design-log entries in the same PR, and moves resolved items out of "Open risks for audit".

## Agent skills

### Issue tracker

Issues live in GitHub Issues (via `gh`). See `docs/agents/issue-tracker.md`.

### Domain docs

Single-context: one `GLOSSARY.md` + `docs/adr/` at the repo root. See `docs/agents/domain.md`.
