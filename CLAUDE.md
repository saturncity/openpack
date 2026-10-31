## Start here (Step 1 → Step 2 handoff, 2026-10-31)

Master agent kickoff: `docs/agents/MASTER-PROMPT.md`. Read in order: `docs/agents/hands-off.md` (how to work without the owner), `REQUIREMENTS.md` (owner's ranked requirements, the yardstick), `SPEC.md` (numbered requirements + verification), `PLAN.md` (phases, tools, gates), `QUESTIONS.md` (hands-off defaults → ADRs), `AUDIT.md` / `AUDIT-2.md` (feasibility). Numbers: `python3 audit.py`. Work is tracked as GitHub issues: spec is #1, phases #2–#8, tasks under them. Keep `STATUS.md` current.

## Agent skills

### Issue tracker

Issues live in GitHub Issues (via `gh`). See `docs/agents/issue-tracker.md`.

### Domain docs

Single-context: one `GLOSSARY.md` + `docs/adr/` at the repo root. See `docs/agents/domain.md`.
