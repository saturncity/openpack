# OpenPack design log

The owner asked for a record of every design difficulty and consideration, kept for a later audit of the finished project. This file is that record. ADRs record decisions; this log records the difficulty behind each one, the options weighed, what is still uncertain, and what the bench must confirm.

**Rules for this file**

- Every design PR adds or updates its entries here in the same PR (CLAUDE.md, `docs/agents/hands-off.md`).
- One entry per difficulty, grouped by area, and an ID that never changes (`RF-7`). If an entry is superseded, mark it **Superseded by X** and keep it.
- Each entry has: the difficulty, the options weighed, what was chosen and why, links, the residual risk, and whether Phase 5 bench work must verify it.
- Numbers come from `python3 audit.py`, a test or a datasheet. Quote the source.
- `#N` means github.com/saturncity/openpack issue or PR N. ADR links are relative to `docs/adr/`.
- When a risk closes, move it out of "Open risks for audit" and note the evidence in its entry.

Backfilled 2026-11-01 from AUDIT.md, AUDIT-2.md, ADR-0001 to ADR-0022, hw/REVIEW.md, docs/analysis/, and merged PRs #43 to #121 with their review comments.

## Open risks for audit

Unresolved items, worst first. Each links to its entry.

| # | Risk | Why it matters | Closes when | Entry |
|---|---|---|---|---|
| 1 | **The R1 dropout margin is thin.** The tightest bsim case loses 0.086 % of frames against the 0.1 % limit, and the model keeps 1.5 dB of the 3 dB design margin at the worst stage point. | R1 (no dropouts) is the top requirement. The margin exists only if the venue follows the wing install rule. | G5 bench and G6 full-house test pass with antennas in the wings. | RF-7, AN-3 |
| 2 | **Pack 1's 2482 MHz carrier has never been simulated.** bsim cannot transmit above 2480 MHz, so pack 1 passes "by equivalence". Its legality rests on an occupied bandwidth estimate (fails above 2.51 MHz). | One pack in eight could fail R1 or fail EN 300 328. | #92: spectrum analyser on a real pack at 2482. | RF-6, CO-2 |
| 3 | **The boards are designed before any bench calibration** (single purchase, ADR-0019). | ADC/DAC delays, noise, ripple, FEM behaviour and antenna patterns are datasheet or model values. A board re-spin is possible. | Phase 5 measurements agree with the twin. | PR-1 |
| 4 | **Two pack FEM settings are guesses.** The ANT_SEL level that routes the nRF21540 to the u.FL (firmware assumes 1), and the MODE pin (P1.04 from the pad table; Fanstel's sample says P0.24, which is the pack's I2S BCLK). | Wrong ANT_SEL: the whip is not driven and range collapses. Wrong MODE: wrong gain or power. | Bench check, or a written answer from Fanstel. | PK-2, PK-3 |
| 5 | **Module certification paperwork is incomplete.** The BT40NE whip is not on FCC grant X8WBT40N. Fanstel publishes no UKCA or EU declaration for the BT40NE or BT40E. | OpenPack must make its own UK declaration under RER 2017. A US build needs a permissive change. | Fanstel's EN 300 328 reports in hand; own DoC written. | CO-3, CO-4 |
| 6 | HG2409P-NF panel rear lobes (−9 dB at 120–135°) and its 60–90° pattern points are read off a plot. | R1 isolation assumes 8.8 dB rejection. | #92 pattern measurement. | AN-2 |
| 7 | TD-on latency depends on the PCM5102A low-latency filter (FLT=1): 4577 µs modelled, only **23 µs** under the SPEC 4.6 ms line (bsim 4596 µs against an assert of 4600), and 0.4 ms under the 5 ms hard limit. FLT=1 has a weaker stop band and non-linear phase, not yet checked by ViSQOL. | One slow stage on the bench breaks the TD-on line. | Phase 5 latency (logic analyser) and SYS-4 ViSQOL with FLT=1. | AU-3, AU-4 |
| 8 | Preamp noise margin is thin: 6 % in ADR-0006 (0.94 µV), now 3 % (0.967 µV after the hot-plug resistor) against ≤ 1 µV. It comes from a generic macromodel, with supply noise and op-amp 1/f noise not modelled. Boost ripple filtering is only −10 dB at 100 Hz. | R5 (audio quality) could fail on the bench. | Bench noise and ripple measurement; TI model run. | PK-4, PK-9 |
| 9 | Phone leakage into gap carriers at 11–17 MHz offset and real per-copy floor loss are unknown. bsim's Wi-Fi spectrum is a model. | The event-rate gate (≤ 1 audible dropout/h) cannot be decided in simulation. | G5/G6 measurement (ADR-0010). | RF-13, TS-5 |
| 10 | QPQ1907 BAW filter loss at the band-edge carriers (2403, 2482) is a 2 dB estimate, and it is credited 0 dB rejection at 2370–2400 MHz (UK B40 phones). | Noise figure and blocking at the edges. | S2P data or VNA check. | RF-11 |
| 11 | MCUboot images on the openpack boards are signed with the default development key (`root-ec-p256.pem`). | Anyone can sign firmware the bootloader accepts. | A private signing key before units leave the bench. | FW-9 |
| 12 | **Rack Wilkinson trees lose 13.7 dB as routed** (limit amended to ≤ 14 dB, #126). The NF margin stays 8.2 dB (6.6 dB with the 100 ft lead), but the loss model (FR-4 tan δ, bends) is unmeasured. | NF and coax budgets (R1) rest on modelled losses. | VNA of one tree and both cable runs measured at the first venue. | RK-7c, RK-7h |
| 13 | **Codec choice not re-opened.** ADR-0005 picked ADPCM-6 because only it fits the TD copy in 85 B, and said: if TD ships off, ADPCM-8 vs ADPCM-6 becomes a quality tie for an owner A/B listening test. ADR-0017 ships TD off by default. No ADR records whether the choice was re-opened. | Non-TD packs (the default) may be giving up quality for no reason. | ADR-0005 amended: either keep ADPCM-6 because of per-pack TD, or offer ADPCM-8 on non-TD packs after a listening test. | AU-1 |
| 14 | Pack BOM is $33.34 against the $35 cap only at Fanstel's direct module price ($13.47). At Digi-Key UK (£12.52 ≈ $16.47) it is about $36.3, and $36.63 at Digi-Key US. Assembly and coating are excluded. BT40NE lead time is about 10 weeks; TPS259541 (rack) about 20 weeks. | R12 cost target; schedule of the single purchase. | Purchase quote (#36). | SC-1, SC-4 |
| 15 | bsim model limits: free space only, no body loss or fading, no compression or PIMD, runs of 20–60 s rather than 1 h, Wi-Fi skirt −12…−15 dB at 11 MHz (the 802.11 mask allows −20), nothing above 2480 MHz. | Twin results are relative evidence, not proof. | G5 calibration within 20 % of the twin. | TS-13 |
| 16 | Fab DFM has not been run on any board; CPL rotations for several packages are unmapped. | DFM findings arrive at purchase time. | DFM reports attached to #34. | PR-4, PK-14 |
| 17 | Rack total £1,501.50 ex VAT (£1,190.94 like for like) against an £800–830 target: the owner-fixed case and CM4, the £300 (est.) PCB order, the far-wing 75 ft coax. | R12 cost. | Owner accepts, or picks parts to cut (#36); a JLC quote replaces the PCB estimate. | RK-7k |
| 18 | Hammond side-extrusion cover-screw lugs may touch the main board's side edges (drawing not conclusive, STEP not downloadable). | The board may not drop into the case. | Bare-board dry fit; notch the edges if needed (no copper there but pour). | RK-7a |

## RF and link budget

### RF-1. One shared TDMA channel does not fit; one carrier pair per pack (FDMA)
- **Difficulty:** 8 packs × LC3plus 160 kbps on one 2 Mbps channel needs 155 % of a 1 ms frame. The nRF5340 has no 5 GHz radio; the ESP32-C5's 5 GHz is Wi-Fi MAC only (no deterministic TDMA) and doubles pack power.
- **Options:** shared TDMA; 5 GHz on ESP32-C5; FDMA with one carrier pair per pack; sub-GHz second band (US only).
- **Chosen:** FDMA, ADPCM at 6 bits/sample, each 1 ms frame sent twice on two widely spaced 2.4 GHz carriers from one radio. This is how commercial digital systems work, and it meets latency.
- **Links:** AUDIT.md "Blockers", AUDIT-2.md §C, ADR-0002, ADR-0004.
- **Residual risk:** carrier count (RF-2). Sub-GHz remains the strongest v2 fallback.
- **Bench:** no.

### RF-2. 16 carriers, only 7–10 fit between Wi-Fi channels
- **Difficulty:** 8 packs × 2 copies × 2 MHz = 16 carriers; the gaps between Wi-Fi 1/6/11 hold 7–10. "Never overlap Wi-Fi" is impossible at 8 packs.
- **Options:** accept overlap; two packs per pair with time staggering (needs a downlink); nRF54L15 at 4 Mbps (no help with channel count).
- **Chosen:** 8 packs firm; gap carriers first; the rest under Wi-Fi with copy B ≥ 40 MHz from copy A so both copies never share a Wi-Fi channel.
- **Links:** ADR-0002, AUDIT-2.md B1.
- **Residual risk:** resilience rests on diversity, merge, PLC and the install rule.
- **Bench:** G5/G6.

### RF-3. Carriers 2 MHz apart collide; near-far against 3 MHz neighbours
- **Difficulty:** bsim scenario (c) showed 58–100 % copy loss between 2 MHz-spaced gap carriers with no Wi-Fi, and a pack next to the antenna blocked its neighbours.
- **Options:** 2 MHz spacing (fails); 3 MHz spacing with a near-far rule; fewer packs.
- **Chosen:** every carrier ≥ 3 MHz from every other, and whichever pack is near an antenna, every other pack keeps a carrier ≥ 5 MHz away. Validator `host/channel_plan.py` and `tests/test_host.py` enforce it.
- **Links:** #76, ADR-0015, PR #82, PR #86.
- **Residual risk:** a near pack still costs its 3 MHz neighbour that copy (100 % copy loss, 0 frames lost with no Wi-Fi). With heavy Wi-Fi the neighbour then rests on its in-band copy. Documented limit.
- **Bench:** G6 with actors in both wings.

### RF-4. Wi-Fi losses come in bursts; time diversity costs latency
- **Difficulty:** a Gilbert-Elliott model shows ~1 % residual loss at 10 % busy, but as ~100 multi-frame dropouts per minute. PLC cannot hide them.
- **Options:** time diversity (TD: packet n also carries frame n−2; +2.3 ms, ~30 % more airtime); lower busy fraction via antennas and power; adaptive channels (needs downlink).
- **Chosen:** first built both and measured (ADR-0001). Once every pack had a gap carrier and the rack antennas held it, TD off showed the same 0.000 % loss as TD on, so TD is **off by default, on per pack** for hostile venues (ADR-0017).
- **Links:** AUDIT-2.md B2, ADR-0001 (superseded), ADR-0017, #26, #91, PR #102.
- **Residual risk:** TD packs output 2.3 ms later than non-TD packs; a sound designer mixing both hears the offset.
- **Bench:** G5/G6 decide which venues need TD.

### RF-5. UK power limits make R1 fail at the original test geometry
- **Difficulty:** EN 300 328 non-adaptive equipment at ≥ 10 dBm EIRP must leave a 3.5 ms Tx-gap (our longest gap is 436 µs) and keep medium utilisation ≤ 10 % (ours is 42.4 % at 20 dBm). The PSD limit alone caps any non-hopping mode at 11.2 dBm. At 9 dBm, gap carriers 11 MHz from Wi-Fi lost 33–47 % of copies and only 2 of 8 packs met SYS-3 at 40 % Wi-Fi. The shortfall was 12.7 dB of isolation.
- **Options:** (A) non-adaptive 9 dBm, FEM kept; (B) adaptive LBT (≤ 2.2 dB gain); (C) adaptive FHSS (no fixed gap carrier); (D) drop the FEM; (E) 1 Mbit PHY (TD doesn't fit); (F) US power (illegal).
- **Chosen:** A, plus a stop-and-ask to the owner. The owner chose receive-side isolation: directional rack antennas with an install rule (ADR-0016), later moved to the wings (ADR-0021). UK rules limit only the transmitter, so the gap is closed at the receiver.
- **Links:** ADR-0015, ADR-0016, ADR-0021, #80, #89, PR #86, PR #90, PR #93, `docs/analysis/r1-uk-isolation.md`.
- **Residual risk:** R1 now depends on antenna placement (RF-7).
- **Bench:** yes, G5.

### RF-6. Pack 1 needs an eighth gap carrier at 2482 MHz, 1.5 MHz below the band edge
- **Difficulty:** 7 gap carriers at 3 MHz spacing cannot serve 8 packs; pack 1 had both copies in-band (TD on 9.4 % loss at 40 % Wi-Fi). The only free gap slot is 2482.
- **Options:** pack 1 in-band with TD on (4.58 ms); 2482 (UK/EU only); 2481 (2 MHz from 2479, collides).
- **Chosen:** 2414/2482 for pack 1 in the UK plan. Clause check (EN 300 328 4.3.2.7–4.3.2.9): 99 % OCB top edge at 2483.28 MHz with +50 ppm and lab uncertainty, fails only above a 2.51 MHz OCB; out-of-band margins 6 / 21 / 11 dB at 9 dBm. US stays at 2480 (2483.5–2500 is restricted under FCC 15.205). Firmware and host cap fB by region.
- **Links:** ADR-0016, PR #93, #92, `host/channel_plan.yaml`, `host/channel_plan_us.yaml`.
- **Residual risk:** never simulated (bsim stops at 2480); credited by equivalence with 2476/2479. If the OCB measures over 2.51 MHz, pack 1 falls back to the US pair with TD on (R1 partial for that pack).
- **Bench:** **yes**, #92: 99 % OBW and 2483.5–2487.6 MHz emissions on a real pack.

### RF-7. Thin R1 margin with wing antennas (0.086 % against 0.1 %)
- **Difficulty:** with antennas only in the wings, packs on stage can be 12 dB hotter at an antenna than a far pack, actors pass right by the panels, and crew Wi-Fi in the opposite wing sits in the main beam. Mid-wing at 2 m, straight across, was 1.8–8.2 dB under the twin threshold.
- **Options:** (A) 4 m wing boom aimed at the far upstage corner + BT40E receivers; (B) mid-wing 2 m, BT40NE; (C/D) BT40NE with fixed or switched pads; (E) omni antennas.
- **Chosen:** A. Model: every stage point keeps ≥ 1.5 dB over the twin threshold (worst point uses 1.5 dB of the 3 dB design margin). bsim (c): 7/7 runnable packs meet SYS-3 in all 12 cases; tightest 0.086 % with TD off (0.020 % with TD on).
- **Links:** ADR-0021, #101, PR #103, `docs/analysis/r1-wing-antennas.md`, `sim/loss/wing_geometry.py`, `audit.py` Audit 7.
- **Residual risk:** several install settings off at once, or a mount below 3.5 m, drop below the twin threshold. Venues that cannot keep Wi-Fi out of the wings fall back to TD on.
- **Bench:** **yes**, G5 and G6 in a full house.

### RF-8. Module conducted power is +19.1 dBm, not +20
- **Difficulty:** ADR-0007 assumed +20 dBm; the BT40NE grant shows 19.1 dBm.
- **Chosen:** AIR-6 capped at +19 dBm (−0.9 dB, ~10 % range in the US). In the UK the pack runs at +7 dBm conducted, so it does not bind.
- **Links:** ADR-0007 amendment, PR #58.
- **Residual risk:** none for UK.
- **Bench:** no.

### RF-9. The receiver module's always-on nRF21540 LNA overloads near a pack
- **Difficulty:** behind the rack LNA, a pack 0.5 m from a panel drives the receiver module's nRF21540 (RX P1dB −18 dBm minimum, no bypass mode) 15 dB into compression. An RSSI bypass on one receiver cannot protect the other seven, which see the same out-of-channel blocker. No fixed gain plan met both noise figure and a 0.5 m pack.
- **Options:** BT40NE with no pad; fixed 10 dB pad; switched 0/20 dB pad (NF 25.3 dB, costs 1.2 dB of R1 margin); BT40E (no FEM), no pad.
- **Chosen:** BT40E, no pad, panels out of reach on 4 m booms. System NF 11.5 dB; every stage ≥ 6 dB under P1dB, B40 phones included (worst headroom +12.0 dB UK). Even a pack 0.5 m on axis does not compress a stage. About $31 per rack cheaper like-for-like.
- **Links:** PR #95 review M3 and gain-plan comments, ADR-0018, ADR-0021, #112, PR #113.
- **Residual risk:** the receiver can never transmit (fine for v1, ADR-0004; a v1.1 downlink needs its own module).
- **Bench:** G5 near-pack test.

### RF-10. Noise-figure requirement relaxed from 9.30 dB to 21.1 dB for the wing install
- **Difficulty:** RK-5's 9.30 dB came from a 10 m front-of-stage link (Audit 4). In the wings the weakest pack is −47.7 dBm (−67.7 dBm with 10 dB body loss and a 10 dB fade).
- **Chosen:** the limit is the NF that costs ≤ 0.5 dB of R1 margin: 21.1 dB. The design gives 11.48 dB at the band edges with the full 6 dB coax budget.
- **Links:** ADR-0018, ADR-0021, `audit.py` Audit 7.
- **Residual risk:** body loss and fade are assumptions.
- **Bench:** yes, body-loss measurement (R10).

### RF-11. Rack band filter: edge carriers on the skirt, no specified rejection for UK B40
- **Difficulty:** the QPQ1907 BAW specifies insertion loss only over 2402.5–2481.5 MHz, so 2403 and 2482 sit on its skirt. Rejection is specified only to 2370 MHz; O2's UK B40 block runs to 2390 MHz. The Broadcom ACPF-7A24 is better on paper but no UK distributor lists it.
- **Options:** QPQ1907; ACPF-7A24 (not UK-stocked); move the edge carriers.
- **Chosen:** QPQ1907 (DigiKey UK, £2.82, 7,548 in stock). Audit 6 charges the edge carriers 2.2 dB plus a 2 dB skirt estimate and credits 0 dB rejection at 2370–2400.
- **Links:** PR #95 review M2, ADR-0018 item 2.
- **Residual risk:** the skirt loss is an estimate (S2P not read).
- **Bench:** yes, VNA or S2P.

### RF-12. Phones next to the panels
- **Difficulty:** the QPL9057 LNA has > 20 dB gain from 1.5 to 3.8 GHz and the BAW sits after it, so cellular uplinks (B40 at 2390, B7, B1, B3) reach the LNA unfiltered.
- **Chosen:** phones added to the compression budget. A class-3 B40 phone needs ≥ 2.7 m from a panel, so crew phones in the wings go to airplane mode (install rule).
- **Links:** PR #95 review S2, ADR-0018, ADR-0021, `docs/human/antenna-install.md`.
- **Residual risk:** relies on crew discipline.
- **Bench:** G6.

### RF-13. bsim's Wi-Fi spectrum versus real phones
- **Difficulty:** bsim's WLAN model is −12…−15 dB at 11 MHz offset; the 802.11 mask allows −20 dB. Real phone leakage at 11–17 MHz is unknown and sets how clean the gap carriers are.
- **Chosen:** gate in sim on residual loss only; measure leakage in Phase 5.
- **Links:** ADR-0015, ADR-0010.
- **Residual risk:** sim may be optimistic or pessimistic.
- **Bench:** **yes**.

### RF-14. 1 Mbit PHY rejected
- **Difficulty:** 1M gains ~3–4 dB sensitivity.
- **Chosen:** rejected. TD off uses 988 µs of the 1000 µs frame (no room for the 300 µs RX slot); TD on needs 1612 µs and does not fit. A hybrid 1M copy B stays a documented fallback, not simulated.
- **Links:** ADR-0015 option E, ADR-0016 option C, `audit.py`.
- **Bench:** no.

### RF-15. Is the BT40NE's u.FL driven through the FEM?
- **Difficulty:** Fanstel spec p.22 says "the nRF21540 in BT40X is hardware-wired to the PCB trace antenna". If that applied to the BT40NE, the whip would get no PA power and range would drop to 24 m or 16 m with body loss (16 m fails the 20 m audit).
- **Chosen:** traced to Fanstel's 2020 naming: "BT40X" is today's BT40N (PCB antenna only). FCC ID X8WBT40N lists a 6 dBi dipole that can only attach to the BT40NE's u.FL at full PA power, so the u.FL is driven through the nRF21540 and ANT_SEL picks the port. No module change.
- **Links:** #105, PR #106, `docs/analysis/module-antenna.md`.
- **Residual risk:** the ANT_SEL level (PK-2).
- **Bench:** yes (PK-2).

## Antennas and install

### AN-1. Owner constraint: rack antennas only in the wings
- **Difficulty:** ADR-0016's rule put the panels at the front of the stage, ≥ 6 m up, aimed upstage. The owner then allowed antennas only at the sides of backstage.
- **Chosen:** ADR-0021 replaces the rule (AN-3). Antennas, coax, 2482 carrier and channel plan stand.
- **Links:** ADR-0016 (rule superseded), ADR-0021, #101.
- **Bench:** G6.

### AN-2. Panel antenna rear lobes are worse than assumed
- **Difficulty:** the isolation study assumed 15 dB front-to-back. The chosen L-com HG2409P-NF (8 dBi, 75°/65°) states no F/B; its plots show −18 dB at 180° but rear lobes of **−9 dB** at 120–135°, so real rejection is 8.8 dB, not 14.4.
- **Chosen:** distance makes up the rest (Wi-Fi ≥ 4.4 m behind or beside, later folded into the wing rule). £72.12 each at ITM Components UK.
- **Links:** ADR-0016, PR #93, #92.
- **Residual risk:** the 60–90° points are estimates.
- **Bench:** **yes**, #92 pattern measurement.

### AN-3. Wing install rule
- **Difficulty:** R1 rests on placement (RF-7).
- **Chosen:** one HG2409P-NF per wing, 1 m offstage of the acting area, ¼ of the stage depth back; **4.0 m up** (3.7–4.5, never below 3.5); aimed at the **far upstage corner** (≈ 30° upstage of straight across); tilted **10° down** (5–15°). No Wi-Fi transmitter in either wing or on stage; backstage Wi-Fi ≥ 6 m from both antennas; crew phones in airplane mode; venue Wi-Fi on 1/6/11, not 13.
- **Links:** ADR-0021, `docs/human/antenna-install.md`.
- **Residual risk:** a venue that cannot keep the rule needs TD on for affected packs. With Wi-Fi 13 in use, packs 1 and 6–8 lose their gap copy.
- **Bench:** G6.

### AN-4. Antenna coax and cost
- **Chosen:** each panel on L-com CA3N050 (400-series, 15.2 m, £61.07) plus an LCCA30301-FT1.5 BNC-male/N-female jumper (£37.09). 4.2 dB of the 6 dB RK-2 budget. **£340.56 per rack ex VAT.**
- **Links:** ADR-0016, #92.
- **Residual risk:** longer runs in big houses eat the remaining 1.8 dB.
- **Bench:** no.

### AN-5. Pack whip, pigtail and counterpoise
- **Difficulty:** a quarter-wave whip needs a ground counterpoise; the u.FL sits ~71 mm from the whip exit, past the switch fork and light pipes; PK-5 wants ≥ 40 mm from whip to cell.
- **Chosen:** BAT Wireless BWIPX1-SMA-1.13L150 pigtail (LCSC C784404, $0.60), SMA cut off, 31 mm of 0.9 mm wire soldered on as the whip. Shield bonded to PCB ground. Whip-to-cell 40.9 mm. Pigtail loss 0.46 dB (limit 0.6 dB) is now in the link budget, which had no feed loss before; conducted headroom is 7.5 dBm UK.
- **Links:** PR #104 review S2, hw/REVIEW.md pack section, ADR-0012 item 2.
- **Residual risk:** hand-made whip length and solder joint vary; route needs a tie-down.
- **Bench:** yes, RSSI with whip versus PCB antenna.

### AN-6. Metal near the pack's PCB antenna
- **Difficulty:** Fanstel asks for 30 mm clear of external metal around the antenna. A belt-clip heat-set insert and screw sat directly under the overhang.
- **Chosen:** clip inserts moved to (−24, 3)/(−24, 17), clear of the overhang. The lid-post screws at (−30, 26.9) and (−43.9, 26.9) remain near it; use nylon there if the PCB-antenna fallback matters.
- **Links:** PR #104 review S1, hw/REVIEW.md.
- **Residual risk:** the PCB-antenna fallback is degraded; the whip is the primary radiator.
- **Bench:** optional.

### AN-7. Body blocking
- **Difficulty:** a costume and body between pack and antenna costs an assumed 10 dB; a body-blocked far pack next to an unblocked near pack is the worst near-far case.
- **Chosen:** budgeted as 10 dB body loss + 10 dB fade.
- **Links:** ADR-0021, PR #95 gain-plan comment.
- **Residual risk:** real body loss can be 15–20 dB.
- **Bench:** **yes**, R10 measurement in Phase 5/6.

## Pack hardware

### PK-1. SoC module with FEM and u.FL: Fanstel BT40NE
- **Difficulty:** bare nRF5340 gives +3 dBm; a discrete FEM means RF layout and loses modular certification.
- **Options:** BT40NE; BT40N + u.FL pad (not viable, #106); Raytac nRF5340+nRF21540.
- **Chosen:** BT40NE (nRF5340 + nRF21540, PCB antenna + u.FL). In the UK the FEM supplies +7 dBm conducted at low gain (~38 mA at +10 dBm versus 110 mA at +20).
- **Links:** ADR-0007, ADR-0015, ADR-0012.
- **Residual risk:** Fanstel-only part (not at LCSC, consigned for assembly), ~10-week lead time; LGA under the body needs X-ray.
- **Bench:** yes (PK-2, PK-3).

### PK-2. ANT_SEL level that selects the u.FL is unverified
- **Difficulty:** Fanstel does not say which ANT_SEL (P1.05, pad E1) level routes the nRF21540 to the u.FL.
- **Chosen:** firmware drives 1 at boot (`CONFIG_OP_FEM_ANT_SEL_UFL`, flagged UNVERIFIED in Kconfig). In Nordic's convention low = ANT1 and high = ANT2, so the default assumes the u.FL is on ANT2.
- **Links:** #107, PR #110, PR #119, #38, ADR-0012 item 2, `docs/analysis/module-antenna.md` §4.1.
- **Residual risk:** a wrong level sends PA power to the PCB antenna, not the whip: near-total link loss with the whip fitted. A Nordic DevZone note says to hold ANT_SEL low in power-down; that has not been checked. On the receiver, the board net called `ANT_SEL` (P1.01, PE4259 control) is a different signal; renaming it `RX_ANT_AB` was suggested but not done.
- **Bench:** **yes**: whip versus PCB antenna RSSI, or ask Fanstel.

### PK-3. FEM MODE pin: P1.04 or P0.24
- **Difficulty:** Fanstel's p.22 sample puts MODE on P0.24; its p.21 pad table and the schematic put it on pad E0 = P1.04. P0.24 is the pack's I2S BCLK.
- **Chosen:** follow the pad table (P1.04). The board-pin generator refuses P0.24 for MODE (tested). Firmware sets MODE to POUTB (low gain).
- **Links:** PR #110, PR #119.
- **Residual risk:** if the sample is right, the FEM gain mode is not controlled.
- **Bench:** **yes**, #38: conducted TX ≤ +7 dBm at the u.FL.

### PK-4. Preamp: one path, +6 dB, noise margin 3 %
- **Difficulty:** R5 asks ≤ 1 µV A-weighted input noise; R2 asks no clip at 0.6 Vrms. TI's OPA1656 model needs a login, so a generic macromodel with datasheet numbers is used.
- **Options:** dual-gain "never clip" stack; single path with PCM1840 DRE.
- **Chosen:** single non-inverting ×2 (330 Ω/330 Ω) into the PCM1840 with DRE on; second path on the schematic, unused. Noise 0.94 µV in ADR-0006 (6 % margin), now 0.967 µV in ngspice after the 100 Ω hot-plug resistor (MNA cross-check 0.961), a 3 % margin.
- **Links:** ADR-0006, ADR-0012, AUDIT-2.md B6, `tests/test_spice_preamp.py`.
- **Residual risk:** supply noise and op-amp 1/f noise not modelled.
- **Bench:** **yes**.

### PK-5. Op-amp input outside its common-mode range
- **Difficulty:** OPA1656 input CM must stay ≤ (V+) − 2.25 V = 2.70 V. With bias at 2.475 V, +IN peaked at 3.06 V at the PK-2 maximum. The macromodel has no CM limit, so the "no clipping" test missed it.
- **Chosen:** VCM = 180k/100k → 1.77 V; +IN 1.21–2.37 V; the SPICE clamp uses the datasheet 0.25/4.70 V swing; the test asserts the CM limit.
- **Links:** PR #75 review M1.
- **Bench:** no (lesson: assert datasheet limits the model does not enforce).

### PK-6. Mic jack hot-plug and ESD
- **Difficulty:** inserting a 3.5 mm plug shorts the tip and kicks the op-amp input to about −3 V through the 10 µF coupling cap; only the op-amp's internal diode (±10 mA) limits it. Crew plug in many times a show.
- **Chosen:** TPD1E10B06 ESD diode on the tip, 22 pF C0G shunt, BAV199 low-leakage clamp to the rails, 100 Ω series to the + inputs (noise 0.94 → 0.967 µV).
- **Links:** PR #75 review M2, ADR-0012.
- **Bench:** yes, repeated hot-plug.

### PK-7. Peak/clip LED thresholds on single-ended inputs
- **Difficulty:** with INxM AC-grounded, the largest pin swing is about VREF/2 = 1.375 V peak, −6.3 dBFS of the differential full scale. "Amber at −3 dBFS, red at clip" could never trigger.
- **Chosen:** amber ≥ −10 dBFS, red ≥ −7 dBFS (red within 0.7 dB of the analog clip).
- **Links:** PR #75 review S3, ADR-0012, SPEC PK-8.
- **Residual risk:** the single-ended swing limit is inferred.
- **Bench:** **yes**.

### PK-8. Battery-sense divider was hidden inside a comment
- **Difficulty:** in `hw/pack/pack.py` R13/C30 were commented out, so AIN0 saw the full cell through 1 MΩ. SKiDL ERC passed.
- **Chosen:** restored, with divider assertions (0.5 × 4.2 V = 2.1 V ≤ 3.3 V) and a grep check for SKiDL calls inside comments. The BOM went to $35.02 and passives were repriced from LCSC to get back to $34.60.
- **Links:** #83, PR #84, found in PR #81.
- **Bench:** no.

### PK-9. Boost converter ripple into the audio band
- **Difficulty:** TPS61023 PFM ripple can land in the audio band. The 100 Ω + 47 µF bias filter gives −29 dB at 1 kHz but only −10 dB at 100 Hz.
- **Chosen:** layout keeps the boost 14 mm from the ADC and 28 mm from the op-amp, solid L2 under it; 5 V rail to preamp output −33.6 dB at 1 kHz (asserted ≤ −30 dB).
- **Links:** ADR-0012 item 5, hw/REVIEW.md.
- **Residual risk:** low-frequency ripple untested.
- **Bench:** **yes**.

### PK-10. Audio coupling capacitors and power-up thump
- **Difficulty:** X7R coupling caps add distortion; 10 µF ADC coupling caps settle in ~0.1 s after SHDNZ release (the PCM1840 quick-charge is sized for ≤ 1 µF).
- **Chosen:** accepted; expect a thump on the first frames (PK-13 still met).
- **Links:** ADR-0012 items 6 and 9.
- **Bench:** **yes**, THD and start-up.

### PK-11. Battery path on thin inner copper
- **Difficulty:** BAT+, VBAT_RP and VSYS ran as 0.4 mm tracks on 15 µm inner copper (~0.9 A for 100 °C rise, fusing ~1.7 A in 1 s) behind a 3 A fuse, so the track would be the fuse. Track resistance (~0.15 Ω) also made the cutoff margin optimistic.
- **Chosen:** BAT+ → F1 → Q1 → SW1 → VSYS on L1 (35 µm) at 1.0 mm, routed first. Measured path resistance fed into the cutoff (PW-2).
- **Links:** PR #104 review M1, hw/REVIEW.md.
- **Bench:** no.

### PK-12. Bring-up test points
- **Difficulty:** the first layout had only UART pads and SWD; no rail, GND or I2S pads for the Phase 5 logic analyser.
- **Chosen:** TP3–TP11 added (VSYS, +5V, +3V3, +3V3A, +5V_BIAS, GND, I2S BCLK/FSYNC/SDOUT). Pads cost $0.
- **Links:** PR #104 review M2.
- **Bench:** used in Phase 5.

### PK-13. Jack thread and lock fit
- **Difficulty:** the Same Sky SJ1-3543 must lock both a Sennheiser plug and a DPA DAD6034 adapter (tip = mic+, ring and sleeve = ground, from the ew 100 G4 manual p.137).
- **Chosen:** SJ1-3543; fallback Switchcraft 35RAPC3BH3 (+$1.68, would exceed $35).
- **Links:** ADR-0012 item 1.
- **Residual risk:** fit unverified; DPA's own datasheet was not reachable.
- **Bench:** **yes**, physical fit.

### PK-14. JLC assembly files for the pack
- **Difficulty:** KiCad and JLC rotation conventions differ for SOT-23, SOIC and WQFN; the first BOM had no LCSC numbers; the BT40NE is not at LCSC.
- **Chosen:** rotation table in `outputs.py` (checked by test), an LCSC number on every line; F1 SF-1206F300-2 and the BT40NE are CONSIGN.
- **Links:** PR #104 review S3, hw/REVIEW.md.
- **Residual risk:** first check in JLC's CPL preview.
- **Bench:** no (DFM at upload).

## Receiver hardware

### RX-1. Board split and the keyed J1 connector
- **Difficulty:** the sub-board is a mezzanine on a 2×13 2.54 mm header. Rotated 180°, +12 V would land on nRESET/BOOT through 1 kΩ (~8 mA into nRF GPIOs) and +5 V on the UART pins.
- **Options:** asymmetric standoffs (easy to get wrong); a key pin.
- **Chosen:** pin 14 (a GND) is the key. The sub-board footprint has **no hole at 14**, so a full 26-pin header cannot be fitted; "KEY" silk on both sides; XFCN PZ254V-12-26P header (LCSC C22465887) with pin 14 cut. The main-board socket is a Harwin M20-7831346 with an M20-003 polarising key in position 14. A test checks footprint, board, BOM and ADR.
- **Links:** ADR-0014, ADR-0018, PR #81 review S3, PR #95 review S3, PR #116 review S1.
- **Residual risk:** that the M20-003 key seats in the M20-78 dual-row socket (ADR-0018 item 6). A stale comment in `hw/rx/footprints_rx.py` still names a Samtec TSW-113-17-G-D header.
- **Bench:** yes, first unit.

### RX-2. Output thump on power loss
- **Difficulty:** the single-supply balanced driver ramps its 6 V common mode on power-up (~0.9 V differential for seconds) and drops unmatched on power-down. "Mute the desk first" does not help on an unplanned power loss, which is when a sub-bass thump hurts a PA.
- **Chosen:** normally-open DPDT relay (TQ2SA-12V) in both legs, closed by firmware ≥ 5 s after boot, wired-AND with a TPS3808G01 supervisor on raw +12 V (trip 10.78 V), which also mutes the DAC (XSMT). BAT54 hold-up keeps the op-amps linear while the relay opens. Power-cycle sim: < 1 µV differential at the XLR. About $4.2 per channel.
- **Links:** PR #81 review M1, ADR-0014, `hw/spice/rx_driver_power.cir`.
- **Residual risk:** relay release time is modelled as 8 ms.
- **Bench:** **yes**.

### RX-3. Phantom power short
- **Difficulty:** with P48 on, the output caps hold ~39 V; shorting the pin discharged ~1.7 A for ~1 ms into a BAV99 rated 1 A for 1 ms.
- **Chosen:** 4× S1J (IFSM 30 A). Sim: 0.86 A peak, 0.38 mA²s against 3.7 A²s. Cap holds ~21 V because of the cap-side 10 k bleed.
- **Links:** PR #81 review M2, ADR-0014.
- **Bench:** yes, hot-patch test.

### RX-4. Op-amp input overcurrent at power-down
- **Difficulty:** the 47 µF VCM cap discharged through the OPA1656 input ESD diodes (±10 mA limit) when +12 V collapsed.
- **Chosen:** BAT54 from VCM to +12VA.
- **Links:** PR #81 review M3.
- **Bench:** no.

### RX-5. Live insertion and LDO absolute maximum
- **Difficulty:** the 5 V TVS clamps at ~9.2 V but the TLV755P's input limit is 6 V; a hot insertion rings to ~10 V.
- **Chosen:** TLV76733 LDOs (18 V abs max) and a 47 µF electrolytic damper on +5 V.
- **Links:** PR #81 review S1, ADR-0014.
- **Bench:** optional.

### RX-6. Hum from the common-mode reference
- **Difficulty:** VCM ripple reaches the XLR differentially at ×2.96; 10 mV of 100 Hz brick ripple would come out ~10 dB above the noise floor.
- **Chosen:** two RC poles on VCM; −100 dB at 100 Hz (asserted ≤ −80). C44 moved to 2.4 mm from the op-amp pin.
- **Links:** PR #81 review S2, PR #116 review N3.
- **Bench:** yes.

### RX-7. Driver stability into long cable
- **Difficulty:** OPA1656 specifies only 100 pF direct load; 50–100 m of multicore is 5–20 nF. The macromodel's second pole (30 MHz) is assumed, not from the datasheet.
- **Chosen:** 22 Ω isolation; sim into 10 nF + 600 Ω gives 50° / 49° phase margin, 0.35 % overshoot.
- **Links:** PR #81 review S5, ADR-0014 item 3.
- **Residual risk:** if it rings, move the 22 Ω inside the loop (re-spin).
- **Bench:** **yes**, step into 10 nF.

### RX-8. Output level and headroom
- **Difficulty:** PCM5102A full scale is 2.1 Vrms typical only, so +18 dBu could be exceeded per unit.
- **Chosen:** keep +17.98 dBu nominal; outputs reach the swing limit at +19.4 dBu on the worst rail (11.2 V), 1.4 dB headroom (asserted ≥ 1 dB).
- **Links:** PR #81 review S6, ADR-0014.
- **Bench:** yes.

### RX-9. Receiver module changed from BT40NE to BT40E
- **Difficulty:** see RF-9. The BT40E has a different footprint (14 × 16 mm) and no FEM; its nine FEM pads become plain GPIO.
- **Chosen:** BT40E (Digi-Key UK £9.78 at 100, 803 in stock, 10 weeks). No pad moves for the pins this board uses. Receiver builds disable the FEM devicetree node and fail to compile if it is enabled.
- **Links:** ADR-0021, ADR-0014 amendment, #112, PR #113.
- **Residual risk:** u.FL position on the footprint is scaled from a drawing (F.Fab only); HFXO load caps 11 pF for the BT40E versus 12.5 pF for the BT40NE need setting in the board target.
- **Bench:** yes, crystal trim.

### RX-10. 50 Ω line width: the closed-form formula was wrong
- **Difficulty:** the closed-form CPW formula gave 0.39 mm, which is ~46 Ω on this stackup because it does not hold for gap > height.
- **Chosen:** 2D field solve (`hw/rx/rf_line.py`): w 0.31 mm, gap 0.25 mm → 51.5 Ω bare, ~49.3 Ω with solder mask. An independent solver in review agreed within ~1 Ω. The pack's 0.346 mm microstrip is ~51 Ω, not 50.
- **Links:** PR #116 and review N1.
- **Residual risk:** longest line is 4.6 mm (0.07 λ), so the error barely matters.
- **Bench:** no.

### RX-11. Netclass clearance overridden by a custom rule
- **Difficulty:** an unconditional `JLC copper clearance` rule (0.09 mm) in the `.kicad_dru` overrode every netclass, so pours filled at 0.09 mm: 493 gaps, 157 under 0.13 mm on the P48 audio nets (IPC-2221 B4 asks 0.13 mm for 31–100 V coated).
- **Chosen:** rule deleted in both `rx.kicad_dru` and `pack.kicad_dru`; netclasses apply (Default 0.127, Power/Audio_I 0.15, RF 0.25); boards refilled. `test_pour_gaps_per_class` probes the committed fill (≥ 0.125 mm everywhere, ≥ 0.15 mm to Audio_I) with a positive control.
- **Links:** PR #116 review M1, hw/REVIEW.md.
- **Bench:** no.

### RX-12. RF grounds and polarised-part orientation
- **Difficulty:** every GND pad joined the pour through thermal spokes, including u.FL and switch grounds at 2.4 GHz. The relay K1 is polarised and its JLC rotation was unverified; a 180° error would mean no audio from any board in the batch.
- **Chosen:** solid zone connection on RF grounds (tested); K1 gets a pin-1 dot and "+", CPL +270° for the TQ2SA; a test covers pin-1 markers and CPL rotation for every polarised part.
- **Links:** PR #116 review S2, S3.
- **Residual risk:** EasyEDA's footprint for C2684447 could not be fetched (HTTP 403); K1 is the first part to check in JLC's preview.
- **Bench:** no (DFM preview).

### RX-13. Antenna switch isolation and probing
- **Difficulty:** PE4259 isolation is about 18–20 dB at 2.4 GHz; the U.FL jumper costs ~0.3 dB. Test pads for DRV_OUTA/B, XSMT and OUT_EN are missing.
- **Chosen:** accepted; probe at K1's pads, R37/R38 and R62 for now; add pads at the next schematic pass.
- **Links:** ADR-0014 item 5, PR #116 review N5.
- **Bench:** yes.

### RX-14. I2S on the backplane
- **Difficulty:** eight 3 MHz BCK stubs would run beside the LNA and splitters for a digital add-on that does not exist.
- **Chosen:** R33–R35 not fitted (DNP).
- **Links:** PR #81 review S4, ADR-0014.
- **Bench:** no.

## Rack hardware

### RK-1. RF chain per antenna and the QPQ1907 pinout error
- **Difficulty:** RK-2 asks LNA NF ≤ 2 dB, input P1dB ≥ −10 dBm, IIP3 ≥ 0 dBm, then a 1:8 split. The first schematic had the QPQ1907 pins wrong (output tied to ground), so the board had no RF path. Qorvo's site was rate-limited during the first pass.
- **Chosen:** BNC → ESD103 → bias-T → TPS259541 bias eFuse → DC block → ESD101 → QPL9057 → QPQ1907 (pins 1 in, 4 out, 2/3/5 GND, from the datasheet) → 3-stage Wilkinson → 8 u.FL. A test walks the RF path through series elements from each BNC to every slot port.
- **Links:** ADR-0018, PR #95 review M1.
- **Residual risk:** the QPL9057 spec table is tested only at 3.5 GHz, used as a worst-case proxy.
- **Bench:** yes, VNA.

### RK-2. Bias-T resistor would burn out
- **Difficulty:** a default 0402 10 Ω (1/16 W) overloads at 79 mA and dissipates 2.4 W at the 0.49 A eFuse limit.
- **Chosen:** 1 Ω 2512 (0.27 W at the limit, 27 % of rating); every resistor's power rating is now asserted.
- **Links:** PR #95 review M4.
- **Bench:** no.

### RK-3. 12 V input has no fuse
- **Difficulty:** a 15–24 V brick on the 2.1 mm jack would crowbar the SMBJ12A with nothing to interrupt the current; 24 V also exceeds the TPS2595's 20 V limit.
- **Chosen:** 4 A fast fuse (0451004.MRL) ahead of the reverse-polarity FET and TVS.
- **Links:** PR #95 review S1, ADR-0018.
- **Residual risk:** the PJ-063AH jack is not locking.
- **Bench:** no.

### RK-4. Wilkinson splitter realisation
- **Difficulty:** the Hammerstad-Jensen model ignores solder mask (−1 to −3 Ω); one fixed net-tie footprint cannot be both a 17.8 mm arm and a 5 mm feed.
- **Chosen:** IL 10.61 dB (scikit-rf 10.24), isolation ≥ 30.3 dB, holding εr 4.2–4.6 and ±10 % width. Layout to use JLC's calculator with mask or open the mask, and real track geometry for the net-ties.
- **Links:** PR #95 review S5, ADR-0018 item 5.
- **Bench:** **yes**, VNA.

### RK-5. Host carrier and UART fan-out
- **Difficulty:** 8 receivers need 8 UARTs plus reset and boot lines; the host must have no wireless (R1).
- **Options:** CM4IO + CM4 UARTs + 2× SC16IS752; CM4 on the main board; USB hub + FT4232H (datasheet unreadable); Pi 4/5.
- **Chosen:** CM4002008 (no wireless) on the official CM4IO via a ribbon; CM4 UART0/3/4/5 for slots 0–3; two SC16IS752 on SPI1 (≤ 4 MHz) for slots 4–7. The second SC16IS752 needs a custom overlay.
- **Links:** ADR-0018, PR #95 review S4, N2.
- **Residual risk:** CM4 stock (SC0681 is a drop-in).
- **Bench:** yes, host bring-up.

### RK-6. XLR protection against phantom power
- **Chosen:** SMAJ58CA (58 V standoff) on XLR pins 2/3 on the main board, to survive P48 at 52 V.
- **Links:** ADR-0014 item 1, ADR-0018.
- **Bench:** no.

### RK-7. Rack layout (#34)

The rack main board (`hw/rack/layout.py` → `hw/rack/rack.kicad_pcb`) and its 1U chassis fit (`mech/rack.py`). Review record: `hw/REVIEW.md`, rack section. Entries RK-7a onward.

### RK-7a. One board filling the 1U case
- **Difficulty:** eight 48 × 90 mm receivers at the 52 mm ADR-0014 pitch, two RF chains, the CM4 IO board and every rear-panel connector have to fit the owner's case, the Hammond RM1U1913SBK (330 mm deep, inside 415.30 × 323.85 × 40.09 mm, Hammond drawing).
- **Options:** one board filling the case; a narrow backplane strip plus a host tray joined by cables.
- **Chosen:** one board, **412.0 × 321.5 mm, 4 layers (JLC04161H-7628, 1.6 mm), 444 footprints, 2288 tracks, 6267 vias (5574 GND)**. The independent review of #126 kept the full-size board; it moved the front edge back to 321.5 mm (was 323.0), giving 2.35 mm to the front panel instead of 0.85. All panel connectors are on the board. The CM4 IO board sits on 10 mm spacers above it, and the receivers stand 11 mm up on their sockets.
- **Fit (`mech/rack.py`, `tests/mech/test_rack_fit.py`, CadQuery in CI):** - **Fit (`mech/rack.py`, `tests/mech/test_rack_fit.py`, CadQuery in CI):** lid over the receivers **3.39 mm**, over the CM4 IO board 5.89 mm, side walls 1.65 mm, 4.0 mm between receivers, **2.35 mm from the board's front edge to the front panel**, with the side-looking LEDs' lenses on that edge (2.35 mm from the 2.5 mm holes, checked). The longest u.FL jumper path is 40.8 of 100 mm. 106 box checks and the CadQuery volume test pass.
- **Case features (Hammond drawing, re-read for #126):** section LL gives 323.85 mm clear between the 3.18 mm panels, so the front gap is real. Section KK also draws, beyond the cut, the cover-screw speed nuts and lugs of the side extrusion: about 0–9.6 mm in from each side wall, z ≈ 6.6–11.4 mm, at the four side cover screws (top view: ~60 mm from each end). The board edge sits 1.65 mm from the wall at z 5.0–6.6, so it may touch them. The 2D drawing does not settle it, and the STEP model is not downloadable (403). The board has no parts or tracks there (GND pour and edge stitching only), so a 10 × 12 mm edge notch at those four places is a no-risk fix if the dry fit shows contact.
- **Links:** `hw/rack/out/fab/mech.json`, `mech/out/rack_*.png`.
- **Residual risk:** the PCB order is the dearest single line after the case: £300 est. for JLC's minimum of five boards with ENIG, the large stencil, extended-part fees, DHL for ~2 kg and import VAT (RK-7k); quote it before ordering. The side-lug contact above is unconfirmed.
- **Bench:** a dry fit of the bare board in the case before assembly (side lugs, front gap, LED holes).

### RK-7b. Routing a 412 × 321.5 mm board without Freerouting
- **Difficulty:** Freerouting is not available. The pack's 0.1 mm grid router (`hw/pack/router.py`) needs 13 M cells per layer for the whole board.
- **Options:** one coarse grid; a windowed grid per connection.
- **Chosen:**
  - `hw/rack/wrouter.py` routes each connection in a window round the pad and the nearest connected copper.
  - The 270 mm host-to-rear hops used up A*'s 900 k node budget on near-ties, so windows longer than 150 mm get ×12.
  - The bias eFuses' EN/FLT pads sit inside the B.Cu +12V_BUS rear strip, fenced by GND vias and the L1 RF area. Those four nets route first, on F.Cu and In2 only, before the strip joins the router's copper. Their vias become holes in the strip.
  - The EN pull-down and FLT pull-up sit at the host end of their nets, so no +3V3 has to run to the rear.
  - GND pins the generic fan-out walled in are wired by hand: TPS2595 pin 8 to its pad, QPL9057 GND pins to its pad, QPQ1907 pads to vias, TPS62933 pin 4.
- **Links:** `hw/rack/layout.py` (`gnd_hand`, `EARLY_NETS`).
- **Residual risk:** none electrical. A run takes about 35 minutes, and the whole layout re-runs on any change. After DRC, `prune_dangling()` removes the escape vias the router did not need, then their stubs; it undoes itself if anything goes unconnected.
- **Bench:** no.

### RK-7c. Wilkinson trees as routed
- **Difficulty:** ADR-0018 asked ≤ 11 dB worst-port loss for the splitter, ≥ 20 dB isolation and ≥ 15 dB return loss on FR-4. The ports must sit behind each receiver, so the distribution lines are long.
- **Options (#126 review):** this tree, at its as-routed loss; a central splitter feeding 16 coax runs to the slots (about 2 dB better NF, but PIMD worsens to 1.7 m on axis, and 16 runs would have to fit in 1U).
- **Chosen:**
  - **Lines:** near-microstrip on L1 over a solid L2, with a 0.5 mm gap to the L1 pour (DRC rule "RF pour gap"). The 2D field solve (`hw/rx/rf_line.py`) gives 0.35 mm = 50.2 Ω and 0.17 mm = 70.3 Ω, so λ/4 = 18.02 mm. Netclass clearances only, no 0.09 mm override.
  - **Model:** `hw/rack/rf_routed.py` re-models the drawn copper in scikit-rf: lines, bends, T-junctions, the resistor parasitics and A's two vias. Corners are ±10 % width × εr 4.2/4.6.
- **As routed:** tree A worst port **13.66 dB** (13.53–13.66 over the eight ports), tree B 13.47 dB; 13.85 dB at the tolerance corners. Isolation ≥ 39.4 dB (≥ 32.2 at the corners), return loss ≥ 28.2 dB (≥ 22.6). Each tree has 252 mm of divider arms (28 λ/4 arms of 18.02 mm) and 834 mm (A) / 754 mm (B) of 50 Ω distribution line, with 72 bends; A's feed crosses under tree B on L4 through 2 vias. The ideal split is 9.03 dB. The rest is conductor and FR-4 loss (≈ 12 dB/m on a 0.35 mm line) over the ~180 mm each branch needs to reach ports spread over 400 mm.
- **Limit amended (#126):** SPEC RK-5 and ADR-0018 now say **≤ 14 dB as routed** (was ≤ 11; the ADR keeps the history). Reasons:
  - the 52 mm slot pitch sets the tree's length;
  - NF is 12.86 dB worst against the 21.1 dB need (RK-7i);
  - the extra loss improves PIMD (1.2 m on axis against the 1.5 m spec);
  - the central splitter was rejected (see Options).
  `tests/test_rack_layout.py` and `rf_routed.py` assert 14 dB.
- **Links:** `hw/rack/out/rf_routed.json`, `audit.py` Audit 6 (reads it), ADR-0018.
- **Residual risk:** FR-4 tan δ (0.02) and the bend and junction models are estimates.
- **Bench:** **yes**, VNA one tree, input to each port and port to port.

### RK-7d. The LNA path at 50 Ω up to the pins
- **Difficulty:** the work-in-progress used 0.25 mm (59.5 Ω by the field solve) into the QPL9057 and QPQ1907 pins, and its diagonal into LNA pin 7 grazed GND pin 6.
- **Chosen:** every through-line from the BNC to the BAW output is 0.35 mm (50.2 Ω). Each line enters its pin straight along the pin axis, 0.2 mm from the GND pins either side (RF netclass 0.15). Only the shunt-part stubs (ESD, choke, 18 nH) are 0.25 mm; each is ≤ 1.5 mm, under λ/45. The QPL9057 VBIAS pin sits 0.5 mm from RF_IN, so its stub to the decoupling cap is drawn by hand.
- **As routed:** BNC centre pin to the BAW input is **14.6 mm (A) and 14.4 mm (B) of 50 Ω line, 0.20 dB**: ANT 9.5 mm, LNA_IN 1.3 mm, RFIN 1.4 mm, RFOUT 1.4 / 1.2 mm, OUT 1.1 mm; plus 2.7 mm of shunt stubs.
- **Links:** `hw/rack/layout.py` `rf_frontend()`, `hw/rack/out/rf_routed.json` "frontend".
- **Residual risk:** small.
- **Bench:** within RK-7c's VNA check.

### RK-7e. Buck switch node
- **Difficulty:** the TPS62933 SOT-583 has SW, BST, SS and FB on one 0.5 mm-pitch side. A 1.5 mm SW track cannot leave pin 5, and it walled in BUCK_EN, BUCK_FB and BUCK_SS (all three failed).
- **Chosen:** SW is a small F.Cu pour from pin 5 to the inductor and boot cap, as in TI's layout example (SLUSEA4D fig. 10-1). BST goes to the boot cap right of pin 6, SS climbs past pin 8, FB goes straight up to its divider, and EN goes left; a 100 nF sits at VIN/GND pins 3/4. The inductor moved up 2.25 mm, clear of slot 4's test pads.
- **Links:** `hw/rack/layout.py` `BUCK_SW_ZONE`.
- **Load (#126 review):** the real 5 V load is about 1.3 A (eight receivers, two LNAs, the 3.3 V LDO) against the 3 A buck. That gives about 10 mV of ripple and about 30 °C of rise. Only several faults at once would push it past 3 A, and the per-slot eFuses trip first.
- **Residual risk:** the output caps are 4–6 mm from the inductor, joined through the B.Cu +5V pocket.
- **Bench:** **yes**, 5 V ripple and SW ringing at full load.

### RK-7f. eFuse current-limit pins
- **Difficulty:** the TPS2595 ILM (pin 7) is on the side opposite where the first placement put its resistor; 10 eFuses failed to route.
- **Chosen:** every TPS2595 cluster now has the same layout: ILM resistor just above-right of pin 7, dV/dt cap beside pin 1, input cap below, output cap above-right. Pin 8 goes straight to the exposed pad, so its fan-out via no longer blocks pin 7.
- **Residual risk:** none.
- **Bench:** no (limits checked in #95's tests).

### RK-7g. Parts fixed at layout (owner list, 2026-11-01; closes SC-4's rack items)
- **39 nH bias-T choke, LCSC C142171 (Chilisin CS0603-39NJ, SRF 2.2 GHz):**
  - Above its SRF it looks like its 0.13 pF self-capacitance. With the SRF anywhere from 2.0 to 2.44 GHz, the choke is ≥ 1.2 kΩ at 2.44 GHz, which costs about 0.002 dB on a 50 Ω line. The far end is RF-grounded (100 pF + 10 nF).
  - It is rated 600 mA, against the 0.52 A worst-case bias eFuse limit.
  - Accepted in place of the LQW18AN; ADR-0018 is amended.
  - **Bench:** S21 through the bias-T, within RK-7c.
- **Crystal: HCI XC32M4-14.7456-F20NLDTL (LCSC C3034317, ESR 60 Ω, 20 pF, −40…+85 °C, 6,684 in stock; #126 review).** It replaces the owner-listed AKER C6523919 (ESR 100 Ω, −20…+70 °C), which met the review's ESR and temperature asks only on paper margins. The load caps are now 2 × 33 pF (FH C1562), which with ~3 pF stray gives 19.5 pF.
  - Pierce start-up needs gm_crit = 4·ESR·ω²·(C0 + CL)² = **1.04 mA/V** (C0 3 pF est.).
  - Against an est. 8 mA/V for a 3.3 V unbuffered CMOS stage (NXP gives none), the margin is **7.7×**, over the usual 5×. `audit.py` asserts it.
  - **Temperature basis:** inside the closed 1U case, not the wing: 0–40 °C ambient + ~15 °C internal rise (CM4 up to 9 W, buck, eFuses) = 55 °C est. The −40…+85 °C rating covers it with 30 °C to spare.
  - **Bench: yes.** It must still start with 300 Ω (5 × ESR) in series.
- **6.8 µH inductor:** Bourns SRP5030T-6R8M (Irms 4.0 A, Isat 4.3 A, DCR 76 mΩ, Bourns datasheet), bought in the UK and consigned; LCSC C177249 is only 3.5 A. The buck peaks at about 3.4 A at 3 A out.
- **4 A fuse, C27515:** Littelfuse 0451004.MRL in the 2410 case (6.1 × 2.5 mm, LCSC record). Main's footprint name `Fuse_Littelfuse_NANO2_451_453` did not exist; the board uses KiCad's `Fuse_Littelfuse-NANO2-451_453`, the 2410 land (1.96 × 3.15 mm pads), not an 1808.
- **Slot socket, BOOMELE 2×13 8.5 mm (C64320):** replaces the Harwin M20 + key. Contact 14 is pulled and the cavity plugged at assembly; the footprint has no hole at 14, so it matches the receiver's J1 (pin 14 cut). ADR-0014 and ADR-0018 are amended.
- **U.FL, C88373:** one code project-wide; the receiver BOM moves to it too (C88374 is the 80-piece reel of the same part).
- **Other LCSC codes:** C85833 (ferrite), C160315 (JST VH), C5154126 (NC3MAH), C125113/C125114 (LTST-S270 LEDs), C9138 (2×20 header), C361616 (18 nH).
- **From UK distributors:** TE 5415025-1 BNC (or Molex 73138-5033), the CUI PJ-063AH jack, the QPQ1907 and the SRP5030T.
- **Links:** `hw/rack/outputs_rack.py` LCSC table, `hw/rack/prices.py`.
- **Residual risk:** LCSC stock for the Extended parts is unconfirmed.
- **Bench:** as marked.

### RK-7h. Wing coax: a 30 ft lead does not reach the far wing
- **Difficulty:** the brief priced one L-com CA3N030 (9.14 m) per wing. Audit 5 routes the cables from the rack in one wing along the floor, across the stage at grid height and up each 4 m boom (ADR-0021), with 5 % slack and 1 m of dressing. The far wing then needs 15.2 m (6 m stage), 18.3 m (9 m) or 21.5 m (12 m); even a 6 × 6 m stage needs 13.6 m. With the rack at centre-front, each wing still needs 9.9–14.7 m.
- **Options:** two CA3N030 (does not reach); CA3N030 + CA3N050 (stages ≤ 6 m wide only); CA3N030 + CA3N075 (every ADR-0021 venue).
- **Chosen:** **CA3N030 near + CA3N075 far** (+£42.22 against the brief).
  - **Far:** 22.86 m × 0.223 dB/m + 0.3 dB HG2409P lead + 0.1 dB adapter + 3 × 0.15 dB mated pairs = **5.95 dB**, inside the 6 dB design target.
  - **RK-2 rebased (#126 review):** the coax limit is now the wing NF need, not the 6 dB budget. Up to 14.2 dB of wing coax keeps NF ≤ 21.1 dB, and even the 100 ft CA3N100 (7.65 dB) gives NF 14.51 dB, 6.6 dB inside (Audit 6).
  - **Near:** 2.89 dB.
  - **Adapter:** an N-socket to BNC-plug adapter (RS 285-6398, £8.40) replaces the £37.09 LCCA30301-FT1.5 lead. It saves £28.69 per wing and one mated pair.
  - SPEC RK-2 and `docs/human/antenna-install.md` now describe this kit.
- **Links:** `audit.py` Audit 5, `hw/rack/prices.py` ANTENNA_KIT.
- **Residual risk:** small. A venue wider than 12 m needs the 100 ft lead, which costs 1.7 dB of NF but stays well inside the need.
- **Bench / site:** measure both runs at the first venue.

### RK-7i. Gain plan with the as-built losses
- **Difficulty:** recheck NF and headroom with the new coax, the 100 mm u.FL jumpers (Taoglas CAB.6012, 3.1 dB/m → 0.5 dB with two mated pairs) and the as-routed Wilkinson.
- **Result (`audit.py` Audit 6):** system NF on the worst carrier is **12.86 dB** at the 6 dB coax budget (12.81 dB on the far wing's 5.95 dB, 10.97 dB at 2442 MHz), against the 21.1 dB need: **8.2 dB of margin** (was 11.48 dB, 9.6 dB margin). R1 noise cost 0.028 dB (Audit 3 geometry; 0.020 before). Nothing compresses with a pack 0.5 m on axis.
  - The shorter jumper alone would give the radio 0.5 dB more and push PIMD out to 1.6 m on axis (third-order IMD rises 3 dB per dB). With the as-routed tree it holds from **1.2 m on axis** (1.5 m before); `tests/test_rack_rf.py` asserts 2 m. ADR-0021's install rule keeps packs off axis (headroom +12 dB).
- **Residual risk:** an actor standing on axis within 1.2 m of a boom antenna.
- **Bench:** G5.

### RK-7j. Rear panel: the USB-C service port
- **Difficulty:** the Adafruit 4056 panel lead (The Pi Hut 103462) is 28 mm across its ears; mounted flat, it would hit XLR 1 and XLR 2.
- **Chosen:** mounted upright between them, per the Premier Cable drawing C12984-001 (Adafruit product files):
  - flange 28 × 8.5 mm, M3 × 12 screws 20 mm apart, 13 × 13 mm overmold running 40.5 mm back;
  - cut-out: a 4.0 × 9.6 mm slot (Type-C shell 8.94 × 3.26 mm + 0.35 mm a side, R2 ends) and two 3.2 mm holes at ±10 mm, 21 mm above the case floor;
  - `mech/rack.py` models the flange and overmold separately.
- **Residual risk:** the drawing gives no flange thickness (4.5 mm est.).
- **Bench:** dry-fit before drilling.

### RK-7k. Rack cost against the target
- **Difficulty:** the brief targets about £800–830 ex VAT; the rack was £953.92.
- **Result (`audit.py`, GBP ex VAT; UK VAT 20 % on top):** **£1,501.50 ex VAT** (£1,801.80 inc VAT):
  - main board, host and cables £709.04;
  - eight receivers £187.04;
  - antennas, coax and adapters £294.86;
  - two Thor LS003 stands and two HGX-PMT07 kits £310.56.
  Like for like with the £953.92 (no stands): **£1,190.94**, about £360 over the £800–830 target.
- **PCB (#126 review):** the main-board PCB line is now the whole JLC order, **£300 est.** (the reviewer's £250–350 range; JLC's quote page needs a browser). It covers five 4-layer 412 × 321.5 mm ENIG boards, the large stencil, extended-part fees, DHL for ~2 kg and import VAT; it was £40 for one bare board.
- **Chosen:** reported as is. The case (£140.76) and the CM4 (£79.20) are fixed by the owner, and RK-7h adds £42.22.
- **Residual risk:** the PCB order (£300) and 15 small main-board lines are still estimates (£343.90 in all).
- **Bench:** no.

## Firmware and timing

### FW-1. Air format forced by the simulator
- **Difficulty:** BabbleSim's nRF RADIO model accepts only the BLE 2M PDU layout and aborts otherwise. SPEC AIR-2 had no S0 byte. bsim only sees nrfx HAL register writes.
- **Options:** patch the model (sim diverges from upstream); add the header.
- **Chosen:** AIR-2 gains a 1 B header (format version). +4 µs per packet, already in `audit.py`. All RADIO/TIMER access through nrfx HAL.
- **Links:** ADR-0009, #18, PR #66.
- **Bench:** no.

### FW-2. Pack frame skips from k_timer rounding
- **Difficulty:** a 1 ms `k_timer` is 33 RTC ticks = 1007 µs, so its phase swept past the net core's latch every 142 frames. Any other timeout within 3 ticks pushed a frame 61 µs late: a repeat, then a sequence skip. A 50 ms console poll gave 1 skip per 10 s.
- **Options:** frame-clock ISR phased to the latch; 2-frame FIFO (+1 ms latency); leave it.
- **Chosen:** the app core is paced by the audio frame clock, phased 100 µs before the latch; the net core keeps sending the newest frame (no queue). Stress tests in CI with a negative control.
- **Links:** ADR-0020, #87, PR #100.
- **Bench:** no.

### FW-3. 435 µs of latch-to-air wait missing from the latency budget
- **Difficulty:** the payload was latched in the DISABLED interrupt after copy B, 435 µs before it went on air; SPEC §2 did not count that. True SYS-2 was ~3.1 ms.
- **Chosen:** latch from TIMER0 COMPARE3 at t0 − 20 µs (same for 42 B and 81 B); a build assert checks it falls after copy B ends. Frame done → TXEN is 120 µs (was 535). SYS-2 2.67 ms (2.28 ms with FLT=1).
- **Links:** #98, PR #111, ADR-0020 update.
- **Residual risk:** copy A's DMA starts 40 µs after t0, so the latch ISR has 60 µs of slack.
- **Bench:** yes, latency.

### FW-4. Pack frame lead drifts on silicon (HFCLKAUDIO PI loop)
- **Difficulty:** on silicon the frame clock is I2S from HFCLKAUDIO, whose PLL cannot hit 12.288 MHz (+0.371 ppm; one FREQ step is 3311 ppb). Against the net core's TIMER0 the 100 µs lead drifts 1.34 ms/h; open loop, one frame skips every ~40 min. bsim has one crystal per device, so it cannot separate the two clocks.
- **Options:** PI loop on HFCLKAUDIO from the latch margin; open loop; restart I2S when margin runs low.
- **Chosen:** PI loop (kp 2000 ppb/µs, ki 100 ppb/µs/report) on the earliest-frame margin, reported every 100 frames, with sigma-delta dither between FREQ steps. A test-only rate offset (`-op_fclk_ppb`) separates the clocks in bsim. 1 simulated hour at +0.371 and ±40 ppm: 0 skips, margin 100 ± 1 µs.
- **Links:** ADR-0022, #97, PR #114.
- **Residual risk:** that writing FREQ once per ms does not disturb the PLL; the I2S capture path is first exercised on silicon.
- **Bench:** **yes**.

### FW-5. Receiver clock recovery and jitter slot
- **Difficulty:** pack and receiver crystals differ (±20 ppm → 1 ms drift every ~50 s); the receiver must slew its DAC clock. A 1-frame jitter buffer would push SYS-2 to 3.72 ms. bsim has no HFCLKAUDIO and no I2S.
- **Options:** 6-sample setpoint on DAC sample position; 1-frame setpoint; ring-count input (8-sample steps, noisy).
- **Chosen:** setpoint 6 samples (125 µs), loop input = written − played in Q16, PI kp 26000 / ki 8 ppb, quantised to the 3311 ppb step. A software DAC clock on TIMER2 stands in for I2S in bsim. 1 h at ±40 ppm: 0 slips, error ≤ 0.28 samples.
- **Links:** ADR-0013, #24, PR #77, AUDIT-2.md B4.
- **Residual risk:** if real arrival jitter exceeds 125 µs, raise the setpoint (~75 µs left in the budget line).
- **Bench:** **yes**, lock and slips on real crystals.

### FW-6. Receiver tracking reference and antenna choice
- **Difficulty:** a one-switch receiver never hears its other antenna unless it probes; a probe moves a gap copy to the far wing, where Wi-Fi wins; a hot 3 MHz neighbour blocks the stronger antenna for ~2 % of windows, too few for 1 dB ageing to react (1.0 % frame loss with TD off).
- **Chosen:** timing reference = RADIO ADDRESS captured over DPPI, ±W window. Probe one window per channel every **1000** frames (was 100). New miss-triggered switch: on a missed window, move to the other antenna if its last window was valid and ≤ 12 dB weaker, hold 1000 windows.
- **Links:** ADR-0011, ADR-0021, #23, PR #73, PR #103, `fw/tests/rx_ant`.
- **Residual risk:** tuned on a model with two antennas replayed per carrier.
- **Bench:** G5/G6.

### FW-7. Time diversity as a per-pack setting
- **Difficulty:** TD must be selectable per pack without a downlink and without a receiver setting that can be wrong.
- **Chosen:** the pack's `td on|off` command; the receiver infers TD from payload length at lock (81 B versus 42 B) and re-locks if it changes. Lost frames on both copies are rebuilt from packet n+2's `td_audio`.
- **Links:** ADR-0017, #91, PR #102.
- **Bench:** G5.

### FW-8. Board pins generated from the netlists
- **Difficulty:** hand-written devicetree pins drift from the schematic.
- **Chosen:** `fw/boards/openpack/gen_pins.py` writes the pin files from `hw/*/out/*.net` and refuses unmapped nets, double roles, battery sense off an AIN pin, LFXO/NFC pads, USB off its pads, and wired nRF21540 pads. `--check-dts` compares every compiled devicetree against the netlist in CI.
- **Links:** #118, PR #119.
- **Bench:** no.

### FW-9. MCUboot pulled in an insecure test RNG
- **Difficulty:** the openpack app-core MCUboot image enabled `TEST_RANDOM_GENERATOR`: the app core has no RNG (entropy is served by the net core over HCI, which MCUboot lacks), and the RSA/PSA path selects the test RNG without an entropy driver. CryptoCell needs nrf_security, not in this tree.
- **Options:** add nrf_security; switch signature type.
- **Chosen:** MCUboot ECDSA-P256 (verify-only, tinycrypt, no RNG) on openpack_pack and openpack_rx. nrf5340dk builds are unchanged and still warn.
- **Links:** #120, PR #121.
- **Residual risk:** images are signed with the default development key `root-ec-p256.pem`. Replace it with a private key before units leave the bench.
- **Bench:** no.

### FW-10. UK power ceiling enforced at build time
- **Difficulty:** UK needs ≤ +7 dBm conducted (9 dBm EIRP with a 2 dBi whip).
- **Chosen:** build assert: SoC output (−3 dBm with FEM) + FEM gain (10 dB) ≤ `OP_TX_MAX_CONDUCTED_DBM` (7). `region uk` is the default; `region us` is refused while fB is 2482.
- **Links:** PR #110, PR #93, ADR-0015.
- **Residual risk:** the FEM gain figure is a datasheet value.
- **Bench:** **yes**, conducted power at the u.FL (#38).

### FW-11. Unfinished host protocol items
- **Difficulty:** #25 is open: no USB CDC console on the DK (uses the VCOM UART), settings saved in RAM only (no NVS), no `dfu` command in firmware at the time, receiver telemetry partly stubbed.
- **Links:** #25, PR #72, `fw/PROTOCOL.md`.
- **Residual risk:** pack settings (id, channel pair, TD) are lost at power-off until NVS lands.
- **Bench:** yes.

## Audio and latency

### AU-1. Codec: LC3plus too slow; ADPCM-6 chosen
- **Difficulty:** LC3plus's lowest-delay mode gives ~6 ms end-to-end against a 3 ms target. 6-bit ADPCM is "good speech", not Sennheiser EW-D quality.
- **Options:** ADPCM-6, ADPCM-8, block-float 8+3 (bake-off, 21 clips, ViSQOL v3.3.3 + PESQ-WB).
- **Chosen:** ADPCM-6: worst ViSQOL 4.20 (≥ 4.0 on every clip). All three means within 0.05; ADPCM-6 picked because only its 39 B frame fits the TD copy inside 85 B.
- **Links:** ADR-0005, AUDIT.md, AUDIT-2.md B5, `sim/codec/RESULTS.md`, PR #55.
- **Residual risk:** ADR-0005's own rule says that if TD ships off, ADPCM-8 vs ADPCM-6 is a quality tie and the A/B clips (`sim/codec/bakeoff.py`) go to the owner. TD is off by default (ADR-0017). ADPCM-6 is still needed for any pack set to TD on (39 B frame), so the simplest answer is "keep ADPCM-6 everywhere", but no ADR says so, and ADPCM-8 on non-TD packs was never weighed. Worst clips are loud sung belt (keep them in the regression corpus).
- **Bench:** SYS-4 ViSQOL on hardware; owner A/B listening test if ADPCM-8 is offered.

### AU-2. Latency budget did not add up
- **Difficulty:** SYS-2's 2.6 ms never matched its own table (2.72). Missing: TX ramp (+41 µs), 212 µs copies (not 200), latch-to-air wait (FW-3). Datasheets: PCM1840 low-latency filter 160 µs (not 350); PCM5102A 458 µs (not 400).
- **Chosen:** per-stage model in `audit.py`, asserted against bsim (a). Now 2.67 ms (TD off, FLT=0), 2.28 ms with FLT=1.
- **Links:** PR #88, PR #111, `docs/analysis/td-latency.md`.
- **Residual risk:** ADC/DAC delays are datasheet values.
- **Bench:** **yes**, logic analyser.

### AU-3. PCM5102A FLT pin: low-latency filter
- **Difficulty:** the normal filter's 458 µs group delay pushes TD-on latency to 4.96 ms.
- **Chosen:** FLT strapped high: 73 µs, saving 385 µs. Cost: stop band −52 dB instead of −60 dB above 0.55 fs, and non-linear phase. Strapped on the board so it can change without a re-spin.
- **Links:** ADR-0014, ADR-0017, PR #81.
- **Residual risk:** audible effect unchecked.
- **Bench:** **yes**, SYS-4 ViSQOL with FLT=1.

### AU-4. TD-on latency 4.60 ms against the 5 ms hard limit
- **Difficulty:** TD adds 2.3 ms; 81 B copies take 368 µs each.
- **Options (TD on):** baseline 4.96 ms; FLT=1 4.58 ms; DMA block 4: 4.49 ms; d=1: 3.96 ms (worse loss).
- **Chosen:** FLT=1, d=2. Modelled 4577 µs; bsim-measured 4596 µs, asserted ≤ 4600. The 81 B TD packet runs past the reserved RX slot (copy B ends t0 + 877 µs, slot starts t0 + 700), so TD builds set `OP_RX_WINDOW_US = 0` and give up the v1.1 downlink slot.
- **Links:** PR #88, PR #102, PR #111, ADR-0017, `docs/analysis/td-latency.md`.
- **Residual risk:** 23 µs of margin against the SPEC 4.6 ms line, 0.4 ms against the 5 ms hard limit. If any stage measures high, next is DMA block 4 (4.49 ms).
- **Bench:** **yes**.

### AU-5. One gain path, no dual-gain stacking
- **Difficulty:** "never clip" originally meant two gain paths crossfaded.
- **Chosen:** single path with PCM1840 DRE (the same trick in silicon). The x1 path stays on the schematic, unused. Mic clips first at ~132 dB SPL.
- **Links:** ADR-0006, AUDIT-2.md B6.
- **Residual risk:** a real DPA at scream level untested.
- **Bench:** **yes**.

### AU-6. Packet-loss concealment and the event-rate gate
- **Difficulty:** PLC (repeat 10 frames, fade, mute) cannot hide runs ≥ 3 frames.
- **Chosen:** if G2 reports > 10 events/h, open a PLC upgrade (pitch-period extrapolation) before Phase 5.
- **Links:** ADR-0010, PR #77.
- **Bench:** G5/G6.

### AU-7. Mixed TD and non-TD packs are 2.3 ms apart
- **Chosen:** documented for the sound designer; within R3.
- **Links:** ADR-0017.
- **Bench:** no.

## Power and battery

### PW-1. Hot-swap 18650, no charger
- **Chosen:** removable protected 18650, reverse-polarity P-FET, no charger in the pack, fuel gauge from SAADC voltage.
- **Links:** AUDIT-2.md B7, ADR-0012.
- **Residual risk:** an unprotected cell fitted by mistake (3 A fuse covers shorts).
- **Bench:** no.

### PW-2. Cutoff voltage and runtime
- **Difficulty:** the 3.3 V rail falls below PCM1840 IOVDD minimum (3.0 V) near end of discharge. A buck-boost (TPS63802) would fix it but costs ~$1 and breaks $35.
- **Chosen:** firmware shuts down below **3.3 V under load** (was 3.2 V): IOVDD 3.0 + LDO 67 mV + path 54 mV + ADC error 80 mV = 3.201 V, rounded up; the path includes the cradle spring and measured tracks (121 mΩ). Shutdown needs 5 s below cutoff. Runtime **17.5 h** at 0.55 W, 85 % of the cell usable (PK-7 ≥ 16 h).
- **Links:** ADR-0012, PR #75 review S1, PR #104, PR #119.
- **Residual risk:** 1.5 h margin over 16 h; spring and contact resistance are estimates.
- **Bench:** **yes**, PPK2 current and runtime.

### PW-3. Fuse instead of PTC
- **Difficulty:** a 0.5 A PTC (~1 Ω) costs ~0.2 V of 3.3 V headroom.
- **Chosen:** 3 A chip fuse (Bourns SF-1206F300, 23 mΩ).
- **Links:** ADR-0012.
- **Bench:** no.

### PW-4. Battery holder replaced by a printed cradle
- **Difficulty:** the MYOUNG BH-18650-B1BA002 is SMT and its span for 68–70 mm protected cells was unknown; a leaded holder (MPD BH-18650-W) plus pigtail pushed the BOM to ~$38.2.
- **Chosen:** cradle printed into the base with MYOUNG MY-18650-04-J / -05-J contacts (LCSC C19184125 / C19184124, ~$0.23 total).
- **Links:** PR #104, hw/REVIEW.md.
- **Residual risk:** contacts have no published current rating (class ~1 A versus 199 mA peak).
- **Bench:** **yes**, fit and contact resistance.

### PW-5. Rack power protection
- **Chosen:** 4 A fuse → P-FET → SMBJ12A → TPS259541 input eFuse (UVLO 9.98/9.15 V) → TPS62933 5 V → TLV76733 3.3 V; per-slot eFuses on +12 V and +5 V at 0.49 A so one shorted sub-board trips only itself. UVLO 9.15 V sits below the sub-board supervisor's 10.78 V trip.
- **Links:** ADR-0018, PR #95.
- **Residual risk:** TPS259541 has a 20-week lead time.
- **Bench:** no.

## Mechanical

### ME-1. Printer bed 180 mm; everything printed in PETG
- **Difficulty:** a 482.6 mm 1U panel exceeds the owner's Bambu A1 mini; PK-11's 25 mm left no room for a clip; the owner prefers printed parts (R15).
- **Chosen:** 3-segment panel joined by printed strips and M3 inserts; separate printed belt clip on M2 inserts; snap-arm battery door; nothing needs supports.
- **Links:** ADR-0008, PR #60.
- **Residual risk:** clip fatigue and PETG creep in the snap arms.
- **Bench:** **yes**, first print.

### ME-2. Pack board fit in the enclosure
- **Difficulty:** CadQuery was not installed locally; board 73.4 × 35 mm raised 1.4 mm so the antenna clears the clip bosses.
- **Chosen:** box-model `fit.py` locally and the CadQuery fit test mandatory in CI; M2 board retention, light-pipe chimneys (15.4 mm), printed switch fork.
- **Links:** PR #104, hw/REVIEW.md.
- **Bench:** yes, first print.

### ME-3. Receiver mezzanine height in 1U
- **Difficulty:** C47/C48 (Nichicon UEP1J470MPD, 17.5 mm seated) set the stack; 1U leaves ~35 mm above the main board.
- **Chosen:** sub-board top 30.1 mm above the main board, 4.9 mm spare; recorded in `hw/rx/out/fab/mech.json` for the rack. A 12.5 mm 33 µF part is the fallback (needs a new SPICE run).
- **Links:** ADR-0014 item 9, PR #116.
- **Bench:** yes, rack assembly.

## Sourcing and cost (UK)

### SC-1. Pack BOM against $35
- **Difficulty:** R12 aims at ~$30; PK-12 caps $35. The margin rests on Fanstel's direct module price ($13.47; Digi-Key $16.76).
- **Chosen:** cost-downs (LCSC passives, printed cradle). **$33.34** at qty 100 ex cell; about $36.3 at the Digi-Key UK module price (£12.52) and $36.63 at Digi-Key US (both over). Excludes assembly (~$3–6) and conformal coating. The Fanstel 1k price break ($12.24) would add margin.
- **Links:** ADR-0012, PR #75 review S2, PR #84, PR #104, `audit.py` Audit 2.
- **Residual risk:** R12 is +$3.34 over target.
- **Bench:** no (purchase quote).

### SC-2. GBP figures are conversions
- **Difficulty:** most prices were read from US pages; UK quotes were not taken.
- **Chosen:** each line names a UK-reachable distributor; GBP at 0.76 (rx) or USD/GBP 1.31 (pack UK CSV), not live.
- **Links:** PR #79, ADR-0014, `hw/bom/pack_uk.csv`.
- **Residual risk:** prices move before the single purchase.
- **Bench:** no.

### SC-3. Rack cost
- **Difficulty:** QUESTIONS.md Q14 guessed ~$150–250 for the whole rack; the 8 sub-boards alone are $245.
- **Chosen:** accepted. Main board, host and cables £426.32 (£113.26 estimates), 8 sub-boards £210.80, antennas £340.56: **rack £977.68** ex VAT.
- **Links:** ADR-0018, ADR-0014.
- **Bench:** no.

### SC-4. LCSC and stock gaps
- **Difficulty:** some parts are not orderable at LCSC/JLC or have thin stock.
- **Known items on main:**
  - BT40NE (Fanstel; Digi-Key UK £12.52 at 100, 624 in stock, ~10-week lead) and BT40E (Digi-Key UK 13174285): not at LCSC, consigned.
  - Pack: F1 SF-1206F300-2 consigned; GRM31CR60J107ME39L discontinued (CL31A107MQHNNNE instead, check DC bias); DMG2305UX-7 out of stock at Digi-Key UK (Mouser UK / RS).
  - U.FL: the receiver BOM uses LCSC C88374 (Hirose U.FL-R-SMT-1, 80-piece reel suffix); the rack work uses C88373 (10-piece). Same connector; pick one code before ordering.
  - Low JLC stock: TLV76733DGNR (583), TQ2SA relay C2684447 (2245). TPS259541 20-week lead. CM4 SC0680 at 0 at DigiKey UK (The Pi Hut £79.20). No panel USB-C to micro-USB lead found (£8 estimate).
  - The receiver J1 comment in `hw/rx/footprints_rx.py` still names a Samtec TSW-113-17-G-D header; the BOM uses XFCN PZ254V-12-26P.
- **Found by the rack-layout work (not on main yet; RK-7 records the final answer):**
  - 6.8 µH buck inductor: LCSC C177249 is rated only 3.5 A, under the 4 A needed; Bourns SRP5030T-6R8M (C1329837, 4 A) chosen. `hw/rack/prices.py` on main still carries a "$0.60 est." line.
  - PJ-063AH DC jack: no assembly option, so DNP and hand-soldered; bought from DigiKey UK / Mouser UK. It is not a locking jack.
  - BNC: Amphenol 112487's drawing could not be read; TE 5415025-1 (LCSC C5164649) had only 6 in stock; a Samtec socket and connector were also short. Final parts to be confirmed in the rack PR.
  - QPQ1907 not at LCSC in cut tape (consign from DigiKey UK); QPL9057 and ESD101 at 0 stock; the first 39 nH choke had a 2.2 GHz self-resonance (below the band), replaced by LQW18AN39NG80D. **Final (RK-7g):** the owner's C142171 (that 2.2 GHz part) is back, accepted on the in-band impedance analysis; every rack code is settled in RK-7g.
- **Chosen:** record now, resolve in #36.
- **Links:** hw/REVIEW.md, ADR-0018 item 7, `hw/bom/pack_uk.csv`, `docs/human/pack-parts-uk-draft.md`, RK-7.
- **Residual risk:** substitutions at order time.
- **Bench:** no.

## Compliance (UK/EU, EN 300 328, IR 2030, FCC notes)

### CO-1. UK region: 9 dBm EIRP non-adaptive
- **Difficulty:** see RF-5. Ofcom IR 2030 v1.17 (IR2030/7/1, 100 mW EIRP, 10 mW/MHz) with EN 300 328 V2.2.2.
- **Chosen:** declared max 9 dBm EIRP (+7 dBm conducted + 2 dBi whip), 1 dB under 10 dBm, so clauses 4.3.2.4–4.3.2.6 do not apply. US 15.247 kept as a region setting.
- **Links:** ADR-0015, #80, PR #86.
- **Residual risk:** whip gain and conducted power are assumptions until measured.
- **Bench:** **yes**, conducted and radiated power.

### CO-2. 2482 MHz is legal in the UK/EU only
- See RF-6. US capped at 2480 (15.205 restricted band above 2483.5).
- **Bench:** **yes**, #92.

### CO-3. BT40NE whip not on its FCC grant
- **Difficulty:** FCC ID X8WBT40N lists a 6 dBi dipole (ANT060) and a 0.88 dBi PCB antenna, not our ~2 dBi whip, and requires 20 cm separation (body-worn is closer).
- **Chosen:** UK-first. The 31 mm quarter-wave whip is a monopole, a different antenna type from the listed dipole, so the "same type, equal or lower gain" rule (§15.204(c)(4), KDB 996369) arguably does not cover it. A body-worn pack also breaks the 20 cm condition; at 20 dBm EIRP the SAR exemption needs the whip ≳ 2 cm from the body. A US build needs a Class II permissive change or change-in-ID filing plus an RF-exposure evaluation (out of v1 scope, SPEC §10).
- **Links:** #105, PR #106, `docs/analysis/module-antenna.md`.
- **Residual risk:** US use is not covered.
- **Bench:** no (paperwork).

### CO-4. No published UKCA or EU declaration for the Fanstel modules
- **Difficulty:** Fanstel states "CE, RCM: Compliant" but publishes no UKCA or EU DoC for the BT40E or BT40NE.
- **Chosen:** OpenPack writes its own UK DoC under the Radio Equipment Regulations 2017: EN 300 328 V2.2.2 at 9 dBm EIRP (pack transmitter; rack receiver blocking), EN 301 489-1/-17, EN 62368-1 and EN 62479 for the finished products. Fanstel's BT40NE CE testing used a 0 dBi antenna with the nRF5340 at −6 dBm, not our configuration. Ask Fanstel for the EN 300 328 reports before #40.
- **Links:** ADR-0014 amendment, PR #113, `docs/analysis/module-antenna.md`.
- **Residual risk:** testing cost if Fanstel's reports don't cover our configuration.
- **Bench:** no (paperwork); hands-off stop reason 4 before selling.

### CO-5. RF exposure
- **Chosen:** 9 dBm EIRP is 7.9 mW, inside the EN 62479 low-power exemption.
- **Links:** PR #106.
- **Bench:** no.

### CO-6. Documents still name US rules
- **Difficulty:** `docs/agents/hands-off.md` stop reason 4 says "Part 15"; REQUIREMENTS.md says "Region (US first)". REQUIREMENTS.md is owner-only.
- **Chosen:** flagged; ADR-0015 is the authority.
- **Links:** PR #86 follow-ups.
- **Bench:** no.

### CO-7. No encryption in v1
- **Chosen:** out of scope; CryptoCell available for v2 AES-CTR.
- **Links:** AUDIT-2.md B7.
- **Bench:** no.

## Test, simulation and CI tooling

### TS-1. bsim cannot transmit above 2480 MHz
- **Chosen:** the runner defaults to the US plan; pack 1 on 2482 credited by equivalence (RF-6).
- **Links:** ADR-0016, PR #93.

### TS-2. bsim has one crystal per device and no audio clock
- **Difficulty:** HFCLKAUDIO, I2S and the pack's two-clock drift cannot be modelled directly.
- **Chosen:** software DAC clock on TIMER2 (receiver), TIMER1 stand-in at 16 MHz with absolute compares (pack; bsim's TIMER rounds CLEAR-relative periods up to whole µs), and a test-only rate offset.
- **Links:** ADR-0013, ADR-0022.
- **Bench:** **yes**, both paths first run on silicon.

### TS-3. Events per hour cannot be gated in simulation
- **Difficulty:** p_good, phone leakage and antenna directivity are unknown until Phase 5.
- **Chosen:** G2 asserts residual loss and run length, reports events/h; G5/G6 assert ≤ 1 event/h.
- **Links:** ADR-0010, #62.
- **Bench:** **yes**.

### TS-4. Flaky timing tests in CI
- **Difficulty:** `test_receiver_reboot` failed ~25–30 % under load: pyserial's `tcflush` raised `termios.error` on a killed pty and silently killed the telemetry poller. Separately, a Schemathesis "no reply" failure came from the fake receiver not consuming the raw dfu payload (order-dependent, not seed-reproducible). Wall-clock waits also raced bsim start-up.
- **Chosen:** map `termios.error` to `ModuleError`; replace sleeps with predicate waits on telemetry frames; fix the fake receiver; add a back-to-back dfu test. 20/20 local runs pass.
- **Links:** #108, PR #109, PR #115, PR #103 CI escalation.
- **Residual risk:** bsim tests under heavy host load remain timing-sensitive; CI discipline caps re-runs at three before escalating.
- **Bench:** no.

### TS-5. Long bsim runs
- **Difficulty:** 1 simulated hour takes ~16 min.
- **Chosen:** 300 s per PR, 1 h nightly (clock recovery and frame lead).
- **Links:** PR #77, PR #114.

### TS-6. KiBot replaced by kicad-cli
- **Difficulty:** PLAN.md and SPEC G4 name KiBot. KiCad was not on the first host and installing it (container or source build) was refused by the permission system.
- **Chosen:** SKiDL for schematics/netlists and ERC; `kicad-cli` (KiCad 10 from the PPA) in a CI `pcb` job for DRC, refills, renders and fab outputs.
- **Links:** PR #75, PR #104, PR #116.
- **Residual risk:** PLAN.md and SPEC.md still say KiBot (doc drift; G4 is met with kicad-cli).

### TS-7. No autorouter: routing via the pcbnew API
- **Difficulty:** no autorouter (Freerouting) was available on the host, and an external autorouter run would also break regenerable, scripted layouts. The repo does not record why Freerouting was not used; this entry records the outcome.
- **Chosen:** a scripted grid maze router (`hw/pack/router.py`) driven through the KiCad pcbnew API, reused for the receiver. Review found and fixed: vias in the TC2030 keepout (rule areas now obstacles), and dangling L4 segments from growing trees off raw A* cells (the pack copy has the same latent bug but 0 unconnected).
- **Links:** PR #104, PR #116, hw/REVIEW.md.
- **Residual risk:** router quality is below a human or a mature autorouter; image review compensates.

### TS-8. KiCad silently ignored the pack rules file
- **Difficulty:** KiCad 10 drops the whole `.kicad_dru` when one rule (`min_resolved_spokes`) fails to parse, with no message. The pack's "JLC minimums" were never checked. The pcbnew zone fill also ignored the netclass RF gap.
- **Chosen:** rule removed; guard tests prove each rules file loads (probe rules must fire); fills come from `kicad-cli --refill-zones --save-board`.
- **Links:** PR #116.

### TS-9. Models in place of vendor models
- **Difficulty:** TI's OPA1656 model needs a login; the macromodel's second pole is assumed; ngspice-39 in the KiCad container exits 1 in batch mode.
- **Chosen:** generic macromodel with datasheet numbers plus independent MNA cross-checks; CI uses apt ngspice.
- **Links:** ADR-0006, ADR-0014 item 3, PR #81.
- **Bench:** **yes**.

### TS-10. Generated outputs and hidden code
- **Difficulty:** builds rewrite symbol libraries and BOMs in the tree; SKiDL calls hidden in comments (PK-8); netlist timestamps and sheet order vary; mech/pack.py shadowed hw/pack/pack.py on import.
- **Chosen:** CI `git diff --exit-code` on generated files; timestamps stripped; tests fail (not skip) under CI when a tool is missing; modules loaded by path.
- **Links:** PR #75 review M3, PR #81, PR #95 review M5.

### TS-11. Wi-Fi busy fraction is a guess
- **Difficulty:** AUDIT-2 D1 wanted a venue occupancy scan before locking anything. It was made optional and not done; bsim uses 10 % / 25 % / 40 % sets calibrated to `WLAN_actmod`.
- **Links:** #16, #17, PR #66, PR #82.
- **Residual risk:** real venues may be worse than 40 %.
- **Bench:** optional scan.

### TS-12. bsim near-pack level was absolute; geometry exporter bug
- **Difficulty:** the runner's near pack was a fixed −20 dBm, 31 dB hotter than a 9 dBm pack instead of 20, which broke one channel-plan experiment. The first wing-geometry export also subtracted EIRP twice for the boom actor (9 dB too weak); caught before the recorded runs.
- **Links:** ADR-0015, PR #86 follow-ups, `docs/analysis/r1-wing-antennas.md` §4.

### TS-13. What the twin does not model
- **Difficulty:** BabbleSim is free space only: no body loss, fading or moving actors; no receiver compression or PIMD; no I2S (filter delays are added from datasheets). Runs are 20–60 s, not the 1 h the gate names. Its Wi-Fi skirt is −12…−15 dB at 11 MHz offset, where the 802.11 mask allows −20. It refuses carriers above 2480 MHz, so pack 1 on 2482 is credited by equivalence. Its C/I is stricter than the nRF5340 datasheet at 3 MHz.
- **Chosen:** use the twin for relative decisions and gate only what it can model (ADR-0010); analytic models (`audit.py`, `sim/loss/wing_geometry.py`) cover compression, PIMD and geometry.
- **Links:** ADR-0010, ADR-0015, ADR-0016, `docs/analysis/r1-wing-antennas.md`.
- **Residual risk:** open risk 15.
- **Bench:** **yes**, G5: twin and bench loss within 20 %.

### TS-14. Tool versions and CI quirks
- **Difficulty:** schematics are KiCad 9 (SKiDL 3.0.0) but layout needs KiCad 10's `pcbnew` from the system Python; the field solver needs numpy from the `.ws` venv. A workflow step name containing `#22` was read as a YAML comment; the schedule step had to locate the Zephyr SDK under `/opt/toolchains`.
- **Chosen:** quote step names; actionlint before every push; SDK path found at run time.
- **Links:** commits 0b7cf90, 97707fc; `docs/agents/hands-off.md` CI discipline.

### TS-15. Layout image-review findings
- **Difficulty:** DRC-clean boards still had layout faults that only the rendered images showed.
- **Pack (fixed):** digital runs chopping the L1 pour into ~50 mm slots; a 28 mm VCM loop round the jack (now 4.9 mm); unreachable AREG cap; shorted C25/C27; QFN I2S escape; router vias in the TC2030 keepout; USB shield pads 0.225 mm from the edge.
- **Receiver (fixed):** PE4259 GND without a via; dangling router trees; COLD leg looped round J1; digital bundle moved L4 → L3; decoupling 4.3–6 mm cut to 1.5–2.6 mm.
- **Accepted:** 4 `starved_thermal` warnings on USB GND pads (the KiCad 10 API cannot set spoke count); USB D± as two 0.2 mm tracks, not a 90 Ω pair (fine at 12 Mb/s); 44 tented vias under the BT40E LGA (order filled vias if DFM flags them); no 3D models installed, so fit uses courtyard × datasheet height boxes; SJ1-3543 axis height and SW1 actuator height scaled from drawings.
- **Links:** hw/REVIEW.md, PR #104, PR #116.
- **Residual risk:** pack open item 2 in hw/REVIEW.md ("BT40NE antenna wiring is unverified") is stale: `docs/analysis/module-antenna.md` (RF-15) answers it; only the ANT_SEL level remains.
- **Bench:** real-part fit (jack, switch).

## Process

### PR-1. Single purchase at the end; bench calibration after board design
- **Difficulty:** the owner said "I'm not buying anything until we are finished." The original plan calibrated on dev kits before designing boards.
- **Chosen:** all digital work first, then one shopping list (#36); Phase 5 calibration runs after the buy, in parallel with assembly. Mitigations: keep latency and BOM margins; strap options (e.g. FLT) so values change without a re-spin; measure on dev kits before populating boards; order bare PCBs plus a stencil.
- **Links:** ADR-0019, PR #99, #36–#42.
- **Residual risk:** **a board re-spin is possible.**
- **Bench:** the whole of Phase 5.

### PR-2. The owner is away; agents decide
- **Difficulty:** the owner has no electronics background and is not a reviewer. Only money, physical steps, out-of-scope, safety/legal, and unmeetable requirements stop work.
- **Chosen:** decisions as ADRs with a requirements check; owner decisions recorded where they were needed: antennas + install rule (A), TD off by default (B), antennas only in the wings, no buying until done.
- **Links:** `docs/agents/hands-off.md`, ADR-0015/0016/0017/0019/0021.

### PR-3. Independent reviews found real defects
- **Difficulty:** ERC/DRC clean is weak evidence when custom pins are passive and rule files can silently fail.
- **Chosen:** every hardware PR gets an independent datasheet-level review. Caught: op-amp CM violation, missing hot-plug protection, QPQ1907 pinout (no RF path), bias-T burnout, battery path on inner copper, clearance override, unkeyed J1.
- **Links:** PR #75, #81, #95, #104, #116.

### PR-4. Fab DFM is an end-of-project step
- **Chosen:** no fab account and nothing uploaded until the purchase gate; DFM reports then attached to #34.
- **Links:** hw/REVIEW.md, #34.
- **Residual risk:** DFM findings arrive late.

### PR-5. Parallel PRs collide on ADR numbers and shared files
- **Difficulty:** ADR-0015 and ADR-0022 were renumbered because open PRs had claimed numbers; `audit.py` sections conflicted.
- **Chosen:** claim the next number at merge time; keep both audit sections.
- **Links:** PR #86, PR #114.

### PR-6. This log
- **Difficulty:** decisions were spread across ADRs, PR bodies and review comments; an auditor would need all of them.
- **Chosen:** this file, backfilled, with a standing rule that every design PR updates it.
- **Links:** CLAUDE.md, `docs/agents/hands-off.md`.
