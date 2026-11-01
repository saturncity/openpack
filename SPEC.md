# OpenPack — System Specification v0.1

2026-10-31. Traces to `REQUIREMENTS.md` (R-ids). Decisions: `QUESTIONS.md` defaults → `docs/adr/`. Each requirement line has an ID, a number, and the tool that verifies it (`PLAN.md`). Values marked *design* are targets the twin must hit; values marked *measured* are confirmed in Phase 5. Change a number only via an ADR.

## 1. System

| ID | Requirement | Verify |
|---|---|---|
| SYS-1 | 8 bodypacks → 1 receiver rack, 1U, 8 balanced analog outputs (R9) | Inspection |
| SYS-2 | Mic-in to XLR-out latency: ≤ 3.0 ms target, ≤ 5.0 ms hard (R3). Design (§2, bsim (a) + datasheets): **time diversity off by default (ADR-0017): 2.65 ms** (2.27 ms with the PCM5102A FLT=1 strap on hw/rx). TD is a per-pack setting for hostile venues: 4.58 ms with FLT=1 (4.96 with FLT=0; d = 2, 81 B packets). Options: `docs/analysis/td-latency.md` (#26) | bsim timestamps + logic analyzer |
| SYS-3 | Under the Q3 interference setup for 1 h: residual frame loss ≤ 0.1 %, ≤ 2 consecutive lost frames, ≤ 1 audible dropout event (R1) | bsim scenario (c), then Phase 5/6 |
| SYS-4 | Audio: 48 kHz, 20 Hz–20 kHz ±0.5 dB, ViSQOL ≥ 4.0 vs 24-bit input on the Phase 1 corpus (R5) | ViSQOL |
| SYS-5 | 2.4 GHz ISM only. Region from `host/channel_plan.yaml` `region` (ADR-0015). **UK (default):** Ofcom IR2030/7/1, ETSI EN 300 328 V2.2.2 non-adaptive non-FHSS, declared max **9 dBm EIRP** (below 10 dBm, so the Tx-gap/MU/adaptivity clauses 4.3.2.4–4.3.2.6 do not apply), PSD ≤ 10 dBm/MHz, 99 % OBW inside 2400–2483.5 MHz (4.3.2.7), OOB ≤ −10/−20 dBm/MHz (4.3.2.8 Figure 3). The highest carrier is 2482: its OBW top edge is ≤ 2483.28 MHz and its OOB margin ≥ 6 dB (ADR-0016). **US:** FCC 15.247 DTS, ≤ 20 dBm EIRP, highest carrier 2480 (15.205 restricted band above 2483.5) | `audit.py` Audit 3/5 + ADR-0015/0016; 2482 OBW and OOB measured on a pack in Phase 5 |
| SYS-6 | One RF carrier pair per pack (FDMA), no inter-pack sync | Design |
| SYS-7 | No pack→rack link other than the audio uplink in v1; a 300 µs RX slot is reserved per frame (Q4) | Frame schedule test |

## 2. Latency budget (per stage; sum = SYS-2)

Corrected by #26 (`python3 audit.py`, `docs/analysis/td-latency.md`). The radio part (encode + IPC through output slot) is *measured* in bsim (a): 864 µs, 1176 µs at TD length. Filters are datasheet values at 48 kHz, *measured* in Phase 5.

| Stage | µs (TD off) | µs (TD on) | Note |
|---|---|---|---|
| ADC decimation filter | 160 | 160 | PCM1840 low-latency filter, 7.7/fs (SBAS989 Table 18), MD0=1 (ADR-0012). Linear phase would be 356 |
| Frame accumulation | 1000 | 1000 | 48 samples |
| Encode + IPC app→net core | 100 | 100 | Twister timing test |
| TX ramp-up, copy A | 41 | 41 | RADIO fast ramp-up (40 on silicon, 41 in bsim) |
| Copy A on air | 212 | 368 | 53 B / 92 B on air (AIR-2 + 42 B / 81 B payload) at 2 Mbps |
| Retune gap | 100 | 100 | parameter `T_GAP`, includes copy B ramp-up, *measured* |
| Copy B on air | 212 | 368 | |
| Decode + jitter slot | 200 | 200 | fixed output deadline = copy B end + 200 (ADR-0013: 125 setpoint) |
| DAC DMA block (8 samples) | 167 | 167 | parameter `DAC_BLOCK` |
| DAC interpolation filter | 458 | 458 | PCM5102A normal FIR, 22/fs (SLAS859C Table 4). FLT=1 low-latency IIR: 73 (3.5/fs, Table 7) |
| Time diversity | 0 | 2000 | frame n is played after packet n+2 (AIR-3, RX-4) |
| **Total** | **2650** | **4962** | was 2720 / 4720 in this table and 2.6 / 4.6 ms in SYS-2 |

## 3. Air interface

| ID | Requirement |
|---|---|
| AIR-1 | PHY: nRF RADIO `MODE=Ble_2Mbit`, GFSK 2 Mbps, 2 MHz channel spacing, raw packet config (not BLE link layer). Rationale: identical on silicon and in BabbleSim |
| AIR-2 | Packet: 2 B preamble, 4 B access address = `0x8E89BED6 ^ (pack_id * 0x9E3779B1)`, 1 B header (RADIO S0: format version, 0 in v1), 1 B length, payload, 3 B CRC-24 (poly 0x00065B, address skipped), whitening on. This is the BLE 2M PDU layout, the only one the bsim RADIO model accepts (ADR-0009) |
| AIR-3 | Payload (v1, ADPCM-6 shown; codec per ADR-0005): `seq u8` · `status u16` (bat 7 b, peak 6 b, flags 3 b: clip/lowbat/temp) · `codec_state` 3 B · `audio` 36 B · optional `td_audio` 39 B (frame n−2, Kconfig `OP_TIME_DIVERSITY`). Max 85 B |
| AIR-4 | Frame period 1000 µs ±20 ppm (pack crystal). Schedule from frame start t0: copy A TX at t0, copy B TX at t0+T_A+T_GAP on channel B, RX slot at t0+700 µs for 300 µs (idle in v1) |
| AIR-5 | Channel pair per pack from `host/channel_plan.yaml` (ADR-0015, ADR-0016, #76): fA ∈ 2402–2440 MHz, fB ∈ [fA + 40, fmax], fmax = **2482 UK/EU, 2480 US** (validator, pack `chan`, Kconfig); 16 carriers, every one ≥ 3 MHz from every other; whichever pack stands next to an antenna, every other pack keeps one carrier ≥ 5 MHz from it. **UK:** 8 gap carriers clear of Wi-Fi 1/6/11 (2423, 2426, 2448, 2451, 2473, 2476, 2479, 2482), one per pack (pack 1: 2414/2482). **US** (`host/channel_plan_us.yaml`): the 7 below 2480 go to packs 2–8; pack 1 has two in-band carriers, each ≥ 5 MHz from all others. Where a venue runs Wi-Fi 13, 2473/2476/2479/2482 are lost (packs 1, 6–8 lose their gap copy) |
| AIR-6 | TX power: software-set; region maximum enforced in firmware: **UK +7 dBm conducted** (9 dBm EIRP with the 2 dBi whip; nRF21540 at low gain, nRF5340 alone tops out at +3 dBm), **US +18 dBm** (20 dBm EIRP; BT40NE max +19.1 dBm, ADR-0007). Default region UK (ADR-0015) |
| AIR-7 | Airtime per carrier ≤ 45 % of frame (two copies, time diversity on, at 2 Mbps; 25 % with TD off, the default, ADR-0017) |

## 4. Bodypack

| ID | Requirement | Verify |
|---|---|---|
| PK-1 | Input: locking 3.5 mm TRS, Sennheiser SK pinout (confirm from Sennheiser SK 100 G4 manual in Phase 4), bias 5 V via 2.2 kΩ on the mic pin (R6) | Inspection |
| PK-2 | Max input 0.6 Vrms without clipping anywhere in the chain (R2); input-referred noise ≤ 1 µV A-weighted 20 Hz–20 kHz | ngspice `.noise`, `.tran` |
| PK-3 | ADC: PCM1840, 2 Vrms FS, DRE on; preamp fixed +6 dB single-supply 5 V (ADR-0006); second gain path populated on schematic, unused in v1 firmware | ngspice, Twister |
| PK-4 | SoC: nRF5340 pre-certified module with integrated FEM and u.FL (ADR-0007 names the part) | BOM |
| PK-5 | Antenna: 31 mm quarter-wave wire whip, exits top face, ≥ 40 mm from the cell (R15, R10) | CAD check |
| PK-6 | Power: one removable protected 18650 in a holder with positive retention; reverse-polarity protection; no charging circuit (R7). Boost to 5 V for preamp/bias; LDO 3.3 V | Schematic ERC |
| PK-7 | Runtime ≥ 16 h at max TX power continuous (R8). Design draw ≤ 0.6 W | `audit.py`, PPK2 |
| PK-8 | Controls: recessed slide power switch only (R4). LEDs: power/battery (green, red < 3.4 V; firmware shutdown < 3.2 V cell under load, ADR-0012), peak/clip (amber ≥ −10 dBFS, red ≥ −7 dBFS: the single-ended ADC input clips near −6.3 dBFS, ADR-0012). No "link" LED (one-way link cannot know) (R14) | Inspection |
| PK-9 | Config/DFU: recessed USB-C, USB CDC text protocol (`id`, `chan`, `power`, `region`, `save`, `info`), MCUboot serial DFU. Not a charging port | pytest over pty / DK |
| PK-10 | Telemetry in every frame: battery, peak, clip flag, temperature flag (AIR-3) | bsim |
| PK-11 | Enclosure body ≤ 100 × 65 × 25 mm (clip excluded), PETG, printed belt clip, battery door without tools, conformal-coated PCB (R15) | CadQuery tests |
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
| RK-2 | RF: per antenna input, LNA (NF ≤ 2 dB, input P1dB ≥ −10 dBm, IIP3 ≥ 0 dBm) → 1:8 splitter → 8 modules; coax loss budget 6 dB. Antennas (ADR-0016): 2× L-com HG2409P-NF 8 dBi patch, each on 15.2 m of 400-series coax + BNC jumper (4.2 dB). Install rule `docs/human/antenna-install.md`: front of stage, aimed upstage, ≥ 6 m above the stage floor; Wi-Fi ≥ 4.5 m behind/beside, ≥ 12 m in front (R1 rests on it). **R10 verification note:** the 2 BNC stay; the link-on-a-body check (Phase 5/6) uses these antennas mounted per the rule, and Phase 5 also measures their real rear lobes (datasheet plot: −9 dB) |
| RK-3 | Host: Raspberry Pi CM4 **without wireless** on the official CM4 IO Board (ADR-0018), ribbon to the main board; 8 module UARTs = CM4 UART0/3/4/5 + 2× SC16IS752 on SPI1, whose GPIOs drive every slot's nRESET/BOOT; Ethernet via a rear etherCON feedthrough; USB-C service = the CM4IO rpiboot port; boots to service ≤ 60 s |
| RK-4 | Front: per channel, lock LED and audio peak LED; no display |
| RK-5 | Main board (ADR-0018, `hw/rack/backplane.py`, Audit 6): per antenna, RF ESD + host-switched bias-T eFuse (off by default, 0.49 A) → DC block → QPL9057 LNA → QPQ1907 BAW → 3-stage microstrip Wilkinson (≤ 11 dB IL, ≥ 20 dB output isolation, ≥ 15 dB RL across 2400–2483.5 MHz on JLC04161H-7628). System NF at the antenna connector ≤ the 9.3 dB Audit 4 assumed, at the 6 dB coax budget, with the module nRF21540 LNA on (firmware bypasses it above −6 dBm at the radio). Per-slot eFuses on +12 V and +5 V; XLR pins 2/3 TVS ≥ 58 V standoff |

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
Downlink implementation, adaptive channel hopping, encryption, Dante/AES67, in-pack charging, e-ink, sub-GHz, 5 GHz, FCC certification filing, UKCA conformity assessment (selling or certifying is a stop-and-ask, hands-off.md reason 4), adaptive (LBT/DAA) or FHSS operation under EN 300 328 (ADR-0015).
