# Hands-off development

The human owner has no electronics, RF, audio, or firmware background and has pre-approved all work within the scope of `PLAN.md`. Agents decide; the human is not a reviewer. Read this before any task.

## Authority

- **Decide everything inside scope yourself.** Scope = `PLAN.md` phases 0–6 minus its "Explicitly not in this plan" list. Record each decision as `docs/adr/NNNN-<slug>.md` (context, decision, consequences; 10 lines max). Never leave a decision as a question to the human.
- **Open questions have defaults.** `QUESTIONS.md` → "Hands-off defaults" is the answer sheet. Use it, write the ADR, move on. Change a default only with evidence from a simulation or test, and say so in the ADR.
- **Decisions outside the defaults are judged against `REQUIREMENTS.md`.** When no default covers a choice, the ADR gets a "Requirements check" table: one row per affected R-id, one column per option, ✓/✗/partial. Pick the option that satisfies the highest-priority R-ids; ties go to the cheaper or simpler option. If no option satisfies a requirement in full, that is a stop-and-ask (reason 5 below), not a silent downgrade.
- **Gates replace human review.** A phase is done when its `PLAN.md` gate passes in CI. Opus reviews Sonnet's PRs. Nobody waits for the human.
- **Commit, push, open and merge PRs without asking.** Branch per issue, CI green before merge, squash to `main`. One GitHub issue per task (`issue-tracker.md`).

## The only reasons to stop and ask

1. **Money.** Any purchase. Post one message: list with vendor links, quantities, total, what it unblocks. The human buys.
2. **Physical actions.** Plugging in boards, placing antennas, carrying a dongle to a show. Write `docs/human/<task>.md` first (below), then ask.
3. **Out of scope.** Anything on the "not in this plan" list or a change the plan didn't anticipate. One paragraph, a recommendation, default "no".
4. **Safety or legal.** Li-ion handling, selling or certifying, transmitting beyond Part 15 limits.
5. **A requirement can't be met.** Evidence shows an R-id in `REQUIREMENTS.md` is unachievable within scope and budget. State which, why, and the nearest achievable number. Default while waiting: keep working on everything that doesn't depend on it.

Everything else: proceed.

## What hands-off means for each tool

| Tool | Who runs it | Note |
|---|---|---|
| BabbleSim + Zephyr, Twister | Agents, in GitHub Actions or Docker | Linux-only; never assume it runs natively on the owner's Mac |
| ViSQOL, PESQ, numpy/scipy | Agents | ViSQOL decides codec and PLC questions; no listening test required |
| ngspice, `kicad-cli`, KiBot | Agents | Some TI SPICE models need a TI login: ask the human once for the file |
| CadQuery, PrusaSlicer CLI | Agents | Render STL to PNG and review the image yourself |
| FastAPI, pytest, Schemathesis | Agents | |
| PCB layout review | Agents | Render copper/silk layers to PNG with `kicad-cli`, review visually, then run the fab's automated DFM on upload. No human review |
| Dev kits, PPK2, logic analyzer | Human plugs in once, agents drive via `west flash`, `ppk2-api`, sigrok CLI | Use a logic analyzer or DK timers, not an oscilloscope, so latency measurement is CLI |
| Venue occupancy scan | Human, optional | Skip and use literature values if not done |
| Buying | Human | |

Claude Code must run in a permission mode that allows brew, pip, west, git and gh without prompts; that is the owner's setting, not a repo file.

## How to talk to the human

- One message, plain English, every acronym explained in five words, numbers only if they change the decision.
- Lead with the one thing you need. Recommended option first, then "reply ok to proceed". Silence means ok for anything that isn't money.
- Never ask the human to judge engineering. The one exception: blind A/B audio clips, phrased as "which sounds better, A or B?" and only if ViSQOL scores are within 0.1 of each other.

## Human task checklists (`docs/human/`)

Before asking for a physical step, write `docs/human/<task>.md`:
- Zero-knowledge: which cable into which socket, product-page links, parts named by what is printed on them.
- Numbered steps, one action each, expected result after each ("a green light on the small board").
- What to send back and where (a photo or file attached to issue #N).
- "If it didn't work": the two likeliest failures and one thing to try.
- More than five steps: generate it with the `wizard` skill.

## Reporting

`STATUS.md` at the repo root, updated in every merged PR, written for a non-engineer:
```
Phase: 2 of 6 (firmware in simulation)
Done since last update: ...
Next: ...
Waiting on human: nothing | buy X (issue #N) | run docs/human/Y.md
Risks: one line each, or "none new"
```
The human reads `STATUS.md`, nothing else.

## Working rules

- `PLAN.md` is the plan. If reality diverges, edit it in the same PR and explain in an ADR.
- Ponytail applies: smallest working thing, one runnable check per non-trivial piece, nothing built for a later phase.
- Numbers live in `audit.py` or a test, not in prose.
- Nothing is bought, built or laid out before `PLAN.md` says it is unblocked.
