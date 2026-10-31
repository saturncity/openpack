# OpenPack — Audit 2 (audit of AUDIT.md + the Gemini summaries)

Written 2026-10-31 by Fable for Opus to pick up. Numbers: `python3 audit.py` (section "Audit 2").
Companion: `QUESTIONS.md` (the grilling). Decisions resolved there become `docs/adr/`.

## Verdict in one paragraph

AUDIT.md is sound on what it checked (TDMA doesn't fit, LC3plus misses latency, FDMA + ADPCM fits, battery and thermal pass). It did not check four things that change the plan: the channel plan doesn't fit in the Wi-Fi gaps, the loss model ignores burstiness, there is no downlink although the plan assumes remote control, and the receiver has no clock-recovery design. Gemini's two summaries add nothing technical, restate "needs a check" items as findings, and contain contradictions. "Step 1 complete, math works" is premature. The architecture is still the right one; what is missing is a measurement, one latency-vs-robustness decision, and a bench prototype on dev kits before any PCB.

## A. Gemini summaries: what's wrong

| Claim | Problem |
|---|---|
| Channels "sit exactly in the gaps between Wi-Fi 1/6/11" | 8 packs × 2 copies = 16 carriers at 2 MHz. The gaps hold 7–10 (audit.py). At least 6 carriers must sit on top of Wi-Fi channels, or packs must share carriers (which is TDMA again). |
| "All gain, mute, and configuration remotely controlled from the booth" | There is no receiver→pack link in the design. One radio per pack, 100% uplink. Remote mute/gain/channel-move is impossible as drawn. |
| "Sennheiser EW-D latency and dynamic range for $30" | 6-bit ADPCM has ~36–45 dB signal-tracking SNR, not 130 dB. The never-clip front end feeds a codec that discards most of what it captured. Quality is "good speech", not "EW-D". Needs a listening test, not a claim. |
| "20 to 47 hours" runtime | Two different load assumptions from audit.py, not a spec. Real figure with a +20 dBm FEM is ~25–30 h. Still passes. |
| "Dual-ADC PCM1840" | It's a 4-channel part. Minor, but shows the summary wasn't checked. |
| Pipeline: "Opus does the TDMA stack" in "C++" | Plan is FDMA. nRF Connect SDK / Zephyr is C. |
| "CC1352P lacked bandwidth" (stated as a finding) | AUDIT.md said "needs a check". Checked: sub-GHz characterized to 1 Mbps, so 288 kbps fits. It is viable for one copy; shelve it for v2, not because of bandwidth. |
| "Fable (Orchestrator)" | User's standing preference is Opus 5.5 as master agent. Follow the user, not the summary. |
| "$30 BOM" | $30.40 ex. 18650 cell at qty 100 with the cheaper op-amp (audit.py). ~$35 with cell. Tight; honest number is "$30–35". |
| "Step 1 complete" | Guard/ramp times are guesses, DR of the front end unverified, loss model wrong (see B2). Step 1 is complete when the bench proto (section D) passes. |

## B. Findings the first audit missed

### B1. Channel plan doesn't fit the gaps (blocker for "8 packs, no Wi-Fi overlap")
See table above. Options, cheapest first:
1. Accept overlap. Wi-Fi is bursty; our 2 MHz carrier under a 20 MHz Wi-Fi channel sees ~1/10 of its power density and Wi-Fi's own CCA often defers to us. This is what BLE data channels do all day. **Needs measurement, not argument** (D1).
2. Two packs per carrier pair, time-staggered (3 packs max per pair at 2 Mbps; airtime 78%). Needs inter-pack sync, i.e. a beacon, i.e. a downlink. Not v1.
3. nRF54L15 at 4 Mbps halves airtime, so 1 MHz spacing is still too close (GFSK at 4 Mbps is ~3 MHz wide). No help for the channel count; big help for codec headroom (B5).

### B2. Loss model: bursty, not independent (changes the headline risk)
Wi-Fi bursts are 0.2–4 ms. audit.py now runs a Gilbert-Elliott model. At 10% busy per channel the residual is still ~1%, but that is **~100 multi-frame dropouts per minute**, each 2–5 ms. That is not "1% hidden by PLC"; it is unusable. Only fixes:
- **Time diversity**: carry a copy of frame n−2 inside packet n (RED-style). Costs +2 ms latency (constant, must be budgeted) and ~30% more airtime (fits at 2 Mbps for ADPCM 6-bit, fits easily at 4 Mbps). Residual then needs 3 consecutive bad frames on both channels.
- **Lower busy fraction**: directional stage-wing antennas, adaptive channel selection (needs downlink), +20 dBm so the receiver captures us over Wi-Fi.
This is the central trade: **~2.2 ms with no burst protection, or ~4.2 ms with it.** The user decides (QUESTIONS.md Q1). Everything downstream depends on it.

### B3. No downlink (decide now, build later)
v1 can be one-way **if** the three things that normally need a downlink are removed:
- Gain: the never-clip front end means no pack gain. Trim is digital at the receiver.
- Mute: at the console.
- Channel/ID: set over USB-C when docked (nRF5340 has USB; DFU comes free). No DIP switches, no IR.
Telemetry (battery, peak, temp) rides in the uplink header (2 bytes/frame). RF health is measured at the receiver.
**Reserve a ~300 µs RX window in the frame schedule now** (airtime allows it) so v1.1 can add a control beacon from a 9th rack module with its own antenna (the active splitter is RX-only, so the control TX can't share the main antennas). Don't implement in v1.

### B4. Receiver clock recovery is missing
Pack ADC and receiver DAC run on different crystals (±20 ppm → 1 ms of drift every ~50 s). The receiver must slew its audio clock to the incoming stream. nRF5340's HFCLKAUDIO is tunable for exactly this (LE Audio does it). **Receiver modules must be nRF5340 (or nRF54L15 if it has the same), not nRF52.** Spec: jitter buffer of 1 frame, PI-controlled clock, lock within 2 s.

### B5. Codec is not settled, and the chip choice is coupled to it
- ADPCM 6-bit works but is the floor. Each frame must carry its predictor/step state (3 B) so a lost frame doesn't desync the decoder.
- Block floating point (8-bit mantissa + 3-bit exponent per 16 samples, ~8.2 b/sample, 67% airtime at 2 Mbps) has zero delay, zero error propagation, 48 dB SNR re block peak. Simpler than ADPCM.
- nRF54L15 (4 Mbps, I2S, +8 dBm, cheaper than nRF5340) makes 12–16-bit PCM fit with two copies. Trade: ~4 dB worse sensitivity at 4 Mbps, single core, newer SDK support.
**Decide by experiment, not debate**: Python implementations of three codecs on speech/singing, blind listening + ViSQOL. Half a day for Sonnet.

### B6. Dual-gain "never clip" may be YAGNI
With a 6 mV/Pa lav, a single path at +6 dB into a 2 Vrms-FS, 113 dB ADC clips at ~132 dB SPL (the mic clips first) and adds ~1 dB to the mic's own noise. Also, the PCM1840's built-in Dynamic Range Enhancer (113 → 123 dB, up to 24 dB auto-gain) is the same trick in silicon. Keep the two OPA paths on the schematic as an option, but **v1 firmware: single path, DRE on. Add the stacking only if the bench test with a real DPA at scream level shows clipping or audible noise.**

### B7. Small corrections
- OPA1612: ~3.6 mA/channel and needs ±2.25 V min. Overkill for +6 dB from a 1 kΩ source. Use OPA1656 or similar single-supply part at 5 V. Saves $2–3 and power.
- Mic bias: fix at 5 V through a resistor (DPA wants 5–10 V; everything else is happy at 5 V). The 5 V rail is needed for the op-amp anyway. **Drop the 3.3/5 V jumper.**
- nRF5340 max TX is +3 dBm. Stage use needs a FEM (+10 to +20 dBm, software-set). FEM breaks modular FCC certification unless the module includes it (Fanstel BT40F, Raytac MDBT53-1M-FEM, or similar). Choose a module with FEM integrated.
- EU: EN 300 328 caps non-adaptive devices with >10% medium utilisation at 10 dBm EIRP. Our ~26%/channel means **EU = +10 dBm max** unless we add listen-before-talk. US (FCC 15.247 DTS) allows the full +20 dBm. Spec TX power as a per-region setting.
- 18650: hot-swap means **no charger in the pack**. Protected cell + reverse-polarity protection + holder with positive retention (cells walk out of spring holders under stage movement). Fuel gauge = SAADC voltage + lookup table.
- Latency 2.2 ms assumes sub-frame DMA chunks on the DAC side (e.g. 8-sample blocks). A naive 1 ms ping-pong buffer adds ~1–2 ms. Write the budget per stage into the spec with DMA block size as a parameter.
- "Plays the cleanest packet": there is no "cleanest". CRC passes or fails. First good copy wins; output time is fixed at the copy-2 deadline.
- Receiver hopping between the two copies needs ~50 µs retune on both ends. Make the inter-copy gap a parameter (start at 100 µs) and measure on hardware.
- Antenna: 1.2" is the correct quarter-wave. The whip only helps marginally against body loss; the real fix is receiver antenna placement (two directional antennas at the stage wings, not on the rack in the booth). Spec that.
- Encryption: none in v1. Note as out of scope; nRF has CryptoCell if a v2 wants AES-CTR.
- Sub-GHz (902–928 MHz, US only) as the second copy's band: viable (CC1352P at 1 Mbps carries 288 kbps), body loss ~10 dB lower, far fewer phones. Shelve to v2 but it is the strongest fallback if 2.4-only fails D1.
- UHF TV band under FCC 15.236 (50 mW, unlicensed): where real theater systems live, but the occupied-bandwidth limit (verify: 200 kHz) forces a proprietary high-order modem. Out of scope; say so in the spec so nobody re-asks.

## C. What stays locked (agree with AUDIT.md)
FDMA one carrier pair per pack · 1 ms frames · two copies on two widely spaced channels from one radio · one receiver radio per pack with antenna switching · PCM1840 · 18650 · no on-pack controls · recessed power switch + 3 LEDs · locking 3.5 mm TRS, Sennheiser pinout · 1U, 8 XLR, 2 BNC + active splitter · Ethernet + REST/WebSocket on a small Linux host · no Dante · no e-ink · no 5 GHz.

## D. Best way forward (Step 2 plan)

Order matters. Each gate is cheap and kills the biggest remaining risk.

**D1. Measure the venue (1 day, $10).** nRF52840 dongle running an RSSI/occupancy scanner across 2400–2483 MHz, in a real packed house during a show. Output: busy fraction per 2 MHz vs time. This replaces the 10%/40% guesses in audit.py and decides B1/B2. Nothing else should be "locked" until this exists.

**D2. Codec bake-off (½ day, Sonnet).** Python: ADPCM-6, ADPCM-8, block-float 8+3. Speech + singing + whisper→scream. Blind listen + ViSQOL. Picks codec and therefore PHY rate / chip.

**D3. Bench proto on dev kits, no PCB (2–3 weeks, Opus).**
- 2 × nRF5340-DK (or nRF54L15-DK if D2 wants 4 Mbps), PCM1840 EVM or any I2S mic board, PCM5102 DAC board. ~$200.
- Firmware: frame scheduler on net core, codec + I2S on app core, receiver sync/acquire/clock-recovery, PLC.
- Pass gates: end-to-end latency ≤ target (Q1) measured with a scope; 1 h at 10 m with a laptop + 2 phones running iperf on 1/6/11 next to the receiver: residual loss and dropout-event count below the number set in Q3; clock lock holds 1 h.
- This proves 80% of the project with zero custom hardware. A 4-pack build before this is money spent on the wrong risk.

**D4. Only then: PCB + enclosure + 4-pack.** Pack PCB (module with FEM, so no RF layout), receiver sub-board × 8 + backplane + splitter, host = Raspberry Pi CM4/Zero 2 W with Ethernet running the API. CAD in CadQuery/OpenSCAD (code, reviewable by agents). KiCad via SKiDL for netlists; a human reviews layout.

**D5. Hostile-RF gate with 8 packs**, repeat D3's test with 8 packs and a sold-out house. Pass → v1. Fail → v1.1 downlink + adaptive channels, or sub-GHz second band.

## E. Tasks for the agents
- Opus (master): resolve QUESTIONS.md with the user, write ADRs (`docs/adr/0001-fdma.md`, `0002-codec.md`, `0003-no-downlink-v1.md`, `0004-latency-vs-time-diversity.md`), then the spec (`SPEC.md`: numbered, testable requirements, per-stage latency budget, frame format, pass gates).
- Sonnet: D1 scanner script, D2 codec bake-off, `GLOSSARY.md` (frame, copy, carrier pair, residual loss, dropout event, lock).
- Nobody: KiCad, CAD, or 4-pack purchasing until D3 passes.
