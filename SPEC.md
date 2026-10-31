# OpenPack — System Specification v0.1

2026-10-31. Traces to `REQUIREMENTS.md` (R-ids). Decisions: `QUESTIONS.md` defaults → `docs/adr/`. Each requirement line has an ID, a number, and the tool that verifies it (`PLAN.md`). Values marked *design* are targets the twin must hit; values marked *measured* are confirmed in Phase 5. Change a number only via an ADR.

## 1. System

| ID | Requirement | Verify |
|---|---|---|
| SYS-1 | 8 bodypacks → 1 receiver rack, 1U, 8 balanced analog outputs (R9) | Inspection |
| SYS-2 | Mic-in to XLR-out latency: ≤ 3.0 ms target, ≤ 5.0 ms hard (R3). Design: 2.6 ms without time diversity, 4.6 ms with | bsim timestamps + logic analyzer |
| SYS-3 | Under the Q3 interference setup for 1 h: residual frame loss ≤ 0.1 %, ≤ 2 consecutive lost frames, ≤ 1 audible dropout event (R1) | bsim scenario (c), then Phase 5/6 |
| SYS-4 | Audio: 48 kHz, 20 Hz–20 kHz ±0.5 dB, ViSQOL ≥ 4.0 vs 24-bit input on the Phase 1 corpus (R5) | ViSQOL |
| SYS-5 | 2.4 GHz ISM only, FCC 15.247 DTS; EU build limited to +10 dBm EIRP | Datasheet + ADR |
| SYS-6 | One RF carrier pair per pack (FDMA), no inter-pack sync | Design |
| SYS-7 | No pack→rack link other than the audio uplink in v1; a 300 µs RX slot is reserved per frame (Q4) | Frame schedule test |

## 2. Latency budget (design, per stage; sum = SYS-2)

| Stage | µs | Note |
|---|---|---|
| ADC decimation filter | 350 | PCM1840, *measured* Phase 5 |
| Frame accumulation | 1000 | 48 samples |
| Encode + IPC app→net core | 100 | Twister timing test |
| Copy A on air | 200 | ~47 B at 2 Mbps |
| Retune gap | 100 | parameter `T_GAP`, *measured* |
| Copy B on air | 200 | |
| Decode + jitter slot | 200 | fixed output deadline = copy B end + 200 |
| DAC DMA block (8 samples) | 170 | parameter `DAC_BLOCK` |
| DAC interpolation filter | 400 | PCM5102, *measured* |
| **Total** | **2720** | time diversity adds 2000 |

## 3. Air interface

| ID | Requirement |
|---|---|
| AIR-1 | PHY: nRF RADIO `MODE=Ble_2Mbit`, GFSK 2 Mbps, 2 MHz channel spacing, raw packet config (not BLE link layer). Rationale: identical on silicon and in BabbleSim |
| AIR-2 | Packet: 2 B preamble, 4 B access address = `0x8E89BED6 ^ (pack_id * 0x9E3779B1)`, 1 B length, payload, 3 B CRC-24 (poly 0x00065B), whitening on |
| AIR-3 | Payload (v1, ADPCM-6 shown; codec per ADR-0005): `seq u8` · `status u16` (bat 7 b, peak 6 b, flags 3 b: clip/lowbat/temp) · `codec_state` 3 B · `audio` 36 B · optional `td_audio` 39 B (frame n−2, Kconfig `OP_TIME_DIVERSITY`). Max 85 B |
| AIR-4 | Frame period 1000 µs ±20 ppm (pack crystal). Schedule from frame start t0: copy A TX at t0, copy B TX at t0+T_A+T_GAP on channel B, RX slot at t0+700 µs for 300 µs (idle in v1) |
| AIR-5 | Channel pair per pack from `host/channel_plan.yaml`: fA ∈ 2402–2440 MHz, fB = fA + ≥ 40 MHz, 16 distinct carriers for 8 packs, gap carriers (2423–2426, 2448–2451, 2473–2482) assigned first |
| AIR-6 | TX power: software-set 0 to +20 dBm (FEM), default +20 dBm US, +10 dBm EU |
| AIR-7 | Airtime per carrier ≤ 45 % of frame (two copies, time diversity on, at 2 Mbps) |

## 4. Bodypack

| ID | Requirement | Verify |
|---|---|---|
| PK-1 | Input: locking 3.5 mm TRS, Sennheiser SK pinout (confirm from Sennheiser SK 100 G4 manual in Phase 4), bias 5 V via 2.2 kΩ on the mic pin (R6) | Inspection |
| PK-2 | Max input 0.6 Vrms without clipping anywhere in the chain (R2); input-referred noise ≤ 1 µV A-weighted 20 Hz–20 kHz | ngspice `.noise`, `.tran` |
| PK-3 | ADC: PCM1840, 2 Vrms FS, DRE on; preamp fixed +6 dB single-supply 5 V (ADR-0006); second gain path populated on schematic, unused in v1 firmware | ngspice, Twister |
| PK-4 | SoC: nRF5340 pre-certified module with integrated FEM and u.FL (ADR-0007 names the part) | BOM |
| PK-5 | Antenna: 31 mm quarter-wave wire whip, exits top face, ≥ 40 mm from the cell (R15, R10) | CAD check |
| PK-6 | Power: one removable protected 18650 in a holder with positive retention; reverse-polarity protection; no charging circuit (R7). Boost to 5 V for preamp/bias; LDO 3.3 V | Schematic ERC |
| PK-7 | Runtime ≥ 16 h at +20 dBm continuous (R8). Design draw ≤ 0.6 W | `audit.py`, PPK2 |
| PK-8 | Controls: recessed slide power switch only (R4). LEDs: power/battery (green, red < 3.4 V), peak/clip (amber at −3 dBFS, red at clip). No "link" LED (one-way link cannot know) (R14) | Inspection |
| PK-9 | Config/DFU: recessed USB-C, USB CDC text protocol (`id`, `chan`, `power`, `region`, `save`, `info`), MCUboot serial DFU. Not a charging port | pytest over pty / DK |
| PK-10 | Telemetry in every frame: battery, peak, clip flag, temperature flag (AIR-3) | bsim |
| PK-11 | Enclosure ≤ 100 × 65 × 25 mm, PETG, belt clip, battery door without tools, conformal-coated PCB (R15) | CadQuery tests |
| PK-12 | BOM ≤ $35 ex. cell at qty 100 (R12) | `audit.py` |
| PK-13 | Boot to transmitting ≤ 1 s | bsim |

## 5. Receiver module (×8)

| ID | Requirement | Verify |
|---|---|---|
| RX-1 | nRF5340 module, u.FL, SPDT antenna switch (antenna A/B), UART to host, I2S to DAC | Schematic |
| RX-2 | Acquisition: open RX on channel A until a CRC-valid packet with the configured address; lock ≤ 2 s from pack power-on | bsim (a), (e) |
| RX-3 | Tracking: RX windows on A then B per AIR-4, window ±50 µs, re-acquire after 100 consecutive misses | bsim (b) |
| RX-4 | Merge: first CRC-valid copy wins; output at fixed deadline; with time diversity, frame n is recovered from packet n+2 if both copies of n failed | bsim (b), (c) |
| RX-5 | Antenna selection: per-channel RSSI history, switch when the other antenna's last-valid RSSI exceeds current by 6 dB | bsim with two path losses |
| RX-6 | PLC: repeat last frame with 1 ms linear fade; mute after 10 ms of loss | ViSQOL on loss traces |
| RX-7 | Clock recovery: HFCLKAUDIO tuned by a PI loop on jitter-buffer fill; after lock, output rate error ≤ 1 sample/h, no buffer slips over 1 h at ±40 ppm | bsim (d) |
| RX-8 | Output: PCM5102 DAC → balanced driver → XLR male; max +18 dBu, nominal −20 dBFS = −2 dBu, Zout ≤ 100 Ω; digital trim −40…0 dB from host | ngspice, inspection |
| RX-9 | Reports to host at 10 Hz: lock state, RSSI A/B per channel, loss counters, pack telemetry | pytest |
| RX-10 | Survives host reset and pack reboot without manual intervention | bsim (e) |

## 6. Rack

| ID | Requirement |
|---|---|
| RK-1 | 1U, external 12 V DC brick, rear: 8 XLR male, 2 BNC (antenna A/B) with switchable 12 V bias-T for active antennas, RJ45, USB-C (host service) (R9, R10) |
| RK-2 | RF: per antenna input, LNA (NF ≤ 2 dB) → 1:8 splitter → 8 modules; coax loss budget 6 dB; antenna placement guidance in `docs/human/antennas.md` (stage wings, directional) |
| RK-3 | Host: Raspberry Pi CM4 on a carrier with Ethernet; 8 module UARTs via the carrier or a USB-UART hub; boots to service ≤ 60 s |
| RK-4 | Front: per channel, lock LED and audio peak LED; no display |

## 7. Host API (`host/`)

| ID | Requirement | Verify |
|---|---|---|
| API-1 | REST (OpenAPI 3.1): `GET /packs`, `GET /packs/{id}`, `PUT /packs/{id}/trim`, `GET /rx`, `PUT /rx/{n}/pair` (pack id, fA, fB), `GET /rf/scan`, `POST /rx/{n}/firmware`, `GET /health` | Schemathesis |
| API-2 | WebSocket `/telemetry`: all packs at 10 Hz, JSON, ≤ 200 ms end-to-end from the module (R11) | pytest against bsim ptys |
| API-3 | Channel plan file `host/channel_plan.yaml` is the single source of pack-id → carrier pair; pack USB config and `PUT /rx/{n}/pair` both derive from it | pytest |
| API-4 | No authentication in v1; LAN only; documented | README |
| API-5 | `GET /rf/scan`: modules not locked scan 2400–2483 MHz RSSI in 2 MHz steps; result cached 10 s | pytest |

## 8. Firmware structure (`fw/`)

| ID | Requirement |
|---|---|
| FW-1 | One Zephyr application, `CONFIG_OP_ROLE_PACK` / `CONFIG_OP_ROLE_RX`, targets `nrf5340bsim/nrf5340/cpuapp+cpunet` and `nrf5340dk/nrf5340/cpuapp+cpunet` |
| FW-2 | Net core owns RADIO, TIMER, DPPI schedule; app core owns codec, I2S, UART/USB, telemetry; IPC via `ipc_service` with one 1 ms frame per message |
| FW-3 | Audio I/O behind `op_audio.h` (`start`, `read_frame`, `write_block`); backends: I2S (hardware) and WAV file (bsim) |
| FW-4 | Codec in `fw/codec/`, pure C, no Zephyr dependency, bit-exact to `sim/codec/` reference (Twister test compares against golden vectors) |
| FW-5 | All timing constants (`T_GAP`, `DAC_BLOCK`, RX window) are Kconfig; no magic numbers |
| FW-6 | MCUboot on both roles; serial DFU on the pack, UART DFU on modules |

## 9. Test gates (from `PLAN.md`, restated as pass/fail)

| Gate | Pass when |
|---|---|
| G1 Phase 1 | Codec chosen with ViSQOL ≥ 4.0 (SYS-4); ngspice shows PK-2; WLAN model parameters committed |
| G2 Phase 2 | bsim (a) latency ≤ 1.6 ms excl. ADC/DAC filters; (b)+(c) meet SYS-3 at committed busy fraction; (d) RX-7; (e) RX-2/RX-10 |
| G3 Phase 3 | Schemathesis clean; API-2 timing; host survives module reset |
| G4 Phase 4 | ERC/DRC/KiBot clean; PK-12; CadQuery tests; layout image review checklist signed by Opus; fab DFM clean |
| G5 Phase 5 | Measured SYS-2 ≤ limit; twin vs bench residual loss within 20 %; PK-7 from PPK2 |
| G6 Phase 6 | SYS-3 with 4 packs, then in a real sold-out house |

## 10. Out of scope (v1)
Downlink implementation, adaptive channel hopping, encryption, Dante/AES67, in-pack charging, e-ink, sub-GHz, 5 GHz, FCC certification filing.
