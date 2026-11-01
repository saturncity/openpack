# R1 with the rack antennas only in the wings

#101, part of #6. 2026-11-01. Supersedes the install part of ADR-0016 (front of stage, ≥ 6 m up, aimed upstage). That mount is no longer allowed: the owner allows rack antennas only at the sides of the stage. Decision: ADR-0021. Model: `sim/loss/wing_geometry.py`. Numbers: `python3 audit.py` Audit 7. Twin: `tests/bsim/scenarios/run.py --geometry docs/analysis/r1-wing/<case>.json`. Human steps: `docs/human/antenna-install.md`.

**Answer:** yes, in the twin, under a new wing rule, with less margin than before. One L-com HG2409P-NF per wing goes 1 m offstage of the acting area, ¼ of the stage depth back from the front edge and **3.5 m up**. It aims at the **far upstage corner**, tilted **15° down**. There is **no Wi-Fi transmitter in either wing or on stage**, and any backstage Wi-Fi is ≥ 6 m from both antennas. The receiver's per-carrier antenna choice (RX-5) across the two wings carries the near-far case. Under that rule:
- every stage point, in the studio and in both proscenium houses, holds its gap copy above the twin threshold, with an actor walking past an antenna included;
- the worst point keeps **2.8 of the 3 dB** design margin;
- bsim at 10 % and 40 % Wi-Fi gives **7 of 7** bsim-runnable packs passing SYS-3, TD off and TD on in all three venues, with an actor at a boom and the RX-5 probe every 1000 frames (§4: the old 100 cost 0.16 % for one pack with TD off). Pack 1 is credited by equivalence, as in ADR-0016.

No hardware or gain change is needed, and the antennas, coax and 2482 carrier stay. What changes:
- the mount: a 3.5 m lighting boom or stand in each wing;
- one firmware default: the RX-5 probe every 1000 frames, not 100;
- one firmware/host item recommended for PR #95's gain plan (§5).

## 1. Model

- **Geometry:** x runs across the stage (antenna L at −x, R at +x), y runs upstage from the front edge, z is height above the stage floor. Free space at 2442 MHz. No body loss, no fading, and no credit for the proscenium wall. That matches ADR-0015/0016's C/I.
- **Venues:**

| venue | acting area | wings | audience |
|---|---|---|---|
| studio | 6 × 5 m | 1.5 m | end-on, front row 1 m from the edge, 8 raked rows, 9 m wide, floor level with the stage |
| proscenium | 10 × 8 m | 3 m | stalls 1 m below the stage, front row 2.5 m out, 18 rows, 16 m wide; boxes at ±8 m beside the arch, 3 m up; circle front |
| large proscenium | 12 × 10 m | 4 m | 22 rows, 20 m wide, boxes at ±9.5 m |

- **Sources:**
  - Packs at 1.2 m height, on a 0.5 m grid over the acting area.
  - Every seat (and box, and the circle) is a 20 dBm Wi-Fi source, as in Q3. Each antenna takes its single worst source on all three channels.
  - Crew Wi-Fi is modelled anywhere in either wing, outside a keep-out radius.
- **Antenna:** HG2409P-NF cuts as read in ADR-0016: HPBW 75° H / 65° V, rear lobes −9/−10 dB, 180° −18/−30 dB. The 60° and 90° points are interpolated (est.), and Phase 5 measures the pattern (#92). The 3-D pattern isn't published, so the model is pessimistic both ways:
  - the wanted pack gets the **lower** of the two cuts at its off-axis angle;
  - every interferer (Wi-Fi, a hot pack) gets the **higher**.
- **Thresholds:** from the BabbleSim modem tables (`sim/loss/bsim_modem.py`), TD-length copy, PER ≤ 0.1 %.
  - An 11 MHz gap carrier needs C/I ≥ **−12.3 dB** against each Wi-Fi channel, the same 12.7 dB-short figure as Audit 4. The design adds 3 dB (ADR-0016), so "margin" below means C/I − (−12.3) − 3 dB.
  - A neighbouring pack may be **8.3 / 19.5 / 24.9 dB** hotter at 3 / 4 / 5 MHz offset. #76 found the same: 3 MHz fails, 5 MHz is fine.
- **Diversity:** RX-5 (ADR-0011, `fw/src/rx/ant.c`) chooses the antenna **per carrier**. It stays on the stronger-RSSI antenna, probes the other one every 100 frames, and ages a missed window by 1 dB. So a carrier that a hot neighbour blocks on one antenna moves to the other after about 6 dB + ΔRSSI of misses, and the copy on the other carrier covers that gap. A pack keeps its frames if its gap copy holds on either antenna. The "strict" column counts only the stronger-RSSI antenna.

## 2. Options

Margin is in dB over the 3 dB design margin at the worst stage point; ≥ 0 meets the design and ≥ −3 meets the twin threshold. "Stage ok" is the share of stage points with the full margin. Near-far: an actor walks within 0.5 m (horizontal) of antenna L in the worst direction, and every other pack stands anywhere on stage. Every row bans crew Wi-Fi in the wings unless it says otherwise. Run `python3 sim/loss/wing_geometry.py` for every row.

| # | Option | studio 6 m: stage ok / worst / near-far | prosc. 10 m | prosc. 12 m | R1 | Cost / complexity |
|---|---|---|---|---|---|---|
| W0 | Panel mid-wing, 2 m up, aimed straight across | 91.6 % / −1.7 / −2.6 | 97.8 % / −0.9 / −1.0 | 97.0 % / −0.9 / −1.5 | partial: in the twin everywhere, but no margin, and strict RSSI loses 17–41 % of the stage to near-far | £0 |
| W0c | W0 with crew Wi-Fi allowed ≥ 3 m from an antenna | −1.7 | −5.8 | −7.3 | ✗ (a crew AP in the far wing is in the beam) | — |
| **W1** | **Rule (ADR-0021): ¼ depth, 1 m offstage, 3.5 m up, aimed at the far upstage corner (≈ 30°), 15° down, no Wi-Fi in the wings or on stage** | **97.9 % / −0.2 / −0.2** | **100 % / +0.9 / +0.9** | **99.6 % / −0.2 / −0.2** | **✓ 2.8 of 3 dB at the worst point** | a 3.5 m boom or stand per wing (venue stock) |
| W1-lo | W1 on a 2 m stand (10° tilt) | 86.7 % / −2.3 / **−3.7** | 99.2 % / −0.1 / **−3.5** | 98.7 % / −0.8 / **−3.7** | ✗ near-far: an actor at the stand blocks a 3 MHz neighbour on both antennas | £0 |
| W1-crew | W1, crew Wi-Fi allowed 3 m away | −7.3 | −10.0 | −11.1 | ✗ | — |
| W2 | Omni 3 dBi in the wings, W1 mount | 0 % / −6.2 | 0 % / −9.7 | 0 % / −9.1 | ✗ the omni sees the audience as well as the stage | ~£30 per antenna |
| W3 | Generic 6 dBi wide panel (~100°), mid-wing, 2 m, toe 15°, tilt 20° | 100 % / +0.2 / −3.1 | 100 % / +0.9 / −1.7 | 100 % / +0.5 / −1.5 | partial: better against Wi-Fi, worse near-far at 2 m; no real part with a verified pattern | new part + R13 rework |
| W4 | Pad / AGC on the rack LNA | changes no C/I (§5) | | | n/a: near-far is a selectivity ratio, not compression | hw |
| W5 | TD on (4.58 ms, R3 hard limit) | no change in W1 (gap copies already hold); fallback for packs that can't keep the rule | | | ✓ as a fallback | per-pack setting (ADR-0017) |
| W6 | Channel-plan ordering (3 MHz pairs kept apart) | every gap carrier has a 3 MHz neighbour (2423/2426, 2448/2451, 2473–2482), so a static order can't remove the pairs; RX-5 across the wings does that job | | | n/a | — |

**Install tolerance** (W1, one setting off at a time; worst over the three venues, near-far included):

| setting | worst margin |
|---|---|
| height 4.0 m | −0.9 |
| height 3.0 m | −2.3 |
| height 2.5 m | −3.7 ✗ |
| tilt 10° / 20° | −0.5 |
| tilt 25° | −1.8 |
| aim ±5° | −0.8 |
| position ⅕ / 0.3 of the depth | −1.2 / −1.6 |
| 0.5 / 1.5 m offstage | −1.2 / −1.6 |

With several settings off at once, it reaches −4.5 dB, which is below the twin threshold. That is why the install doc says to set it up exactly as written, and why the height floor is 3 m.

## 3. Near-far and the rack chain

With the W1 rule:
- An actor walking past a boom is ≥ 2.35 m from the antenna, at −38.1 dBm (UK) at its connector. Packs on stage reach that antenna at −36 to −50 dBm, so the near pack is at most ~12 dB hotter. A 3 MHz neighbour can then lose its copy on that antenna only at the far corners, where the other wing's antenna holds it (near-far worst = Wi-Fi-only worst, extra 0–0.4 % of the stage).
- On a 2 m stand (W1-lo), the actor is 0.94 m away at −27.6 dBm, and 12–13 % of the stage depends on the other wing. Every venue is then 0.5–0.7 dB under the twin threshold.

Rack chain, with PR #95's gains (ADR-0018 draft, `8e5d0df`): QPL9057 22.4 dB, worst input P1dB −6.9 dBm; BAW 2.2 dB, Wilkinson 11.1, u.FL 1.0, sub-board 0.9; module nRF21540 +13 dB or bypassed −1 dB. No coax (worst). Wi-Fi is the worst seat on all three channels.

| case | antenna | rack LNA input (incl. Wi-Fi) | under worst P1dB | every module's radio, module LNA on / bypassed |
|---|---|---|---|---|
| UK, W1 rule | −38.1 | −28.5 | 21.6 dB | −18.8 / −32.8 |
| US 20 dBm, W1 rule | −27.1 | −25.4 | 18.5 dB | −7.8 / −21.8 |
| UK, off-rule 0.5 m on axis | −17.2 | −17.7 | 10.8 dB | **+2.1** / −11.9 |
| US, off-rule 0.5 m on axis | −6.2 | −7.1 | **0.2 dB** | **+13.1** / −0.9 |

- **Under the rule:** nothing compresses. The nRF5340 0 dBm maximum is never reached, even in the US with the module LNA on, so PR #95's gains stand.
- **At 0.5 m on axis** (an antenna at actor height, which the rule forbids):
  - The rack LNA is fine in the UK and at P1dB in the US.
  - The hot pack reaches **every** module on that antenna at +2.1 dBm (UK) with the module LNA on. ADR-0018's RSSI-driven bypass doesn't help here: each receiver measures only its own pack, so the other seven stay at full gain.
  - bsim doesn't model compression. The `*-onaxis` runs (§4) show only the C/I side: RX-5 moves the blocked carriers to the other wing.

## 4. bsim

Run: `run.py --only bc --eirp 9 --plan host/channel_plan_us.yaml --geometry docs/analysis/r1-wing/<case>.json --busy 10,40 --c-secs 20`. That is 8 packs and 16 receivers (one per pack per antenna) plus Wi-Fi 1/6/11, with RX-5 replayed per carrier and about 19.7 k frames per run. "TD off" uses v1 42 B packets, the shipping default (ADR-0017). "TD on" uses 81 B TD-length packets. SYS-3 means ≤ 0.1 % loss and ≤ 2 frames lost in a row. Pack 1 runs the US in-band pair 2414/2456, because bsim stops at 2480. It shows the known in-band numbers (TD off 21.5 %, TD on 8.8 % at 40 %) and is credited on 2482 by equivalence (ADR-0016), so the counts are of packs 2–8.

Pack placement per case (`wing_geometry.bsim_case`):
- the near pack walks 0.5 m past antenna L's boom (−38.1 dBm there, 2.35 m away);
- its 3 MHz neighbours stand where their gap copy is weakest with it there;
- the rest stand at the lowest-margin stage points, at least 1.5 m apart;
- each antenna gets its worst audience seat as the Wi-Fi source.

| case | near pack | 10 % TD off | 10 % TD on | 40 % TD off | 40 % TD on | worst pack (40 %, TD off) |
|---|---|---|---|---|---|---|
| studio-rule | 7 | 7/7 | 7/7 | 7/7 | 7/7 | 0.000 % (probe 1000); 7: 0.015 % (probe 100) |
| prosc10-rule | 7 | 7/7 | 7/7 | 7/7 | 7/7 | 7: 0.005 % (probe 1000); 0.061 % (probe 100) |
| prosc12-rule | 7 | 7/7 | 7/7 | 7/7 | 7/7 | 0.000 % (probe 1000); 7: 0.020 % (probe 100) |
| prosc12-near2 | 2 | 7/7 | 7/7 | **7/7 at probe 1000** (2: 0.020 %); 6/7 at probe 100 (2: 0.163 %) | 7/7 | see left |
| prosc12-onaxis (off-rule: pack 7 0.5 m on axis, −17.2 dBm) | 7 | — | — | 6/7 (6: 0.076 %, run 3) at probe 1000; 5/7 at probe 100 (6: 0.53 %, 8: 0.53 %) | **7/7** (6: 0.010 %, 8: 0.015 %) | — |
| studio-onaxis (off-rule) | 7 | — | — | 5/7 at probe 100 (6: 0.43 %, 8: 0.51 %) | **7/7** | — |

- **(b):** one pack at the lowest-margin stage point, two receivers. In every venue it loses 0.000 % at 10 / 25 / 40 %, TD off and TD on. `b_inband` (both carriers under Wi-Fi) fails at 40 % as in ADR-0016 (TD on 8.5–8.6 %); that is pack 1's case in bsim only.
- **No Wi-Fi:** every case loses 0 frames, the near pack included. This is the check that the 3 MHz neighbours survive a near pack (#76's XFAIL), and RX-5 now carries it.
- **What bsim found that the model didn't: the RX-5 probe.** Every 100 frames, RX-5 sends one copy's window to the other antenna. For a pack at one wing, the far antenna can't hear its gap copy over the Wi-Fi, so that frame rests on the in-band copy alone, which loses ~47 % at 40 %. That came to 1 % × ~40 % × ~47 % = **0.16 %** for near pack 2 with TD off. ADR-0011 assumed the other copy always covers a probe, but with wing antennas the other copy is often the Wi-Fi-busy one. **Fix:** the `OP_RX_ANT_PROBE_FRAMES` default goes from 100 to **1000** (`fw/src/rx/Kconfig`). That cuts the cost 10× (0.020 %, 7/7). A blocked antenna still ages out after hyst + ΔRSSI misses, using the stored RSSI of the other antenna, so a block is escaped as fast as before; only the return after an actor walks away waits up to 1 s. The replay reads the Kconfig default, and `--rx5-probe N` overrides it. The 10 % runs were at probe 100, which is strictly harder.
- **Off-rule** (an antenna at actor height, actor 0.5 m in front of it): the near pack's 3 MHz neighbours (packs 6, 8) fail with TD off. TD on brings them back to 7/7. That is why the rule sets a 3 m floor, and why TD on is the fallback for a venue that can't keep it.

## 5. What changed, and what didn't

- **Hardware:** no change. The same 2 × HG2409P-NF, CA3N050 and jumpers (£340.56 per rack, ADR-0016), plus a mount ≥ 3.2 m in each wing. Theatres keep lighting booms in the wings. If a venue has none, a wind-up lighting stand is part of the Phase 5 purchase (ADR-0019 list), not a new design item.
- **Gain plan (PR #95):** no change under the rule. Recommended for robustness: make the module-LNA bypass **antenna-wide**. The host sees every receiver's RSSI per antenna (`op_rx_msg`). When any pack exceeds −16 dBm at the radio on antenna X, all modules bypass while listening on X. That removes the +2.1 dBm off-rule overload and costs nothing at stage ranges, where the noise is 50 dB below the wanted signal. It is posted on PR #95, not built here.
- **Firmware:** `OP_RX_ANT_PROBE_FRAMES` default 100 → 1000 (§4). RX-5 already chooses per carrier.
- **Channel plan:** unchanged (W6).
- **TD:** stays off by default (ADR-0017); on per pack for an actor who can't keep the rule.

## 6. Limits

- The pattern's 60° and 90° points, the 3-D combination, the audience heights and the 20 dBm-per-seat assumption are estimates. The worst point has 0.2 dB of slack against the 3 dB margin, so the Phase 5 pattern measurement (#92) and the Phase 6 house test decide.
- Free space only: no body loss, multipath or curtain loss (wing masking costs ~1 dB). Body blocking (R10) is helped by the two opposite wings, but it isn't modelled here.
- bsim holds each geometry still for 20 s. RX-5 is replayed from a converged state, so walking transients (the ~6 + ΔRSSI missed windows before a switch) are covered by the other copy, but they aren't timed.
- bsim stops at 2480 MHz, so pack 1's 2482 carrier is credited by equivalence (ADR-0016).
