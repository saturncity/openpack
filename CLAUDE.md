# OpenPack v2 (fresh start, 2026-11-01)

v2 is an orphan branch: no v1 code or decisions carry over unless an ADR brings them in deliberately. v1 lives on `main`; its audit is in `docs/audit/`.

## Read in order

1. `REQUIREMENTS.md`: the owner's ranked priorities (P1–P12), cost tripwires, prototype exit criteria. The yardstick for every decision.
2. `docs/audit/2026-11-01-v1-audit.md`: why v1 failed, what is reusable (§7.1), what must not come back (§7.2), technology directions (§6).
3. `docs/ideas/`: the radical idea board (next step after this fresh start).
4. `STATUS.md`: current state, written for a non-engineer.

## How we work (owner-confirmed)

- **Hands-off within a phase; the owner reviews at every phase boundary:** architecture chosen, link measured on dev kits, prototype demo, and every board before it is ordered. Do not cross a boundary without the owner's review.
- **Cost tripwire:** more than 25 % over a subsystem budget, or the 32-channel system over £1,500 in parts, stops work and produces a one-page "do we need this" assessment for the owner.
- **Review pack per board** before any order: photo-real renders front and back, parts list with prices and total, DRC report, the fab's manufacturability check, and a one-page plain-English note on what the board does and why each expensive part is there.
- **The owner decides all spending.** Never plan purchases on the owner's behalf; present options and prices. A test round of custom boards is acceptable if it stays under about £200.
- **Measure, don't only simulate.** Simulation gates logic; the bench gates numbers (latency, loss, noise, power). A simulation gate must run the configuration that ships.
- **Report margins with run lengths and confidence intervals.** A sub-percent margin from 20 seconds of simulation is not evidence.
- **Traceability:** ADRs in `docs/adr/` with a requirements-check table (one row per P-id, one column per option); a design log `docs/design-log.md` of every difficulty and choice, updated in the same PR; GitHub issues per task; CI gates.
- **Dropped v1 rules:** "single purchase at the end" and "agents never ask".
- **Owner is UK-based:** GBP prices ex VAT, UK-buyable parts, UK radio rules.

## Licences

Hardware: CERN-OHL-S-2.0. Firmware and software: GPL-3.0-or-later. See `LICENSES.md`.
