# OpenPack architecture card and scaling assessment

Audit of `/home/lenzj/openpack` at `6f0d592` (project closed 2026-11-01, nothing built). Assessed against the owner's next goals: (a) 1-2 TX + 1 RX rapid prototype with the full logic, (b) scaling to 32+ mics, self-configuring, (c) < 5 ms latency (target 3 ms), (d) cost first, receiver end above all.

## 1. Architecture card (as designed)

| Layer | What it is | Key numbers | Source |
|---|---|---|---|
| PHY | nRF5340 RADIO `MODE=Ble_2Mbit`, GFSK 2 Mbps, raw packets (no BLE link layer), 2 MHz carriers, whitening on | 4 us/byte; fast ramp-up 40 us (41 in bsim) | `SPEC.md:40` AIR-1; `fw/src/net/sched.c:42-44` |
| Packet (ADR-0009) | BLE 2M PDU layout: preamble 2 + access address 4 (`0x8E89BED6 ^ pack_id*0x9E3779B1`) + S0 header 1 (format version) + length 1 + payload + CRC-24 3 | 11 B overhead; 42 B payload -> 53 B, 212 us on air; 81 B (TD) -> 92 B, 368 us | `SPEC.md:41` AIR-2; `docs/adr/0009`; `fw/include/op_frame.h:9-10` |
| Payload (AIR-3) | `seq u8` + `status u16` (batt 7 b, peak 6 b, clip/lowbat/temp flags) + ADPCM-6 `codec_state` 3 B + `audio` 36 B = 42 B; optional `td_audio` 39 B (frame n-2) -> 81 B | max 85 B | `SPEC.md:42`; `fw/PROTOCOL.md:51` |
| Frame schedule (AIR-4) | 1 ms frame, t0 = TXEN copy A on fA; copy B TXEN at t0 + T_A + T_GAP on fB; T_GAP 100 us (retune 60 us); 300 us RX slot reserved at t0+700, idle | TD off: copy B ends t0+565 us; TD on: t0+877 (forfeits RX slot, `OP_RX_WINDOW_US=0`) | `fw/src/net/sched.c:6-15,47-52`; `fw/Kconfig` `OP_T_GAP_US`, `OP_RX_WINDOW_US` |
| Carrier plan (AIR-5) | FDMA, one carrier pair per pack, no inter-pack sync. fA 2402-2440, fB >= fA+40, fB <= 2482 UK / 2480 US. All 16 carriers >= 3 MHz apart (2 MHz neighbours collide, bsim #76). 8 UK gap carriers (>= 11 MHz from Wi-Fi 1/6/11): 2423 2426 2448 2451 2473 2476 2479 2482, one per pack; the other 8 carriers sit under Wi-Fi | `host/channel_plan.yaml:10-17`; validator `host/channel_plan.py:28-69` (`MIN_SPACING=3`, `NEAR_SPACING=5`) | `SPEC.md:14,44`; `docs/adr/0002`, `0015`, `0016` |
| Copy A/B merge (RX-4) | Receiver hops A then B each frame; first CRC-valid copy wins at a fixed deadline (copy B end + ~10 us + W); ADDRESS event timestamps re-centre the frame (1 us steps) | windows +-50 us (+-10 us for 81 B TD packets); re-acquire after 100 misses | `fw/src/rx/rx.c:1-28,246-265`; `fw/src/rx/Kconfig:3-17` |
| Time diversity (ADR-0017) | Off by default, per-pack setting; packet n carries frame n-2; receiver detects by length (42 vs 81 B) | +2.0 ms frame offset +0.31 ms longer copies | `docs/adr/0017`; `fw/src/td/op_td.c` |
| Codec (ADR-0005) | ADPCM-6, 6 bit/sample, 48 kHz mono, 288 kbps, 39 B/frame incl. 3 B state; pure C bit-exact to `sim/codec/` | ViSQOL 4.60 mean / 4.20 worst (16-bit ceiling 4.73) | `docs/adr/0005`; `fw/codec/adpcm6.c` |
| Pack timing loops | ADR-0020: audio frame clock (I2S RXPTRUPD) phased 100 us before the net core's payload latch; latch 20 us before TXEN (#98). ADR-0022: PI loop (kp 2000 ppb/us, ki 100) steers HFCLKAUDIO (3311 ppb steps) from latch-margin reports every 100 frames; 0 skips/h at +-40 ppm | frame clock -> TXEN = 120 us | `fw/Kconfig` `OP_PACK_FRAME_LEAD_US`, `OP_PACK_LATCH_LEAD_US`; `fw/src/app/pack.c:1-30`; `fw/src/clk/op_lead.c` |
| Receiver clock loop (ADR-0013) | Jitter slot setpoint 6 samples (125 us), PI on slot fill vs DAC sample position steering HFCLKAUDIO (kp 26000, ki 8 ppb); 0 slips/h, error <= 0.28 samples at +-40 ppm | adds 125-200 us | `fw/src/rx_app/Kconfig:54-73`; `fw/src/rx_app/rx_app.c:1-16`; `fw/src/clk/op_clk.c` |
| PLC (RX-6) | Repeat last frame with 1 ms fade, mute after 10 ms | | `fw/src/rx_app/op_plc.c` |
| Antenna logic (RX-5, ADR-0011/0021) | One SPDT (PE4259) per receiver, per-carrier choice by RSSI history (6 dB hysteresis), probe other antenna every 1000 frames, miss-triggered switch if other antenna <= 12 dB weaker, hold 1000 windows | | `fw/src/rx/ant.c`; `fw/src/rx/Kconfig:19-44` |
| Host protocol | ASCII 115200 8N1 request/reply (`info status stats pair trim td scan dfu`; pack console `id chan power region td save dfu`), one UART per receiver; FastAPI host (`/packs /rx /rf/scan /telemetry` WS at 10 Hz) on a Raspberry Pi CM4 | `scan` is a stub returning -100 dBm | `fw/PROTOCOL.md:9-33`; `host/PROTOCOL.md`; `host/app.py:82-204` |
| Module choice (ADR-0007/0021) | Pack: Fanstel BT40NE (nRF5340 + nRF21540 FEM + u.FL), $13.47 @100 Fanstel direct, +19.1 dBm max, UK runs +7 dBm conducted (9 dBm EIRP). Receiver: BT40E (nRF5340, u.FL, no FEM), GBP 9.78 @100 | pack BOM $33.34 (cap $35) | `docs/adr/0007`, `0021`; `audit.py` BOM section |
| Power | 18650 protected cell, TPS61023 boost 5 V, 2x TLV75533 3.3 V, no charger; cutoff 3.3 V under load; 17.5 h at 0.55 W | | `docs/adr/0012`; `audit.py` cell cutoff |
| Rack RF | 2x L-com HG2409P-NF 8 dBi panels in the wings (4 m booms) -> CA-400 coax -> bias-T -> QPL9057 LNA -> QPQ1907 BAW -> 1:8 Wilkinson (13.66 dB as routed) -> 8 receiver mezzanines; system NF 11.5-12.9 dB vs 21.1 dB need | rack GBP 1,501.50 ex VAT (packs: 8x GBP 23.38 sub-boards = 187; main board/host/case 709; antennas+coax 295; stands 311) | `docs/adr/0018`; report D6 |
| Region (ADR-0015/0016) | UK default: EN 300 328 non-adaptive below 10 dBm EIRP so Tx-gap/MU/LBT clauses do not apply; PSD caps any non-FHSS mode at 11.2 dBm; 2482 carrier legal UK/EU only | | `SPEC.md:13`; `docs/adr/0015` |

### Latency budget (SPEC §2, `audit.py` "#26" section)

| Stage (us) | TD off | TD on |
|---|---|---|
| ADC decimation (PCM1840 low-latency, MD0=1) | 160 | 160 |
| Frame accumulation (48 samples) | 1000 | 1000 |
| Frame clock -> TXEN (lead 100 + latch 20) | 120 | 120 |
| TX ramp-up | 41 | 41 |
| Copy A on air | 212 | 368 |
| T_GAP | 100 | 100 |
| Copy B on air | 212 | 368 |
| Decode + jitter slot | 200 | 200 |
| DAC DMA block (8 samples) | 167 | 167 |
| DAC filter (PCM5102A normal FIR 458; FLT=1 IIR 73) | 458 | 458 |
| Time diversity offset | 0 | 2000 |
| Total | 2670 (2285 with FLT=1, as built) | 4982 (4597 with FLT=1) |

Source: `SPEC.md:17-34`; radio part measured in bsim at 884 / 1196 us. Structural floor: 1 ms accumulation + ~0.5 ms converters + ~0.6 ms air = 2.3 ms; it meets the 3 ms target with TD off, and 4.6 ms with TD on (only 23 us under the 4.6 ms SPEC line, design-log open risk 7).

## 2. Spectrum math for scaling (band 2400-2483.5 MHz, UK)

Airtime per copy per carrier (`sched.c` AIR_US + 40 us ramp): 42 B -> 252 us = 25 % of a 1 ms frame; 81 B (TD) -> 408 us = 41 % (this is the "41 %" in `audit.py`; `SPEC.md:46` AIR-7 says 25 % off / 45 % on). At 4 Mbps (nRF54L15): 146 us = 15 % / 224 us = 22 %.

Carrier count (centres 2402-2482):
- 2 MHz spacing: 41 carriers, but bsim (#76, design-log RF-3) showed 2 MHz neighbours collide at 2 Mbps GFSK, so the project rule is >= 3 MHz (`host/channel_plan.py:15`).
- 3 MHz spacing: 27 carriers -> **13 packs** at two copies each (fA set 2402-2440 holds 13, fB set 2442-2482 holds 14), **27 packs** at one copy. With no Wi-Fi anywhere.
- With Wi-Fi 1/6/11 present: 8 gap carriers (`SPEC.md:44`); `audit.py` "Audit 2" counts 10 x 2 MHz carriers in the gaps (7 at 22 MHz Wi-Fi width) vs 16 needed for 8 packs. So **4 packs** fully in the gaps at two copies, or the shipped compromise of 8 packs with one gap copy + one in-band copy (ADR-0002). Wi-Fi 13 (UK venues) removes 4 of the 8 gap carriers.
- 4 Mbps GFSK is ~3 MHz wide (AUDIT-2 B1) -> >= 4 MHz spacing -> 21 carriers, and only ~5 fit the gaps. 4 Mbps buys airtime, not carriers.

TDMA sharing of one carrier pair (several packs, each one copy per carrier per 1 ms frame, slot = air + 40 us ramp + 30-60 us guard; `audit.py` `GUARD_US=30` is itself a guess):
- 2 Mbps, 42 B: slot 282-312 us -> **3 packs per pair** (76 % airtime; AUDIT-2 B1 said the same). TD 81 B: 2 packs.
- 4 Mbps, 42 B: slot 176-206 us -> **4-5 packs per pair** (58-73 %). TD 81 B: 3 packs.
- Latency is unchanged by TDMA: each pack phases its audio frame clock to its own slot exactly as ADR-0020 phases it to the latch today; the budget above stays 2.3-2.7 ms (TD off).

Total demand for 32 packs (slot 282 us at 2 Mbps / 176 us at 4 Mbps): two copies = 19 fully-loaded carriers at 2 Mbps, 12 at 4 Mbps; one copy = 10 / 6 carriers.

Receiver side is the real wall. One nRF5340 radio demodulates one channel at a time; each receive window costs ramp 40 + air 212 + 2W (+-50 us) + 10 = 362 us (282 us with W = 10 us). So **one nRF5340 receiver radio can catch at most 2-3 copies per ms** = 1 dual-copy pack (as built) or 3 single-copy packs. At 4 Mbps with W = 10: 5 copies/ms = 2 dual-copy or 5 single-copy packs. The "one receiver module per pack" that drove the rack cost (report D6) is intrinsic to "two copies per frame on an nRF-class radio", not a layout choice.

**Verdict: this air interface cannot reach 32 packs in one venue.** FDMA with two 2 MHz copies per pack tops out at 13 packs in a Wi-Fi-free band and 4-8 packs with Wi-Fi present; the receiver also needs one radio per pack. Options that keep latency under 5 ms:

| Option | Packs/venue (UK, Wi-Fi 1/6/11) | Latency | Receiver radios | What changes |
|---|---|---|---|---|
| A. Keep FDMA, add TDMA sharing at 2 Mbps (3 packs/pair) | 8 gap pairs x 3 = ~24 if in-band copies accepted; 12 if both copies must be gap | 2.3-2.7 ms | still 1 per pack (2 copies) | downlink beacon for slot sync (ADR-0004 slot), new sched/rx timelines; TD impossible (2 packs/pair) |
| B. TDMA at 4 Mbps (nRF54L15), 4-5 packs/pair | ~20-40 depending on in-band acceptance | ~2.0-2.4 ms (half air time) | 1 per 2 packs (W=10 us) | new SoC (single core; no bsim model yet), 4 MHz spacing, -4 dB sensitivity |
| C. One copy per frame + pseudo-random frequency hopping over 20+ carriers + TD d=1 | 27 carriers / 3 packs per carrier-ms = up to ~80 slots; practically 32 with hopping headroom | TD d=1 + FLT=1 = **3.6 ms** (`audit.py` TD-options row "DAC FLT=1 + TD d=1": 3597 us); 2.3 ms with TD off | 1 per 3 packs at 2 Mbps (hop in lockstep), 1 per 5 at 4 Mbps | adaptive FHSS also lifts the UK power cap to 20 dBm EIRP (EN 300 328 FHSS, >= 15 hops; ADR-0015 rejected it only because fixed gap carriers were wanted); needs inter-pack sync = downlink |
| D. Wideband single receiver (SDR / FPGA, >= 60 MHz IF, demodulate all carriers at once) | limited by TX side only (13 FDMA, 27+ with TDMA) | must demodulate in hardware; USB-buffered SDR adds ms and breaks 3 ms | **1 per rack** | the "innovation at the highest level" the owner asked for; whole new RX stack, no reuse of `fw/src/rx` |
| E. Smaller frames (0.75 ms) | no capacity gain (airtime % is per frame) | -0.3 ms | same | rejected in `docs/analysis/td-latency.md` row 13 |

C is the smallest change that scales and stays under 5 ms; it reuses the pack scheduler, codec, lead loop and jitter/clock loops, and is legal at higher UK power. A/B/C all need the downlink that v1 deferred.

## 3. Reusability for the 1-2 TX + 1 RX prototype

What exists: one Zephyr app, roles by Kconfig (`fw/Kconfig` `OP_ROLE_PACK/RX`), sysbuild builds both cores for `nrf5340bsim`, `nrf5340dk`, `openpack_pack`, `openpack_rx` (`fw/sysbuild.cmake`, `fw/Kconfig.sysbuild:NET_CORE_BOARD`). Twister `fw.build.dk.pack`, `fw.build.dk.rx`, `fw.build.dk.pack_td` are **build-only** (`fw/testcase.yaml`); nothing ever ran on silicon (commit `ae61ac0` added the DK targets, PR #129 says USB CDC and DFU are "build-verified only", `fw/PROTOCOL.md:35,41`).

Can it run on off-the-shelf boards?
- **nRF5340 DK: yes, as the radio + protocol core.** Overlays `fw/boards/nrf5340dk_nrf5340_cpuapp.overlay` (icmsg IPC + USB CDC console) and `..._cpunet.overlay` (FEM node placeholder, dropped for RX by `role_rx_cpunet.overlay`). Audio backend defaults to I2S on the DK (`fw/Kconfig` `OP_AUDIO_BACKEND`: `OP_AUDIO_I2S if BOARD_NRF5340DK`), with hard-coded fallback pins in `fw/src/audio/op_audio_i2s.c:137` (pack: BCLK P0.24, FSYNC P0.23, SDIN P0.20) and `:220` (rx: BCK P0.24, LRCK P0.23, SDOUT P0.13).
  - **Bug for the DK:** P0.20 is the DK's uart0 TX (`.ws/zephyr/boards/nordic/nrf5340dk/nrf5340_cpuapp_common-pinctrl.dtsi:24,44`), which the DK build keeps for logs; P0.23/P0.24 are also the DK's Button 1/2 pins. The pack DK build will fight the console for P0.20. Fix: an `i2s0` pinctrl node in the DK overlay (the code already prefers `pinctrl_0`, `op_audio_i2s.c:55-60`).
  - The FEM node on the DK drives P0.21/P0.26/P0.27/P1.04/P1.05 to nothing (P0.21 is uart0 CTS on the DK, harmless with HW flow control off). Set `CONFIG_OP_FEM_NRF21540=n` for a DK pack, else the +7 dBm cap math assumes a 10 dB FEM (`OP_TX_SOC_DBM` default -3).
- **BT40 modules without the custom boards:** the Fanstel EV-BT40NE eval board is the only route; pin map is ADR-0012. Not needed for a logic demo.
- **nRF5340 Audio DK:** no overlay exists; it has a CS47L63 codec (I2S/TDM, needs I2C config) and its own HFCLKAUDIO wiring, so it would need a new `boards/` overlay plus a codec init driver; not a drop-in.

Minimum hardware for "the same logic end to end" (TX audio -> RF -> RX audio, lock, merge, PLC, clock loops, console/host):
1. 2x nRF5340 DK (pack + receiver), optionally a 3rd for the second pack (~GBP 37 each per `docs/shopping-list.md`).
2. Pack audio: a PCM1840 EVM (or any I2S-master-tolerant 48 kHz ADC board; code is I2S master at BCK 32 fs, 16-bit, `op_audio_i2s.c:1-3`) plus a mic preamp; or skip the ADC and feed a WAV from a laptop in bsim.
3. Receiver audio: PCM5102A breakout (~GBP 3-5, 3-wire BCK PLL, matches `op_audio_i2s.c:14`), FLT pin high for the 73 us filter.
4. Two USB cables (CDC console on the pack DK's "nRF USB"; receiver protocol on uart0 VCOM) and the host app `uvicorn host.app:app` with `OPENPACK_RX_PORTS`.
Two packs need two receiver DKs under the current design (one radio per pack), so "1-2 TX + 1 RX" with one receiver means one pack at a time per receiver, which is faithful to the design but shows the scaling wall at once.

Firmware gaps before a bench demo (`fw/PROTOCOL.md:53-60`, issues #132/#128):
- **#132**: console `id`/`chan`/`power`/`td` are saved (NVS) and reported but **do not retune the radio**; the net core reads `OP_PACK_ID`/`OP_CH_A/B_MHZ` from its own Kconfig (`fw/include/op_frame.h:22-24`). Each pack must be built with its own Kconfig. Blocks any "automatic" demo.
- **#128**: host `dfu <n>` streams raw bytes; firmware now expects bare `dfu` then MCUboot SMP. Host side unchanged.
- Net core image not under MCUboot (SWD only), `fw/PROTOCOL.md:57`.
- Receiver `scan` is a stub (`fw/PROTOCOL.md:17`): `/rf/scan` returns -100 dBm everywhere.
- Receiver telemetry has a single `rssi`/`loss`, not per-carrier A/B (`fw/PROTOCOL.md:64`).
- Pack status word sends 0 until sensors land (`fw/PROTOCOL.md:51`).
- I2S/HFCLKAUDIO paths, ANT_SEL level, FEM MODE pin: never exercised on silicon (design-log open risks 3, 4).

## 4. "Automatic" operation today vs needed

Today:
- Pack identity and carriers are **compile-time** Kconfig (`OP_PACK_ID` 0-7, `OP_CH_A_MHZ`, `OP_CH_B_MHZ`, `fw/Kconfig`), set from `host/channel_plan.yaml` by hand over USB when docked (ADR-0004), and even the console values do not reach the radio (#132).
- Channel plan is a **static YAML** validated for spacing, gap coverage and near-far (`host/channel_plan.py:28-69`); 8 packs hard-coded (`sorted(packs) != list(range(1, 9))`, line 30).
- Host `/rf/scan` (`host/app.py:130-158`) polls unlocked receivers' `scan`, which is a stub. No adaptive channel selection anywhere.
- No downlink: v1 is pack -> rack only (ADR-0004); 300 us RX slot at t0+700 reserved and idle (`OP_RX_WINDOW_US` 300; TD build sets it to 0). The receiver chain is RX-only: BT40E has no PA and the rack path is LNA -> BAW -> Wilkinson (ADR-0018), so a beacon needs a 9th module with its own antenna (AUDIT-2 B3).

Missing for self-configuring packs (any of options A-C above):
1. **Downlink beacon**: rack TX on a control carrier, received in the 300 us slot (fits a <= 54 B payload at 2 Mbps after ramp-up); carries frame-sync, slot/carrier assignments, hop sequence. Pack firmware must open RX in that slot (`sched.c` only transmits) and the pack's whole frame phase must follow the beacon instead of its own crystal (today the receiver follows the pack).
2. **Join protocol**: a pack with no assignment transmits on a well-known contention carrier; the rack assigns id + carrier pair/slot; the pack `save`s it. Today's console `id`/`chan` + NVS (`fw/src/proto/op_store.c`) is the storage half of this.
3. **Real spectrum scan** on receivers (RSSI sweep, nRF RADIO RSSISTART) replacing the stub, and a planner that assigns gap carriers dynamically (the rules in `channel_plan.py` are reusable as the planner's constraints, minus the hard-coded 8).
4. **#132** (app -> net IPC config message applied at a frame boundary).
5. A rack TX path: either a separate module + antenna, or a TX/RX switch ahead of the LNA (breaks the current receive-only chain; new design).

## 5. Reusable assets

Code (keep):
- `fw/codec/adpcm6.c` (+ golden vectors `fw/codec/tests/`, `sim/codec/`) — pure C, bit-exact, PHY-independent.
- `fw/src/net/sched.c` — hardware-timed TIMER0/DPPI TX schedule; parametrised by payload length; extend with slot offset for TDMA.
- `fw/src/rx/rx.c`, `ant.c` — acquisition/tracking/merge/antenna logic; the window/deadline macros generalise to any copy timeline.
- `fw/src/clk/op_clk.c` (shared PI loop), `op_aclk.c`, `op_lead.c`, `fw/src/app/pack.c` — the two clock loops (ADR-0013, 0020, 0022) are needed by any design with a 1 ms frame.
- `fw/src/rx_app/` jitter slot + PLC; `fw/src/td/` time diversity; `fw/src/proto/` console parser, NVS store, DFU hook (pure C, ztest'd).
- `fw/src/audio/op_audio_i2s.c` I2S master for PCM1840/PCM5102A (untested on silicon).
- `host/` FastAPI service + `modules.py` serial client + `channel_plan.py` constraints; tests `tests/test_host*.py`.
- Twin: `tests/bsim/scenarios/run.py` (G2 gate, scenarios a-e, Wi-Fi interferers), `tests/bsim/sched/lead.sh`, `tests/bsim/wlan_params.yaml`, `sim/loss/bsim_modem.py`, `sim/loss/wing_geometry.py`, CI `.github/workflows/fw.yml`.
- Analysis: `audit.py` (airtime, latency budget, Gilbert-Elliott, EN 300 328 clauses, BOM; needs numpy for the PSD section), `docs/analysis/td-latency.md`, `r1-uk-isolation.md`, `r1-wing-antennas.md`, `module-antenna.md`, `sim/codec/RESULTS.md`, `sim/loss/RESULTS.md`.
- Pack hardware: `hw/pack/` (SKiDL schematic, KiCad layout, DRC clean, $33.34 BOM), `hw/spice/preamp.cir`; mech `tests/mech`. The pack is largely independent of the air-interface change (module and whip stay; a 4 Mbps option swaps the module).
- Regulatory: ADR-0015/0016 clause-by-clause EN 300 328 analysis; `docs/human/antenna-install.md`.

Decisions NOT to carry forward (driven by 8 packs / 1U / FDMA):
- **One receiver radio per pack** (AUDIT.md "What does fit", ADR-0002, RX-1): the cost driver; forced by two copies per frame on a single-channel radio.
- **Static carrier pair per pack, no inter-pack sync** (SYS-6, AIR-5, `channel_plan.yaml`, 8 hard-coded packs in `channel_plan.py:30`): cannot scale or self-configure.
- **Two full copies on two fixed carriers** (AIR-4): 50 % airtime, 2 radios' worth of RX windows per pack; prefer one copy + hopping + TD d=1, or TDMA sharing.
- **Fixed gap carriers at 3 MHz spacing including 2482** (ADR-0016): only 8 exist; 2482 is UK-only and unsimulated (open risk 2).
- **One-way link with the downlink deferred** (ADR-0004, SYS-7): self-configuration needs the downlink from day one; keep the 300 us slot idea.
- **Receive-only rack chain (LNA -> BAW -> 1:8 Wilkinson, 412 x 321 mm main board, BT40E)** (ADR-0018/0021): built for 8 fixed receivers; blocks a rack-side TX; the splitter loses 13.7 dB.
- **Wing panel antennas on 4 m stands + install rule** (ADR-0016/0021): GBP 606 of the GBP 1,501 rack and a thin 0.086 % margin; needed only because fixed carriers sit 11 MHz from Wi-Fi at 9 dBm EIRP. Adaptive FHSS (option C) legally allows 20 dBm EIRP and removes the dependence on gap carriers.
- **Non-adaptive 9 dBm EIRP** (ADR-0015): a consequence of the non-hopping design.
- **CM4 + CM4IO host with 8 UARTs + 2x SC16IS752** (ADR-0018): sized for 8 receivers; a shared-receiver design needs one serial/USB link.
- **Hammond 1U case, printed 3-segment panel** (ADR-0008): form factor assumptions.
- **ADPCM-6 chosen only so TD fits 85 B** (ADR-0005; open risk 13): with TD off by default, re-open ADPCM-8 / block-float; at 4 Mbps even 12-16-bit PCM fits.
- **Pack-sourced frame timing** (receiver follows pack crystal, RX-3): a beacon-synchronised system inverts this.
