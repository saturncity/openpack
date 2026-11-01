# ADR-0021: Rack antennas in the wings (4 m boom, aimed at the far upstage corner) and BT40E receivers
Status: accepted. 2026-11-01. Issue #101 (part of #6). **Supersedes ADR-0016's install rule** (front of stage, ≥ 6 m up, aimed upstage). ADR-0016's antennas, coax, 2482 carrier and channel plan stand. **Decides the gain plan for #33 / PR #95 and the receiver board** (PR #95's stop-and-ask: its options b + c). Amends ADR-0011 (probe interval, miss-triggered switch) and ADR-0018 (module choice). Study `docs/analysis/r1-wing-antennas.md`, model `sim/loss/wing_geometry.py`, numbers `python3 audit.py` Audit 7, twin `run.py --geometry`.
- **Context:**
  - Owner constraint (2026-11-01): rack antennas may go only in the wings.
  - A panel there, aimed straight across, has four problems: it sees the far side of the audience in its beam; its own downstage corner is off-axis; actors walk right past it; and crew Wi-Fi in the opposite wing sits in its main beam.
  - Packs on stage can be 12 dB hotter at an antenna than a far pack. Every gap carrier has a 3 MHz neighbour (#76), so near-far matters, worst with actors waiting in both wings.
  - Mid-wing at 2 m, straight across, the worst point with both sides occupied is 1.8–8.2 dB under the twin threshold.
  - PR #95 found that a pack 0.5 m from a panel overloads the receiver module's always-on nRF21540 (P1dB −18 dBm, no bypass) whatever the fixed gain plan.
- **Decision:**
  - **Install:** one HG2409P-NF per wing, 1 m offstage of the acting area and ¼ of the stage depth back from the front edge.
    - **4.0 m up** on a lighting boom or stand (3.7–4.5; never below 3.5).
    - Aimed at the **far upstage corner** (≈ 30° upstage of straight across), tilted **10° down** (5–15°).
    - **No Wi-Fi transmitter in either wing or on stage**; backstage Wi-Fi ≥ 6 m from both antennas.
    - Crew phones in the wings in airplane mode; venue Wi-Fi on 1/6/11.
  - **RX-5:** its per-carrier antenna choice across the two wings is part of the R1 budget. Two firmware changes:
    - `OP_RX_ANT_PROBE_FRAMES` default goes from 100 to **1000**. A probe moves a gap copy to the far antenna, where Wi-Fi wins, and that frame rests on the in-band copy alone.
    - New **miss-triggered switch** (`op_ant_set_miss`, `OP_RX_ANT_MISS_DB` 12, `OP_RX_ANT_HOLD_FRAMES` 1000). On a missed window, the channel moves at once to the other antenna if that antenna's last window was valid and ≤ 12 dB weaker, and holds there for 1000 windows. A hot 3 MHz neighbour blocks the stronger antenna for only ~2 % of windows, too few for ADR-0011's 1 dB ageing to move it, and that cost 1.0 % frame loss with TD off in bsim (`prosc12-any`).
  - **Receivers: BT40E modules (no nRF21540), no pad**, behind PR #95's QPL9057 + QPQ1907 + Wilkinson chain.
    - The wings need system NF ≤ **21.1 dB**: the weakest pack is −47.7 dBm, −67.7 with 10 dB body loss and a 10 dB fade, and that NF costs 0.5 dB of R1 margin. RK-5's 9.30 dB was a 10 m front-of-stage assumption. The BT40E gives 11.5 dB (0.06 dB cost).
    - Every stage stays ≥ 6 dB under P1dB and the nRF5340 PIMD holds, B40 phones included (worst headroom +12.0 dB UK, +12.3 dB US).
    - Even a pack 0.5 m on axis doesn't compress a stage (+4.0 dB).
    - It costs $58 less per rack. The receiver never transmits in v1 (ADR-0004).
  - TD stays off by default (ADR-0017), and on per pack as the fallback.
- **Evidence:**
  - Model (free space, the HG2409P's pessimistic cuts, worst seat 20 dBm on all three Wi-Fi channels, hot pack anywhere on stage or at a boom, one or two at once). Worst stage point over the 3 dB design margin: studio 6 m −1.2, proscenium 10 m −0.1, proscenium 12 m −1.5 dB. So every point keeps ≥ 1.5 dB over the twin threshold, and 92–100 % of the stage keeps the full margin.
  - Each install setting off on its own still clears the twin threshold. At 3.2 m height the 12 m house is 0.8 dB under it.
  - bsim (c), 20 s per run, 10 % and 40 % Wi-Fi, TD off and on, with RX-5 replayed (both firmware changes): **7/7** bsim-runnable packs meet SYS-3 in all 12 cases (pack 1 by equivalence on 2482).
    - The cases cover the three venues, a hot pack at a boom, actors at both booms, and the worst stage aggressor from the model, alone or mirrored.
    - The tightest is 0.086 % with TD off (0.020 % with TD on). Even off-rule (pack 0.5 m on axis): 7/7.
    - Before the miss switch, the worst stage-aggressor case lost 1.0 % with TD off.
- **Requirements check:**

| R-id | A: 4 m wing rule + BT40E (chosen) | B: mid-wing 2 m across, BT40NE | C: A with BT40NE + fixed 10 dB pad | D: A with BT40NE + switched 0/20 dB pad | E: omni in the wings |
|---|---|---|---|---|---|
| R1 | ✓ bsim (see Evidence) + pack 1 by equivalence; ≥ 1.5 dB over the twin threshold everywhere; rests on the rule | ✗ both sides occupied: up to 8.2 dB under | ✓ RF; headroom +5.4 dB | partial: NF 25.3 costs 1.2 dB of R1 margin (studio stays padded) | ✗ 2.6–7.5 dB under |
| R3 | ✓ TD off, 2.65 ms | ✓ | ✓ | ✓ | ✓ |
| R9 / R10 | ✓ 8 packs, 2 BNC | ✓ | ✓ | ✓ | ✓ |
| R12 | ✓ pack BOM unchanged; −$58/rack; antennas £340.56 as ADR-0016; boom from venue stock | ✓ | partial: +pads | partial: +switches, control | ✓ |
| R13 | ✓ model + bsim with two antennas (RX-5 replayed) | ✓ | ✓ | partial: RX-5 + switch control not modelled | ✓ |
| owner constraint | ✓ wings only | ✓ | ✓ | ✓ | ✓ |

- **Consequences:**
  - R1 rests on placement, with 1.5 dB of the 3 dB design margin left at the worst point. Several settings off at once can drop below the twin threshold, so the install doc demands the numbers as written.
  - #32/#34 swap the receiver module BT40NE → BT40E. It is u.FL-only with no FEM (Fanstel $9.55; DigiKey UK £9.78, 803 in stock, `docs/analysis/module-antenna.md`).
    - It has a **different footprint** (14×16 mm BT40 pads, not the BT40NE's), so `hw/rx` needs the new symbol/footprint before layout. Its nine FEM pads become GPIO.
    - The receiver's ANT_SEL open item (#105) goes away.
    - The pack keeps the BT40NE.
  - PR #95 drops its pad options and relaxes the RK-5 NF line for the wing install.
  - Phase 5 measures the HG2409P 60–90° pattern (#92). Phase 6 repeats SYS-3 with the antennas in the wings of a full house.
  - A venue that can't keep the no-Wi-Fi-in-the-wings rule falls back to TD on for the affected packs.
