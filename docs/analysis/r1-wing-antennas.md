# R1 with the rack antennas only in the wings

#101, part of #6. 2026-11-01. Supersedes the install part of ADR-0016 (front of stage, ≥ 6 m up, aimed upstage). That mount is no longer allowed: the owner allows rack antennas only at the sides of the stage. Decision: ADR-0021, which also settles PR #95's gain-plan stop-and-ask. Model: `sim/loss/wing_geometry.py`. Numbers: `python3 audit.py` Audit 7. Twin: `tests/bsim/scenarios/run.py --geometry docs/analysis/r1-wing/<case>.json`. Human steps: `docs/human/antenna-install.md`.

**Answer:** yes, in the twin, under a new wing rule and a receiver-module change, with less margin than before.

The configuration:
- **Antennas:** one L-com HG2409P-NF per wing, 1 m offstage of the acting area and ¼ of the stage depth back from the front edge. Each sits **4 m up** on a lighting boom, aims at the **far upstage corner** and tilts **10° down**.
- **No Wi-Fi transmitter in either wing or on stage.** Backstage Wi-Fi stays ≥ 6 m from both antennas, and crew phones in the wings are in airplane mode.
- **Receivers:** BT40E modules (no nRF21540), with no pad.
- **Firmware:** RX-5 probes every 1000 frames, not 100, and gains a miss-triggered switch with a hold (§4).

Under that configuration:
- **Model:** every stage point in a 6 m studio, a 10 m and a 12 m proscenium house holds its gap copy ≥ **1.5 dB above the twin threshold**. That covers any pack hot anywhere (at a boom or on stage), and actors in both wings at once.
- **bsim:** **7 of 7** bsim-runnable packs meet SYS-3 in every case: 10 % and 40 % Wi-Fi, TD off and TD on, one or two hot packs, at a boom or on stage. The tightest is 0.086 % with TD off. Pack 1 is credited on 2482 by equivalence, as in ADR-0016.
- **What changed from ADR-0016:**
  - the mount: a 4 m boom or stand per wing;
  - the receiver module: BT40NE → BT40E, which removes PR #95's overload and saves $58 per rack;
  - two RX-5 firmware changes (the probe interval, and the miss-triggered switch).
- **What did not change:** the antennas, coax, 2482 carrier, channel plan and rack chain.

## 1. Model

- **Geometry:** x runs across the stage (antenna L at −x, R at +x), y runs upstage from the front edge, z is height above the stage floor. Free space at 2442 MHz. No body loss, no fading, and no credit for the proscenium wall. That matches the ADR-0015/0016 C/I.
- **Venues:**

| venue | acting area | wings | audience |
|---|---|---|---|
| studio | 6 × 5 m | 1.5 m | end-on, front row 1 m from the edge, 8 raked rows, 9 m wide, floor level with the stage |
| proscenium | 10 × 8 m | 3 m | stalls 1 m below the stage, front row 2.5 m out, 18 rows, 16 m wide; boxes ±8 m beside the arch, 3 m up; circle front |
| large proscenium | 12 × 10 m | 4 m | 22 rows, 20 m wide, boxes at ±9.5 m |

- **Sources:**
  - Packs at 1.2 m height, on a 0.5 m grid over the acting area, plus an actor walking 0.5 m past each boom.
  - Every seat is a 20 dBm Wi-Fi source (Q3). Each antenna takes its single worst seat on all three channels at once.
  - Crew Wi-Fi is modelled anywhere in either wing, outside a keep-out radius.
- **Antenna:** the HG2409P-NF cuts as read in ADR-0016: HPBW 75° H / 65° V, rear lobes −9/−10 dB, 180° −18/−30 dB. The 60° and 90° points are interpolated (est.); Phase 5 measures the pattern (#92). The 3-D pattern isn't published, so the model is pessimistic both ways:
  - the wanted pack gets the **lower** of the two cuts at its off-axis angle;
  - every interferer (Wi-Fi, a hot pack) gets the **higher**.
- **Thresholds:** from the BabbleSim modem tables (`sim/loss/bsim_modem.py`), TD-length copy, PER ≤ 0.1 %.
  - An 11 MHz gap carrier needs C/I ≥ **−12.3 dB** against each Wi-Fi channel, the same 12.7 dB-short figure as Audit 4. The design adds 3 dB (ADR-0016), so "margin" below means C/I − (−12.3) − 3 dB. A margin of −3 is the twin threshold itself.
  - A neighbouring pack may be **8.3 / 19.5 / 24.9 dB** hotter at 3 / 4 / 5 MHz offset (#76: 3 MHz fails, 5 MHz is fine).
- **Silicon vs twin:** the nRF5340 PS v1.1 C/I (PR #95: ±2 MHz −2/−11, ±4 −22/−47, ≥ 6 −54 dB) interpolates to about −12 dB at 3 MHz on the worse side. The plan has no 4 MHz pairs, so the twin is the stricter of the two.
- **Diversity:** RX-5 (ADR-0011, `fw/src/rx/ant.c`) chooses the antenna **per carrier**. A pack keeps its frames if its gap copy holds on either antenna. That needs RX-5 to leave a blocked antenna, which needed one fix (§4).
- **Near-far:**
  - `near_far_any`: one hot pack anywhere (boom or any stage point), every other pack anywhere.
  - `near_far_any(both=True)`: two hot packs, mirror images.
  - `near_far_both`: actors at both booms, every (X, Y, Z) triple, including victims with a 3 MHz neighbour on each side (2426 between 2423/2429, 2476 between 2473/2479, 2479 between 2476/2482).

## 2. Options (antenna and install)

Margin is in dB over the 3 dB design margin at the worst stage point; −3 is the twin threshold. "Wi-Fi" is with no hot pack, "near-far" is the worst with a hot pack anywhere, and "both" is the worst with two (mirrored or at both booms). Every row bans crew Wi-Fi in the wings unless it says otherwise. All rows come from `wing_geometry.py` (the script `audit.py` Audit 7 calls).

| # | Option | studio 6 m: Wi-Fi / near-far / both | prosc. 10 m | prosc. 12 m | R1 |
|---|---|---|---|---|---|
| W0 | Panel mid-wing, 2 m up, aimed straight across | −1.7 / −2.6 / **−4.8** | −0.9 / −1.0 / **−9.5** | −0.9 / −1.5 / **−11.2** | ✗ actors on both sides |
| W1-lo | W1 on a 2 m stand | −2.3 / −3.7 / −5.5 | −0.1 / −3.6 / −9.3 | −0.8 / −3.7 / −11.5 | ✗ |
| W1-3.2 | W1 at 3.2 m | −0.5 / −0.5 / −0.5 | +0.5 / −1.8 / −2.2 | −0.1 / −3.2 / **−3.8** | ✗ 12 m house |
| W1-3.5 | W1 at 3.5 m, 10° | −0.5 / −0.5 / −0.5 | +0.9 / −1.0 / −1.0 | +0.2 / −2.6 / −2.6 | ✓ but thin (floor) |
| **W1** | **Rule: ¼ depth, 1 m offstage, 4.0 m up, aimed at the far upstage corner (≈ 30°), 10° down** | **−1.2 / −1.2 / −1.2** | **+0.2 / −0.1 / −0.1** | **+0.1 / −1.5 / −1.5** | **✓ ≥ 1.5 dB over the twin threshold** |
| W1-crew | W1, crew Wi-Fi allowed 3 m from an antenna | −6.8 | −9.0 | −10.3 | ✗ (a crew AP in the far wing is in the beam) |
| W2 | Omni 3 dBi in the wings, W1 mount | −5.6 | −10.5 | −10.5 | ✗ sees the audience as well as the stage |
| W3 | Generic 6 dBi wide panel (~100°), mid-wing 2 m, toe 15°, tilt 20° | +0.2 / −3.1 / −6.3 | +0.9 / −1.7 / −10.9 | +0.5 / −1.5 / −13.2 | ✗ near-far, and no real part with a verified pattern |
| W5 | TD on (4.58 ms, R3 hard limit) | gap copies already hold under W1; fallback for packs that can't keep the rule | | | ✓ fallback |
| W6 | Channel-plan ordering | every gap carrier has a 3 MHz neighbour. Moving pack 6's in-band 2429 to 2431 would free 2426, but 2476 and 2479 sit inside the 2473–2482 gap block at 3 MHz spacing. RX-5 across the wings does the job instead (`near_far_both` = Wi-Fi-only worst under W1) | | | n/a |

**Install tolerance** (W1, one setting off at a time; worst over all venues and near-far cases):

| setting | worst margin |
|---|---|
| height 3.5 m | −2.6 |
| height 3.7 m | −2.2 |
| height 4.3 m | −1.5 |
| height 4.5 m | −2.0 |
| tilt 5° | −1.6 |
| tilt 15° | −1.8 |
| tilt 20° | −2.4 |
| aim 25° / 35° | −1.4 / −1.9 |
| position ⅕ / 0.3 of the depth | −1.0 / −2.2 |
| 0.5 / 1.5 m offstage | −1.8 / −2.3 |

Every single deviation stays above the twin threshold. Several at once can fall below it, so the install doc asks for the numbers as written. Studio: 92 % of the stage has the full 3 dB, and the rest has ≥ 1.8 dB.

## 3. Near-far and the gain plan

**Near-far under W1:**
- An actor at a boom's foot is 2.8 m from the antenna, at −40.9 dBm (UK, pattern and tilt included). That equals 7.7 m on axis.
- A pack on stage in an antenna's beam can be hotter, up to about 12 dB over the weakest stage pack on the same antenna. That is the case `near_far_any` finds: in the 12 m house, a hot pack 1 m inside the stage-left edge, with its 3 MHz neighbour at the downstage-left corner. RX-5 moves the victim's carrier to the other wing, where it holds with 1.5 dB over the twin threshold.
- With actors in both wings at once (`near_far_both`), the worst case is no worse than with no hot pack.

**Gain plan (the decision for #33 / PR #95 and the receiver board).** PR #95's chain at `01570d9`:
- QPL9057 23.0 dB (21.5 dB proxy for NF), worst input P1dB −7.6 dBm;
- BAW 2.2 dB (+2 dB at the band edges), Wilkinson 11.1, u.FL 1.0, sub-board 0.9;
- BT40NE nRF21540 +13 dB, P1dB −18 dBm, **no bypass**;
- nRF5340 PRX,MAX 0 dBm, PIMD −22 dBm.

PR #95's rule: every stage's total input ≥ 6 dB under its worst P1dB, and PIMD scaled to the weakest wanted pack. Levels assume no coax; the NF uses the 6 dB coax budget at a band-edge carrier, and the cascade reproduces PR #95 (9.39 / 15.89 / 25.31 dB). The interferers are the boom actor, Wi-Fi 1/6/11 from the worst seat and a 23 dBm LTE B40 phone (2390 MHz, unfiltered ahead of the LNA) from the worst seat, all at once.

**NF the wings need.** The weakest wing pack is −47.7 dBm at its better antenna (12 m house, far corner), or −67.7 dBm with 10 dB body loss and a 10 dB fade. An NF of ≤ **21.1 dB** costs ≤ 0.5 dB of the R1 margin (Audit 6's noise-cost form). RK-5's 9.30 dB was Audit 4's assumed chain for the 10 m front-of-stage link, not an R1 need. In the wings, the far packs are 3–12 m away.

| option | NF (6 dB coax, band edge) | R1 cost | worst headroom under W1, UK / US (B40 phone included) | off-rule, pack 0.5 m on axis: compression / with PIMD | modules per rack |
|---|---|---|---|---|---|
| (c) W1, BT40NE, no pad | 9.39 | 0.04 | **−14.6** / −5.9 ✗ (studio Wi-Fi + phone overload the nRF21540) | −14.2 / −44.6 | — |
| (c) + fixed 10 dB pad, BT40NE | 15.89 | 0.16 | +5.4 / +4.1 | −4.2 / −24.6 | + pad parts |
| (a) + (c): switched 0/20 dB pad, BT40NE | 25.31 when padded | **1.21** ✗ | +13.8 / +12.3, but the studio's audience Wi-Fi keeps it padded all show | +4.0 / −4.6 | + 2 switches, RSSI control, RX-5 support |
| **(b) + (c): BT40E receivers (no FEM), no pad** | **11.48** | **0.06** | **+12.0 / +12.3** | **+4.0** / −18.0 | **−$58** (8 × $9.55 vs $16.76) |

**Recommendation: (b) + (c).**
- BT40E modules on the eight receiver sub-boards, no pad, and the W1 rule.
- It is the only option that meets the wing NF need with margin, keeps every stage ≥ 6 dB under P1dB and inside the nRF5340 PIMD in all venues and both regions, and still doesn't compress with a pack 0.5 m on axis. PIMD fails there, which is why the rule exists. It is also the cheapest.
- The receiver never transmits in v1 (ADR-0004), so it doesn't need a PA. A later downlink would get the nRF5340's own +3 dBm, plenty at stage range.
- The BT40E is u.FL-only, no FEM: Fanstel $9.55, DigiKey UK £9.78, 803 in stock (`docs/analysis/module-antenna.md`, #106). Its footprint differs from the BT40NE's (14×16 mm BT40 pads), so `hw/rx` swaps the symbol and footprint before layout (#32/#34). The receiver's ANT_SEL item (#105) goes away; the pack keeps the BT40NE.
- Crew phones in the wings would be inside any option's phone distance, so the install doc says airplane mode in the wings.
- bsim doesn't model compression; the `*-onaxis` runs (§4) show only the C/I side.

## 4. bsim

The run: `run.py --only bc --eirp 9 --plan host/channel_plan_us.yaml --geometry docs/analysis/r1-wing/<case>.json --busy 10,40 --c-secs 20`.
- **Setup:** 8 packs, 16 receivers (one per pack per antenna) and Wi-Fi 1/6/11 at each antenna's worst seat, with RX-5 replayed per carrier using the `fw/src/rx/Kconfig` defaults. About 19.7 k frames per run.
- **TD off** uses v1 42 B packets, the shipping default (ADR-0017). **TD on** uses 81 B TD-length packets.
- **SYS-3:** ≤ 0.1 % loss and ≤ 2 frames lost in a row.
- **Pack 1** runs the US in-band pair 2414/2456, because bsim stops at 2480. It shows the known in-band numbers (TD off 21.5 %, TD on 8.8 % at 40 %) and is credited on 2482 by equivalence (ADR-0016), so the counts are of packs 2–8.

| case | what is hot | 10 % TD off / on | 40 % TD off / on | worst pack, 40 % TD off |
|---|---|---|---|---|
| studio-rule, prosc10-rule, prosc12-rule | pack 7 walking past L's boom; its 3 MHz neighbours where they are weakest | 7/7, 7/7 | 7/7, 7/7 | ≤ 0.005 % |
| prosc12-near2 | pack 2 at L's boom | 7/7, 7/7 | 7/7, 7/7 | 0.000 % |
| **prosc12-both**, **studio-both** | **actors at both booms**: 2 at L, 6 at R; victim 3 (2426, between 2423 and 2429) | 7/7, 7/7 | 7/7, 7/7 | 0.015 / 0.005 % |
| prosc12-any | `near_far_any`'s worst: pack 2 on stage 1 m inside the left edge, in L's beam; victim 3 at the downstage-left corner | 7/7, 7/7 | 7/7, 7/7 | **0.086 %** (TD on 0.020 %) |
| prosc12-any-both, prosc10-any-both, studio-any-both | the same with a mirror-image hot pack on the other side | 7/7, 7/7 | 7/7, 7/7 | 0.066 / 0.025 / 0.000 % |
| prosc12-onaxis, studio-onaxis (off-rule) | pack 7 0.5 m straight in front of L at its height (−17.2 dBm) | — | 7/7, 7/7 | 0.051 % |

- **(b):** one pack at the lowest-margin stage point, two receivers. In every venue it loses 0.000 % at 10 / 25 / 40 %, TD off and TD on. `b_inband` (both carriers under Wi-Fi) fails at 40 % as in ADR-0016. That is pack 1's case in bsim only.
- **No Wi-Fi:** every case loses 0 frames, the hot packs included. RX-5 now carries #76's near-pack XFAIL.
- **Tightest margin:** prosc12-any at 40 % with TD off, 0.086 % against the 0.1 % limit (17 frames in 19.7 k, run of 1). TD on gives 0.020 %.

**What bsim found that the model didn't, and the two RX-5 fixes:**
1. **Probe cost.** Every 100 frames, RX-5 sends one copy's window to the other antenna. For a pack at one wing, the far antenna can't hear its gap copy over the Wi-Fi, so that frame rests on the in-band copy alone, which loses ~47 % at 40 %.
   - Cost: 1 % × ~40 % × ~47 % ≈ **0.16 %** with TD off (prosc12-near2).
   - Fix: `OP_RX_ANT_PROBE_FRAMES` 100 → **1000**, so 0.02 %.
2. **Intermittent block.** A hot pack 3 MHz away blocks the stronger antenna only while its copies overlap in time: about **2 %** of windows, in short gaps. ADR-0011's 1 dB-per-miss ageing resets on the next valid copy, so the carrier never leaves that antenna. Each blocked window then lands on a frame whose in-band copy is lost ~47 % of the time.
   - Cost: prosc12-any lost **1.0 %** with TD off and 0.117 % with TD on, while the other antenna alone would have lost 0.010 %.
   - Fix: a **miss-triggered switch** (`op_ant_set_miss`, `OP_RX_ANT_MISS_DB` 12, `OP_RX_ANT_HOLD_FRAMES` 1000). On a missed window, move to the other antenna at once if its last window was valid and it is ≤ 12 dB weaker, then hold for 1000 windows. That gives 0.086 % / 0.020 %, and it also brings the off-rule on-axis case to 7/7.
   - Unit tests: `fw/tests/rx_ant` (6/6 on native_sim). The replay mirrors `ant.c` (`tests/test_wing.py`).
3. **Exporter bug** (fixed before these runs): a first export had subtracted the EIRP twice for the boom actor, which made it 9 dB too weak.

## 5. What changed, and what didn't

- **Antennas:** unchanged. The same 2 × HG2409P-NF, CA3N050 and jumpers (£340.56 per rack, ADR-0016), plus a mount ≥ 3.7 m in each wing. Theatres keep lighting booms in the wings. A venue with none needs a wind-up stand, on the Phase 5 list (ADR-0019).
- **Receiver board (#32/#34) and gain plan (#33 / PR #95):**
  - BT40NE → **BT40E** on the eight receiver sub-boards, no pad, nothing switched.
  - RK-5's NF limit becomes ≤ 21.1 dB for the wing install.
  - This is posted on PR #95; it is not built here.
- **Firmware (here):** RX-5 probe 1000, and the miss-triggered switch with hold.
- **Channel plan:** unchanged (W6).
- **TD:** stays off by default (ADR-0017); per pack where a venue can't keep the rule.

## 6. Limits

- **Pattern and audience:** the pattern's 60° and 90° points, the 3-D combination, the audience heights and 20 dBm per seat are estimates. The worst point has 1.5 dB of slack against the 3 dB margin, and bsim's tightest case is 0.086 % against 0.1 %. Phase 5 (#92: the pattern) and Phase 6 (a full house) decide.
- **Propagation:** free space only: no body loss, multipath or curtain loss (wing masking costs ~1 dB). Body blocking (R10) is helped by the two opposite wings, but it isn't modelled here.
- **Static geometry:** bsim holds each geometry still for 20 s. RX-5 is replayed from a converged state, so walking transients are covered by the other copy, but they aren't timed.
- **2482 carrier:** bsim stops at 2480 MHz, so pack 1's 2482 carrier is credited by equivalence (ADR-0016).
- **Compression:** compression and PIMD come from datasheet limits (PR #95), not from bsim. The BT40E footprint swap in `hw/rx` is still to do.
