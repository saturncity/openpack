# ADR-0021: Rack antennas in the wings: ¼ depth, 3.5 m up, aimed at the far upstage corner, no Wi-Fi in the wings
Status: accepted. 2026-11-01. Issue #101 (part of #6). **Supersedes ADR-0016's install rule** (front of stage, ≥ 6 m up, aimed upstage). ADR-0016's antennas, coax, 2482 carrier and channel plan stand. Study `docs/analysis/r1-wing-antennas.md`, model `sim/loss/wing_geometry.py`, numbers `python3 audit.py` Audit 7, twin `run.py --geometry`.
- **Context:** Owner constraint (2026-11-01): rack receive antennas may go only at the sides of the stage, in the wings. In a wing, a panel aimed straight across the stage has three problems. It sees the far side of the audience inside its beam. Its own downstage corner is off-axis. And actors walk right past it. Crew Wi-Fi in the opposite wing sits in its main beam. Mid-wing at 2 m, straight across, the worst stage point is 1.7–7.3 dB short of the 3 dB design margin (W0, W0c). With an actor at a 2 m stand, a 3 MHz neighbour is blocked on both antennas (W1-lo: 0.5–0.7 dB under the twin threshold).
- **Decision:** one HG2409P-NF per wing. Each goes 1 m offstage of the acting area and ¼ of the stage depth back from the front edge, on a lighting boom or stand at **3.5 m** (3.2–4.0; never below 3 m). It aims at the **far upstage corner** (≈ 30° upstage of straight across), tilted **15° down** (10–20°). **No Wi-Fi transmitter in either wing or on stage**; backstage Wi-Fi ≥ 6 m from both antennas; venue Wi-Fi on 1/6/11 only. Antenna A goes in stage left on ANT A, antenna B in stage right on ANT B. RX-5's per-carrier antenna choice (ADR-0011) is now part of the R1 budget: the opposite wing holds a carrier blocked by an actor at a boom. TD stays off by default (ADR-0017), and on per pack as the fallback. Crew phones in the wings go to airplane mode. **Gain plan, coordinated with PR #95:** the rule answers that PR's near-pack stop-and-ask (its option c, "out of reach"): the closest actor is 2.35 m away, the same as 5.6 m on axis. A **fixed 10 dB pad after the BAW** then keeps the rack LNA, the always-on nRF21540 and the nRF5340 ≥ 6 dB under P1dB in every venue. Without it, studio front-row Wi-Fi alone leaves the nRF21540 3.3 dB short. The pad's NF (15.9 dB) costs 0.15 dB of R1 margin at stage ranges, so RK-5's NF ≤ 9.3 dB is relaxed for the wing install. PR #95 builds it.
- **Evidence:**
  - Model, worst point over studio 6 m / proscenium 10 m / 12 m, near pack included: −0.2 / +0.9 / −0.2 dB over the 3 dB margin. So every stage point keeps ≥ 2.8 dB over the twin threshold, and 97.9–100 % of the stage keeps the full margin.
  - bsim (c), 20 s per run, Wi-Fi 10 % and 40 %, near pack at a boom: **7/7** bsim-runnable packs meet SYS-3 in every venue, TD off and TD on (pack 1 by equivalence on 2482).
  - Only after one fix: with the ADR-0011 probe every 100 frames, near pack 2 lost 0.163 % with TD off. A probe moves its gap copy to the far antenna, where the Wi-Fi wins, so that frame rests on the in-band copy. **`OP_RX_ANT_PROBE_FRAMES` default → 1000** (0.020 %). This amends ADR-0011's probe interval.
  - Off-rule (antenna at actor height, actor 0.5 m in front of it): 5–6/7 with TD off, 7/7 with TD on.
- **Requirements check:**

| R-id | A: W1 rule (chosen) | B: W0 mid-wing 2 m, across | C: omni in the wings | D: wide 6 dBi panel | E: W1 on a 2 m stand + TD on everywhere |
|---|---|---|---|---|---|
| R1 | ✓ 7/7 bsim (probe 1000) + pack 1 by equivalence; 2.8 of 3 dB at the worst point; rests on the rule | partial: no margin; near-far leans on the other wing | ✗ −6 to −10 dB | partial: Wi-Fi ✓, near-far at 2 m −3.1 dB | partial: model 0.5–0.7 dB under the twin threshold near a stand; bsim off-rule TD on 7/7, but only with TD on for every pack |
| R3 | ✓ TD off, 2.65 ms | ✓ | ✓ | ✓ | partial: 4.58 ms |
| R9 / R10 | ✓ 8 packs, 2 BNC | ✓ | ✓ | ✓ | ✓ |
| R12 | ✓ pack BOM unchanged; antennas £340.56/rack as ADR-0016; boom from venue stock; one pad per RF chain | ✓ | ✓ | partial: new part | ✓ |
| R13 | ✓ model + bsim with two antennas (RX-5 replayed) | ✓ | ✓ | ✗ no real part with a verified pattern | ✓ |
| owner constraint | ✓ wings only | ✓ | ✓ | ✓ | ✓ |

- **Consequences:**
  - R1 still rests on placement, now with less margin (2.8 of 3 dB at the worst point). Two settings off at once can drop below the twin threshold (−4.5 dB at the tolerance corners), so the install doc demands the numbers as written.
  - Phase 5 measures the HG2409P 60–90° pattern (#92). Phase 6 repeats SYS-3 with the antennas in the wings of a full house.
  - A venue that can't keep the no-Wi-Fi-in-the-wings rule falls back to TD on for the affected packs.
  - SPEC RK-2, GLOSSARY and `docs/human/antenna-install.md` now carry this rule.
