# R1 under UK rules: can the receive side close the gap?

> **Outcome (2026-11-01, ADR-0016/ADR-0017):** adopted 1a + 4a + 5 with TD off. EN 300 328 clause check: 2482 is compliant (Audit 5). The real antenna (L-com HG2409P-NF) has rear lobes at −9 dB, not the 15 dB F/B assumed below. Its rejection is 8.8 dB, so at the Q3 2 m geometry only 3/8 hold, and the install rule moves to **Wi-Fi ≥ 4.5 m behind/beside, antennas ≥ 6 m up**. bsim (c) at that distance: packs 2–8 0.000 % TD on and off. Install doc: `docs/human/antenna-install.md`.

#89, part of #4. 2026-10-31. Follows ADR-0015 (PR #86). Numbers come from `python3 audit.py` (section "Audit 4") and from bsim (c) via `tests/bsim/scenarios/run.py` (PR #82) with the new `--rx-gain`, `--wifi-gain`, `--near-att`, `--busy` and `--c-secs` flags. This note recommends; the ADR is written separately.

**Answer:** yes, in the twin, with conditions. Two directional rack antennas aimed at the stage, with the audience Wi-Fi behind them, bring every gap carrier to 0.000 % copy loss at 40 % Wi-Fi. An 8th gap carrier (2482 MHz, UK only) then gives pack 1 one too. In bsim, 7 of 8 packs pass SYS-3 at 40 % with TD **off**; pack 1 passes by equivalence (below), because bsim cannot transmit above 2480 MHz. That holds only if the install rule in §6 is followed. If the Wi-Fi sits beside the antennas at 2 m, the result drops to 3–4 of 8.

## 1. What is short, in dB

The UK limit (9 dBm EIRP, ADR-0015) is on the pack transmitter. Under the Q3 geometry (pack at 10 m, Wi-Fi 20 dBm at 2 m from the receive antenna, 0 dBi isotropic in the twin) a pack arrives at −51.2 dBm and each Wi-Fi channel at −26.2 dBm. The bsim modem (`sim/loss/bsim_modem.py`, the BabbleSim BLE_simple tables in Python) passes −27.8 dB of a Wi-Fi channel 11 MHz away into the 2M filter. That leaves a SINR of +2.8 dB, against the 15.5 dB a TD-length copy needs for PER ≤ 0.1 %.

| carrier | offset from nearest Wi-Fi | isolation needed (twin) |
|---|---|---|
| 2423 2426 2448 2451 2473 | 11 MHz | **12.7 dB** |
| 2476 2479 | 14 / 17 MHz | 0 |
| 2482 (new) | 20 MHz | 0 |
| 2402 (band edge) | 10 MHz | 18.4 dB |

That 12.7 dB is the "~11 dB" in ADR-0015. Coax, the rack LNA and the splitter scale the pack and the Wi-Fi alike, so they change the noise floor and nothing else. With 6 dB of coax, the 20 dB / NF 2 LNA, the 1:8 splitter and BT40E modules, the system NF is 9.3 dB, and the indoor (n = 3) range with an 8 dBi patch is 41 m. Thermal noise is never the limit; Wi-Fi is.

## 2. Options

bsim (c): 8 packs + 8 receivers + Wi-Fi 1/6/11, UK 9 dBm, near pack 1. "Pass" means SYS-3 for that pack: ≤ 0.1 % loss and ≤ 2 frames in a row, TD-length packets (81 B) with TD on unless stated otherwise. 40 % runs are 20–30 s (≈ 20–30 k frames); 10 % runs are 60 s. Patch = 8 dBi, front-to-back (FtB) 15 dB (est.). In the twin, the patch is `--rx-gain 8 --wifi-gain 8−rejection`.

| # | Option | dB gained at 11 MHz | R1 packs passing, 40 % | R1 packs passing, 10 % | R3 (SYS-2) | R9 | Cost | Complexity |
|---|---|---|---|---|---|---|---|---|
| 0 | ADR-0015 baseline (isotropic, current plan) | 0 | **2/8** (7, 8). Packs 2–6: TD on 4.4–13.4 %. Pack 1 passes only as the near pack | 6/8 + near pack 1: packs 2/3/4/6 0.035–0.049 %, 7/8 0 %; pack 5 1.31 % ✗ (base10, 60 s) | TD on 4.96 ms | 8 | — | — |
| 1a | **Patch, Wi-Fi behind** (FtB 15, reflection cap 23.5) | **+14.4** | **7/8**: packs 2–8 copy B (or A) 0.000 %, TD on *and TD off*. Pack 1 has no gap carrier (in-band pair, 9.3 % at 40 %, #88) | **8/8** in f15_10_n4 (60 s): packs 2–8 0.000 % TD on and off; pack 1 (in-band, at 4 m) 0.000 % TD on | **TD off 2.65 ms** (2.27 with PCM5102A FLT=1, #88) | 8 | est. £100–200 per rack: 2 panels + 2 low-loss coax runs. R12 untouched (rack side) | Low: already Q9/RK-2 ("directional, stage wings"). New install rule (§6) |
| 1b | Patch, Wi-Fi beside (90°, est. 10 dB) | +9.8 | 3–4/8: gap copies lose 3–6 %, TD on 0.010–0.142 % (packs 2/3/4 just over 0.1 %) | — | TD on 4.96 ms | 8 | as 1a | as 1a |
| 1c | Patch, Wi-Fi in front | 0 | as row 0: front_40_n4 matches base40 (packs 2–6 fail) | — | — | 8 | as 1a | — |
| 2a | 1M PHY on both copies | +4.3 (+6.8 at 12 MHz) | ≤ 2/8: 4.3 < 12.7, and TD does not fit (1612 µs/frame) | — | TD off +0.42 ms → 3.07 | 8 | $0 | fw: MODE, schedule; loses RX slot (SYS-7) |
| 2b | Hybrid: copy A 2M (with td_audio), copy B 1M | +4.3 on the gap copy | alone: 2/8. With 1b: 9.8 + 4.3 = 14.1 ≥ 12.7, so it is the fallback if Wi-Fi must sit beside | — | 932 µs/frame; copy B ends +56 µs → 5.02 ms (over 5.0) unless FLT=1 (4.63) | 8 | $0 | fw: per-copy MODE switch inside T_GAP; not in bsim (needs fw) |
| 3 | Adaptive (LBT/DAA) at the 11.2 dBm PSD cap | +2.2 | 2/8 (10.5 dB short; ADR-0015: 14 and 17 dBm still fail) | — | CCA ≥ +120 µs/frame: TD on > 5.0 ms | 8 | $0 | High: EN 300 328 4.3.2.6 conformance; defers every in-band copy while Wi-Fi is on air. **Not worth it** |
| 4a | **8th gap carrier 2482 MHz** (`r1-uk-plan.yaml`: pack 1 2414/2482) | n/a (20 MHz from Wi-Fi 11: needs 0 dB) | with 1a: **8/8** (pack 1 by equivalence, §4) | with 1a: 8/8 | unchanged | 8 | $0 | Low: fw proto `chan` range 2480 → 2482 and host validator; UK only (US restricted band 2483.5–2500) |
| 4b | 2402 band-edge carrier | n/a (needs 18.4 dB) | with 1a: fails (14.4 < 18.4); needs FtB ≥ 25 and still hits the 23.5 dB reflection cap | — | unchanged | 8 | $0 | Low; US-legal; too weak |
| 4c | 1M PHY, 2 MHz spacing for more carriers | +4.3 | TD does not fit; RX slot gone | — | +0.42 ms | 8 | $0 | High: every schedule constant, not in bsim. Rejected |
| 4d | Time-share one gap carrier between two packs' copy B | n/a | ✗: packs are not synchronised (SYS-6), so two copies on one carrier overlap for long stretches (2 × 368 µs of each 1000 µs frame, sliding at the 0–40 ppm crystal difference) | — | — | 8 | $0 | Needs inter-pack sync = a downlink (out of scope v1, SPEC §10). Rejected |
| 5 | Placement rule (§6) | turns 1b/1c into 1a | — | — | — | — | $0 | Owner follows a checklist |

Row 0 at 10 % reproduces ADR-0015 exactly. Pack 5 fails (1.31 %) on near-far with pack 1 at 2456, not on Wi-Fi. A near pack at ≥ 4 m (1a) or moving pack 1 off 2456 (4a) removes that failure.

## 3. bsim evidence (raw)

`run.py --only c --eirp 9 --busy 40 --c-secs 20` plus:

| run | flags | gap-copy loss (packs 2–6) | TD on loss / max run | TD off (v1 42 B) |
|---|---|---|---|---|
| base40 | — | 45–56 % (2451: 65 %) | 2–6: 8.9–13.4 % / 6–14 ✗; 7, 8: 0.000 % | 2–6: 21 % ✗ |
| f15_40 | `--rx-gain 8 --wifi-gain -7` | 0.00 % (2451: 22 %, near pack) | 2–4, 6–8: 0.000 % / 0; pack 5: 4.84 % ✗ | 2–8: 0.000 % |
| f10_40 | `--rx-gain 8 --wifi-gain -2` | 2.7–6.4 % | 2: 0.102, 3: 0.142, 4: 0.117, 6: 0.086 %, run 1; pack 5 5.7 % ✗ | 1.2–3.7 % ✗ |
| **f15_40_n4** (30 s) | `--rx-gain 8 --wifi-gain -7 --near-att 43.2` (near pack 1 at 4 m) | 0.00 % | **packs 2–8: 0.000 % / 0**; pack 1 (both copies in-band, now at 4 m): 8.3 % ✗ | packs 2–8: ≤ 0.003 %, run ≤ 1 |
| f15_40_n8 | as above, `--near 8` (2479 near at 4 m) | 0.00 %; 3 MHz neighbour 2476: 0.08 % | packs 2–8: 0.000 % | ≤ 0.046 %, run 1 |
| f15_40_n8_3m | `--near 8 --near-att 40.7` (near at 3 m) | 2476: **7.6 %** | pack 7: 0.178 % ✗ | pack 7: 4.2 % ✗ |
| front_40_n4 | `--rx-gain 8 --wifi-gain 8` (Wi-Fi in front) | 45–56 % | as base40: 2–6 fail ✗ | ✗ |

In every 40 % run, pack 1 (both copies in-band) passes only because it is the near pack (−20 dBm at the rack, so Wi-Fi cannot hurt it). At 10 m it is the in-band pair: 9.3 % at 40 % with TD on (#88).

Pack 5's failure in f15_40 is near-far, not Wi-Fi. The runner's near pack is −20 dBm absolute: 31 dB hotter than a 9 dBm pack at 10 m, i.e. 0.35 m from the antenna. Its 2456 copy is 5 MHz from pack 5's 2451. Two things fix it: an antenna out of reach (`--near-att 43.2` = 4 m), or the 4a plan, which moves pack 1 off 2456.

## 4. The 8th carrier: 2482 MHz, and why bsim cannot test it

The three Wi-Fi gaps (11 MHz clear of 1/6/11) hold 2 + 2 + 4 carriers at 3 MHz spacing, and the 4th upper one is 2482. Its centre sits 1.5 MHz from the 2483.5 band edge. Ideal BLE 2M GFSK at 9 dBm puts −25.3 dBm/MHz into 2483.5–2484.5 and −49.6 into the next MHz. EN 300 328 4.3.2.8 allows −10 and −20 there, so there are 15 dB of margin before PA regrowth. Phase 5 must measure the real nRF21540 skirt. In the US, the same carrier at 20 dBm puts −14 dBm into the 15.205 restricted band (limit ~−41 dBm), so 2482 is UK only and the US keeps `host/channel_plan.yaml`. Like 2473/2476/2479, it is lost if the venue runs Wi-Fi 13.

BabbleSim rejects any centre above 2480 MHz (`bs_pc_2G4_utils.c`: "center_frequency out of ISM band"). With `docs/analysis/r1-uk-plan.yaml`, pack 1 shows NO LOCK. The silicon (nRF5340 FREQUENCY 0–100 → 2400–2500 MHz) has no such limit. Pack 1 is therefore credited by equivalence:
- **Wi-Fi:** 2482 is 20 MHz from Wi-Fi 11. 2479 (17 MHz) and 2476 (14 MHz) lose 0.000 % in every run, even isotropic at 40 %. The modem passes −68.9 dB at 16 MHz and nothing measurable at 20.
- **Neighbours:** 2482's only near neighbour is 2479 at 3 MHz. Every 3 MHz pair in the plan (2423/2426, 2448/2451, 2473/2476/2479) runs in the same simulations with no cross-pack loss at no Wi-Fi.
- **Near-far:** a 3 MHz neighbour passes −23.8 dB, so a gap copy holds while its neighbour is ≤ 8.3 dB hotter. For packs at 10 m, no pack may come closer than 3.8 m to an antenna. bsim agrees: with 2479 near at 4 m its neighbour 2476 loses 0.08 % of copies and passes. At 3 m it loses 7.6 % and fails (TD on 0.178 %) (§3).

Adopting 2482 needs `fw/src/proto/proto_pack.c` / `proto_rx.c` to accept fB ≤ 2482 (now 2480). It also needs the host validator's `GAPS` / fB limit to change. This study does not touch either; the ADR decides.

## 5. Why not the others

- **Selectivity (2):** the nRF5340 RADIO has no programmable channel filter. Bandwidth follows MODE, so the only choice is 1M vs 2M. At 11–12 MHz the interference is the Wi-Fi's own spectral skirt *inside* our channel. A sharper filter cannot remove that; only a narrower one helps, and 1M is +4.3 dB in the twin. 1M doubles air time: TD no longer fits, and the RX slot (SYS-7) goes. Hybrid 2b keeps TD and is the fallback if Wi-Fi beside the antennas cannot be avoided. It costs fw work and 56 µs of SYS-2.
- **Adaptive (3):** the PSD cap (10 dBm/MHz, BLE 2M worst 1 MHz = 76 % of power) stops at 11.2 dBm. That is +2.2 dB, against 12.7 needed. LBT/DAA also defers in-band copies whenever Wi-Fi is on air, and adds CCA time that pushes TD-on latency over 5.0 ms. Not worth an implementation.
- **Time-sharing (4d):** it needs packs synchronised to each other, which needs a downlink. Out of scope v1.

## 6. Recommendation and install rule

**Recommend 1a + 4a + 5, with TD off.** With every pack on a clean gap carrier, TD buys nothing (0.000 % TD off in f15_40). TD off gives SYS-2 2.65 ms, under the 3 ms target, and restores the AIR-4 RX slot. Keep `OP_TIME_DIVERSITY` as a Kconfig fallback for venues that break the rule. Cost: two 8–9 dBi panel antennas (FtB ≥ 15 dB on the datasheet), two low-loss coax runs, est. £100–200 per rack, a purchase for Phase 5 (stop-and-ask: money). It needs one fw range change (2482) and the host validator; pack BOM unchanged ($34.98).

Install rule for `docs/human/antennas.md` (RK-2), from `audit.py` with 3 dB margin over the twin:
1. Two flat panel antennas, one each side at the **front of the stage** (downstage corners or the proscenium), **aimed upstage at the performers**, so the audience is behind them.
2. Mount each one high, ≥ 3 m up, so that no actor comes closer than **4 m** (near-far, §4).
3. Keep audience seats and any Wi-Fi device **≥ 3 m behind** each antenna and **≥ 4 m to the side**.
4. Keep **no Wi-Fi access point, hotspot or crew laptop within 12 m in front of an antenna** (on stage or in the wings it faces). It gets the full antenna gain.
5. Venue Wi-Fi on channels 1, 6, 11 only, not 13 (ADR-0015).
6. Coax ≤ 25 m of LMR-400 (≤ 13 m LMR-240, ≤ 5 m RG-58) inside the RK-2 6 dB budget. Rack LNA input P1dB ≥ −10 dBm, IIP3 ≥ 0 dBm (Wi-Fi in front at 2 m gives −18.7 dBm per channel; IM3 −71 dBm per 2 MHz vs pack −43 dBm). That is a spec line for #32.

**If the rule cannot be kept** (say, audience 2 m beside a wing antenna), the best achievable is row 1b: 3–4 of 8 packs, gap copies losing 3–6 %, TD-on residual 0.09–0.14 %. Add 2b (hybrid 1M copy B) to get back to ~14 dB.

## 7. Limits of this evidence

- The twin's Wi-Fi spectrum is −12…−22 dB at 9–11 MHz, worse than many phones and better than the 802.11 mask allows. Phase 5 measures real phones at 11–17 MHz (ADR-0015).
- FtB 15 dB, side 10 dB, the 15 m / 6 dB reflection and coax losses are estimates. A real theatre is reverberant, and the reflection term caps rejection at 23.5 dB in this model. Phase 5/6 measure it with the bought antennas.
- bsim free space; no body loss, no fading. Run lengths are 20–60 s, not 1 h; events/h are reported, not asserted (ADR-0010).
- Two antennas with RX-5 selection are not modelled: one antenna per receiver in the twin.
