# ADR-0019: Single consolidated purchase after all digital design
Status: accepted (owner decision, 2026-11-01). Issues #36–#42. Amends the Phase 5/6 order in `PLAN.md`.

- **Context:** The owner said: "I'm not buying anything until we are finished." The old plan bought two dev kits and bench tools after Phase 4 design, calibrated, then ordered boards in Phase 6.
- **Decision:**
  - All digital work completes before any purchase: Phase 4 layouts, DFM, mech, and firmware for the real boards.
  - Then ONE shopping list (#36): dev kits + bench instruments + PCBs and parts for 4 packs + rack + antennas.
  - The Phase 5 bench calibration runs after that buy, in parallel with board assembly.
- **Requirements check:**

| R-id | A: one buy after all design (chosen) | B: old plan, DKs first then boards |
|---|---|---|
| R1 | partial: twin is calibrated after boards exist; hardware proof still comes in G5/G6 | ✓ calibrates before boards |
| R3 | partial: ADC/DAC delay measured after layout; margin in SYS-2 budget | ✓ |
| R12 | ✓ one order, one shipping, no duplicate DK/EVM spend before design is final | ✓ |
| R13 | ✓ more digital-first, not less | ✓ |
| Owner instruction | ✓ | ✗ |

The owner's instruction decides; A is the only option that follows it.
- **Consequences:** Boards are designed before bench calibration of the twin, so a board re-spin is more likely. Mitigations:
  - **Design margins:** keep the SYS-2 latency and BOM margins, and strap options (e.g. PCM5102A FLT, ADR-0017) so values can change without a re-spin.
  - **DK measurements before population:** measure on dev kits first wherever the result could change the BOM or layout.
  - **Bare PCBs plus a stencil:** assembly waits for bench results; a re-spin costs boards, not populated parts.
  - Gates keep their content. Order: Phase 4 gate (also the purchase gate) → purchase → G5 with assembly in parallel → G6.
