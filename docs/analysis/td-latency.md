# Time diversity vs latency: where the 0.18 / 0.5 ms went, and how to get TD on to ≤ 4.6 ms

Part of #26. 2026-10-31. Numbers: `python3 audit.py` (section "#26"), `tests/bsim/scenarios/run.py` (a)/(b). This note does not pick TD on/off. That is #26's ADR.

## 1. Why bsim (a) projects 2.78 / 5.10 ms when SPEC said 2.6 / 4.6

run.py (a) measures the radio part: encode + IPC (100), then t0 to copy B end, then the 200 µs output slot. That came out at 864 µs (42 B) and 1176 µs (81 B TD length). It then adds the old SPEC lines: accumulation 1000, DMA 170, ADC 350, DAC 400.

| Stage | old SPEC §2 | bsim / datasheet | Δ TD off | Δ TD on |
|---|---|---|---|---|
| SYS-2 text vs its own §2 table | 2600 | table sums to 2720 | +120 | +120 |
| TX ramp-up before copy A | not listed | 41 (fast ramp, bsim) | +41 | +41 |
| Copy A + copy B on air | 2 × 200 | 2 × 212 (53 B on air) / 2 × 368 (92 B) | +24 | +336 |
| Rounding (measured vs model) | | | −1 | −1 |
| **run.py projection − SPEC** | | | **+184 → 2.78 ms** | **+496 → 5.10 ms** |
| ADC filter: PCM1840 low-latency, MD0=1 is already strapped (ADR-0012) | 350 | 160 (7.7/fs, SBAS989 Table 18) | −190 | −190 |
| DAC filter: PCM5102A normal FIR | 400 | 458 (22/fs, SLAS859C Table 4) | +58 | +58 |
| DAC DMA block, 8 samples | 170 | 167 | −3 | −3 |
| **Corrected (SPEC §2 now)** | | | **2650** | **4962** |

The TD-on gap is mostly the packet. The 39 B `td_audio` adds 156 µs to each copy, and the deadline waits for copy B. The SPEC had costed TD as +2000 µs of offset and nothing else. With the datasheet filters, TD on is 4.96 ms: just under the 5.0 ms hard limit, 0.36 ms over the 4.6 design.

The 81 B packet also breaks AIR-4/SYS-7. Copy B ends at t0 + 877, but the reserved RX slot starts at t0 + 700. That is why the TD build sets `OP_RX_WINDOW_US=0`. The longest payload that still fits is 57 B (td_audio ≤ 15 B, about ADPCM-2).

## 2. Options for TD on (each on top of the corrected 4962 µs)

R1 is measured with run.py (b) `--long` (120 s, 119 693 frames), 40 % Wi-Fi on 1/6/11, with the re-spaced test plan `docs/analysis/td-latency-plan.yaml` (≥ 3 MHz between carriers, #76). The "R1" column is the residual frame loss / longest lost run for the pair with both copies under Wi-Fi (2437/2462; plan pack 8 at 2431/2471 matches within 0.1 pt). A pair with one gap carrier (PR #82: 2437/2479) loses 0 % at 40 % with TD off or on, so TD only matters for in-band pairs. SYS-3 is ≤ 0.1 % and ≤ 2 in a row. Different offsets come from the same dumps: frame n counts as recovered if any copy of packet n + d arrived (run.py `on1`, `on2`, `on3`, `on1a`, `on2a`).

| # | Option | SYS-2 TD on | TD off | R1 @ 40 % (in-band) | R1 @ 10 % | Airtime / carrier | Cost | Complexity / risk |
|---|---|---|---|---|---|---|---|---|
| 0 | TD off (42 B), for reference | — | 2650 | 21.8 % / 7 | 1.37 % / 2 | 25 % | — | — |
| 1 | **Baseline TD on**: d=2, 81 B | 4962 | 2650 | 9.29 % / 8 | 0.058 % / 1 | 41 % | — | RX slot lost |
| 2 | **DAC low-latency filter (PCM5102A FLT=1)** | **4577** | **2265** | 9.29 % / 8 (no air change) | 0.058 % / 1 | 41 % | $0: pin 11 tied high on hw/rx | Trivial. IIR filter: 3.5/fs group delay, ±0.0001 dB passband to 0.45 fs, stopband −52 dB instead of −60 dB (SLAS859C Table 7). Phase is not linear and the datasheet does not specify it. Check SYS-4 by ViSQOL in Phase 5 |
| 3 | 2 + DAC DMA block 8 → 4 samples | 4494 | 2182 | same as 1 | same | 41 % | $0 | I2S interrupt at 12 kHz; `DAC_BLOCK` Kconfig. ADR-0013 loop input is the sample position, so it does not change |
| 4 | TD offset d=1 (frame n−1 in packet n) | 3962 | 2650 | 9.88 % / 9 | 0.076 % / 2 | 41 % | $0 | Low: TD ring depth 1 instead of 2. Bursts of 2 frames now hit both copies: +0.6 pt loss, +1 run |
| 5 | 2 + 4 | 3577 | 2265 | 9.88 % / 9 | 0.076 % / 2 | 41 % | $0 | as 2 and 4 |
| 6 | Partial TD: td_audio = ADPCM-3 of frame n−2 (21 B, 63 B packet) | 4818 | 2650 | **7.04 % / 6** | 0.037 % / 2 | 34 % | $0 | Medium: second encoder and decoder path (3-bit state shadow), lower quality on the recovered frames (needs a ViSQOL check on loss traces). Still misses the RX slot (t0 + 733) |
| 7 | 2 + 6 | 4433 | 2265 | 7.04 % / 6 | 0.037 % / 2 | 34 % | $0 | as 2 and 6 |
| 8 | Partial TD, d=1 (63 B) | 3818 | 2650 | 7.41 % / 7 | 0.047 % / **3** ✗ | 34 % | $0 | as 6. Fails the ≤ 2 run at 10 % |
| 9 | td_audio in copy A only (copy B 42 B) | 4806 | 2650 | ≤ 17.4 % / 9 (d=1 A-only from 81 B dumps; d=2 A-only ≈ same) | 0.41 % ✗ | 41 % / 25 % | $0 | Low, but gives back half the TD benefit. Rejected |
| 10 | T_GAP 100 → 60 µs | 4922 | 2610 | ≈ 1 | ≈ 1 | 41 % | $0 | Retune ISR gets 20 µs instead of 60 (sched.c). Needs silicon measurement. Small gain |
| 11 | Output slot 200 → 150 µs | 4912 | 2600 | ≈ 1 | ≈ 1 | 41 % | $0 | bsim (a) merge-deadline slack drops from 133 to 83 µs; ADR-0013's 125 µs setpoint fits only if decode ≤ 25 µs. Small gain |
| 12 | TD offset d=3 | 5962 ✗ | 2650 | 9.20 % / 7 | 0.054 % / 1 | 41 % | $0 | Over the hard limit, for −0.1 pt |
| 13 | 0.75 ms frames (36 samples), d=2, 63 B packet | 4068 | 2328 | not run (no build: codec frame size is fixed) | — | 45 % (AIR-7 limit) | $0 | High: codec frame, IPC, every schedule constant. Copy B ends at t0 + 733 of 750, so no RX slot is ever possible |
| 14 | PCM1840 linear-phase filter (MD0=0), for reference | 5158 ✗ | 2846 | — | — | — | — | Keep MD0=1 |

Packet length costs R1 by itself. With the same TD rule on 42 B dumps (no length penalty), the in-band loss at 40 % would be 4.84 %. At 81 B it is 9.29 %, because each copy is on air 1.7× longer under the same Wi-Fi. That is why partial TD (63 B) loses less than full TD (81 B). At 25 %: TD off 9.88 %, row 1 2.19 %, row 4 2.45 %, row 6 1.55 %.

None of these meets SYS-3 at 40 % for a pair with both copies under Wi-Fi. A gap carrier in the pair is what meets it. TD on only changes the result for in-band pairs at ≤ 10 % busy (row 1: 0.058 % vs TD off 1.37 %), so it matters most if #76 leaves one pack with two in-band carriers.

## 3. Recommendation (for the #26 ADR to accept or reject)

**Row 2: tie PCM5102A FLT high on the receiver board.** It is the smallest change that brings TD on to ≤ 4.6 ms (4.58 ms). It changes nothing on air, costs nothing, and moves R1 by 0. TD off also drops to 2.27 ms. It is a pin strap on hw/rx, which has not been designed yet. The margin is only 23 µs. If Phase 5 measures any stage high, add row 3 (DMA block 4 → 4.49 ms). If TD ships on, row 7 (also ADPCM-3 td_audio) is next: −144 µs and 2.3 pt less loss at 40 %. It needs a recovered-frame quality check and a codec change. Row 4 (d=1) buys the most latency, at a small R1 cost.
