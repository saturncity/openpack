# ADR-0014: Receiver sub-board: backplane connector pinout, antenna switch, DAC, balanced driver, output mute
Status: accepted. 2026-10-31, amended after the #81 review; amended 2026-11-01 for ADR-0021 (module BT40NE → BT40E, see the amendment at the end). Issue #32. Schematic `hw/rx/rx.py` (SKiDL). SPICE decks `hw/spice/rx_driver*.cir` with the shared `opa1656.lib`. Tests `tests/test_rx_sch.py`, `tests/test_spice_rx_driver.py`.
- **Context:** RX-1/RX-8 fix the parts (nRF5340 module, SPDT switch, PCM5102, balanced driver, UART, I2S) and the levels (+18 dBu max, −20 dBFS = −2 dBu, Zout ≤ 100 Ω). They do not fix the board split, rails, connector, GPIO map or mute. QUESTIONS.md keeps I2S on the backplane for a future digital add-on. ADR-0011 left the antenna GPIO a weak stub. The owner is UK-based.
- **Sources:**
  - TI PCM5102A SLAS859C: pins, 2.1 Vrms full scale (typical), 1 kΩ minimum load, 470 Ω/2.2 nF filter, BCK PLL, Table 3/4/7 filters, §11.2 XSMT.
  - pSemi PE4259 DOC-03694-5.01: pins, Table 5, DC-blocked RF ports, 0.5 dB / 20 dB at 2 GHz.
  - TI OPA1656 SBOS901C: 4.5–36 V, CM (V−)…(V+)−2.25 V, AOL range 0.5 V from the rails at 2 kΩ, ZO 26 Ω, ±10 mA input.
  - TI TLV767 SLVSE84D (VIN abs max 18 V) and TPS3808 SBVS050N (DBV pins, 0.405 V threshold, open-drain RESET).
  - Panasonic TQ relay datasheet, SA schematic (coil 1+/10−; COM 3/8, NC 2/9, NO 4/7; release ≤ 4 ms).
  - Fanstel BT40 v1.08 (ADR-0012); Zephyr `nrf5340_cpuapp_common-pinctrl.dtsi` (uart0 TX P0.20, RX P0.22).
- **Decision:**
  - **Board split.** The sub-board is a mezzanine on the rack main board (#33): a 2×13 2.54 mm header, **pin 14 pulled as the key** (its hole is plugged in the socket), and u.FL from the splitters. The XLRs are on the main board.
    - With the key, a 180° insertion cannot be made. Without it, +12 V would land on nRESET/BOOT.
    - Live insertion is tolerated. TVS on both rails: SMF15A ≤ 24.4 V, SMF5.0A ≤ 9.2 V.
    - Every part on +5 V survives 9.2 V. The LDOs are TLV76733 (18 V abs max), not TLV755P (6 V). A 47 µF electrolytic damps the +5 V ring.
    - Series resistors: 1 kΩ on host-driven lines, 100 Ω on module-driven lines. With a slot unpowered and the CM4 up, the six host lines back-power +3V3 with ≤ 15 mA in total; accepted.
  - **Rails.** The driver takes +12 V through 10 Ω, then a **BAT54 hold-up diode**, then 100 µF (+12VA). The diode stops C7 draining into a collapsing backplane. +5 V from the rack buck feeds two TLV76733: +3V3 (module, DAC DVDD, switch, supervisor) and +3V3A (DAC AVDD + CPVDD).
  - **RF.** J3 ANT_A / J4 ANT_B → 10 pF → PE4259 RF2 / RF1 → RFC → J5 → U.FL jumper → module u.FL.
    - **ANT_SEL = P1.01 (pad D6)**, a net-core GPIO with a 100 k pull-down. Low = antenna A (`op_rx_ant_select(0)`).
    - The BT40E (ADR-0021) has one RF port, its u.FL, wired straight to the nRF5340: no FEM, no module ANT_SEL. P1.05 is an unused GPIO.
  - **GPIO map.**
    - UART: TX P0.20 (C5), RX P0.22 (D5). These are the DK console pins; no flow control.
    - I2S master: BCK P0.24 (C3), LRCK P0.23 (C4), SDOUT P0.13 (B6). The PCM5102A PLL needs BCK = 32 or 64 fs (SLAS859C Table 11), so firmware uses 16- or 32-bit slots.
    - **XSMT_EN** P0.12 (B5), through 10 k. **OUT_EN** P0.11 (pad 12), relay.
    - LEDs P1.09/P1.10. BOOT P1.02. Slot ID P1.11–P1.13. nRESET pad 14. SWD on Tag-Connect.
  - **DAC.** PCM5102A in I2S mode, 3-wire BCK PLL, DEMP off, mono on OUTL.
    - **FLT high = low-latency IIR filter.** Group delay is 3.5/fs = 73 µs instead of 22/fs = 458 µs (Tables 4/7), saving 385 µs. **SYS-2 needs it** (latency analysis, PR #88).
    - Trade-off: stop band −52 dB instead of −60 dB above 0.55 fs, and non-linear phase. Pass band ±0.0001 dB.
  - **Driver.** OPA1656 on +12VA as two inverting stages, so both + inputs sit at VCM and the input common mode never moves.
    - Leg A = −3.65k/2.47k = −1.478 → XLR 3. Leg B = −leg A → XLR 2, in phase.
    - **VCM has two RC poles** (22k/22k + 22 µF, then 10 k + 22 µF), because VCM ripple reaches the XLR differentially at ×2.96.
    - **BAT54 from VCM to +12VA** so that at power-down C49 empties into the rail, not into the op-amp inputs.
  - **Output path, each leg.** 22 Ω → **S1J clamps to both rails** (IFSM 30 A) → 47 µF 63 V bipolar → 10 k bleed (cap side held at 0 V) → **relay contact (normally open)** → 100 k bleed → 22 Ω → connector.
  - **Mute (relay K1).**
    - K1 is a TQ2SA-12V. Its 12 V coil is switched by a BSS138 with an S1J flyback diode.
    - The BSS138 gate is driven by **OUT_EN via 10 k, wired-AND with a TPS3808G01 open-drain output**. The supervisor senses raw +12 V through 249k/9.76k and trips at 10.78 V. A 100 k pull-down holds the relay open through reset.
    - The supervisor also pulls **XSMT** low through a BAT54 (SLAS859C Fig. 38 "in parallel with a GPIO").
    - Firmware closes K1 ≥ 5 s after power-up, once VCM has settled; RK-3 allows 60 s.
  - **I2S to the backplane: R33–R35 not fitted (DNP).** Without them, eight 3 MHz stubs don't run beside the LNA/splitters. Fit 100 Ω for a digital add-on.
- **Numbers (ngspice, `tests/test_spice_rx_driver.py`; OPA1656 macromodel in `opa1656.lib`):**
  - Level: 0 dBFS = **+17.98 dBu**, −20 dBFS = **−2.02 dBu**. **Headroom: the outputs reach the swing limit at +19.4 dBu on the worst rail (11.2 V), 1.4 dB above full scale.** This covers the DAC's typical-only 2.1 Vrms.
  - Response: 20 Hz–20 kHz −0.06 dB into 10 kΩ. **Zout 88 Ω** at 1 kHz.
  - Swing at 0 dBFS into 2 kΩ: 1.21–10.00 V on an 11.2 V rail.
  - **Supply rejection (+12 V → XLR): −100 dB at 100 Hz** (asserted ≤ −80), −60 dB at 20 Hz. Noise −103.7 dBu.
  - **Into 10 nF per leg + 600 Ω: phase margin 50° / 49°** (asserted ≥ 45°). Step overshoot 0.35 % (asserted ≤ 10 %).
  - **Phantom short** (P48, relay closed, charged pin shorted): S1J peak 0.86 A, I²t 0.38 mA²s, against 3.7 A²s from IFSM. The cap holds about 21 V, not 39 V, because the 10 k cap-side bleed sits against the 6.8 k phantom feed.
  - **Power cycle** (on → K1 closes at 5 s → brick dies at 6 s): XLR differential < 1 µV, common mode 12 µV. K1 opens 8 ms after the trip; the hold-up keeps the op-amps linear meanwhile. VCM never exceeds +12VA.
- **BOM** (`hw/rx/out/bom.csv`, printed by `audit.py`): **$30.68 / £23.38 per sub-board** at qty 100.
  - The BT40E is priced at Digi-Key UK, £9.78 qty 100 (converted to $12.86); was the BT40NE at $16.76. Other GBP figures are conversions at 0.76 ex VAT, not UK quotes. Each line names a UK-reachable distributor.
  - The mute adds about $4.2: relay, supervisor, FET, diodes.
  - SPEC/AUDIT set no cap. Q14's "~$150–250" guess for the whole rack is exceeded by the 8 sub-boards alone ($245).

## Backplane connector J1 (sub-board side, 2×13 2.54 mm; odd pins one row, even the other)

| Pin | Net | Dir (sub-board) | Note |
|---|---|---|---|
| 1 | `GND` | — | |
| 2 | `GND` | — | |
| 3 | `AUD_HOT` | out | XLR pin 2, DC-blocked, phantom-tolerant, relay-muted |
| 4 | `AUD_COLD` | out | XLR pin 3; XLR pin 1 = main-board chassis/GND |
| 5 | `GND` | — | guard between audio and power |
| 6 | `GND` | — | |
| 7 | `+12V` | in | driver ≤ 30 mA + relay coil 12 mA |
| 8 | `+12V` | in | |
| 9 | `+5V` | in | LDOs, ≤ 120 mA (module RX + DAC) |
| 10 | `+5V` | in | |
| 11 | `GND` | — | |
| 12 | `GND` | — | |
| 13 | `BP_I2S_BCK` | out | not driven (R33 DNP); future digital add-on |
| 14 | `KEY` | — | pin pulled from the header; socket hole plugged |
| 15 | `BP_I2S_LRCK` | out | not driven (R34 DNP) |
| 16 | `BP_I2S_SDOUT` | out | not driven (R35 DNP) |
| 17 | `BP_UART_TX` | out | module TX (P0.20) → host RX, 100 Ω, 3.3 V |
| 18 | `BP_UART_RX` | in | host TX → module RX (P0.22), 1 kΩ |
| 19 | `BP_nRESET` | in | open-drain from host, 1 kΩ (RX-10, FW-6) |
| 20 | `BP_BOOT` | in | low at reset = MCUboot serial recovery, 1 kΩ |
| 21 | `BP_LED_LOCK` | out | RK-4, drives a front-board LED + its resistor, 100 Ω |
| 22 | `BP_LED_PEAK` | out | RK-4, 100 Ω |
| 23 | `BP_SLOT0` | in | slot ID bit 0: GND = 0, open = 1 (1 kΩ) |
| 24 | `BP_SLOT1` | in | slot ID bit 1 |
| 25 | `BP_SLOT2` | in | slot ID bit 2 |
| 26 | `GND` | — | |

- **Requirements check** (choices SPEC leaves open):

| R-id | Mezzanine + XLR on main board (chosen) | XLR on each sub-board | Inverting driver, +12 V (chosen) | Non-inverting + inverter | ±5 V charge pump | Relay + supervisor mute (chosen) | No mute ("mute the desk") | FLT low latency (chosen) | FLT normal |
|---|---|---|---|---|---|---|---|---|---|
| R9 1U, 8 XLR | ✓ | partial: vertical cards don't fit 44 mm | ✓ | ✓ | ✓ | ✓ | ✓ | – | – |
| R3 latency | – | – | – | – | – | – | – | ✓ −385 µs (SYS-2) | ✗ |
| R5 audio | ✓ | ✓ | ✓ +18 dBu, 1.4 dB headroom | partial: +IN to 8.7 V vs 9.15 V | partial: 0.34 V swing margin | ✓ no thump on power loss | ✗ thump into the PA on a brick failure | partial: −52 dB stop band | ✓ |
| R1 dropouts | – | – | – | – | – | ✓ relay closes only when settled | ✓ | – | – |
| R11 remote mgmt | ✓ UART, reset, boot | ✓ | – | – | – | ✓ firmware-controlled | – | – | – |
| R12 cost | ✓ | ✗ | ✓ | ✓ | ✗ | partial: +$4.2 per channel | ✓ | ✓ | ✓ |

- **Consequences / open items:**
  1. #33 must follow this pinout and its key (plug socket position 14). The main board must also provide:
     - an XLR-pin ESD/TVS rated ≥ 58 V standoff, so it survives P48 at 52 V;
     - CM4 UART fan-out, front LEDs with resistors, slot straps, and the rack buck.
  2. Firmware owes an rx devicetree:
     - I2S pinctrl at 32/64 fs;
     - `op_rx_ant_select()` driving P1.01 from the net core;
     - XSMT_EN and OUT_EN, with OUT_EN set ≥ 5 s after boot and only after XSMT is un-muted;
     - slot read;
     - no FEM node: the #107 nRF21540 node is pack-only (`fw/boards/role_rx_cpunet.overlay`, ADR-0021).
  3. The stability numbers rest on a macromodel with an **assumed** second pole at 30 MHz, not taken from the datasheet. Re-run with TI's OPA1656 model, or bench a step into 10 nF. If it rings, move the 22 Ω inside the loop.
  4. The relay release time with the flyback diode is modelled as 8 ms; measure it on the bench. The supervisor trip is 10.78 V ± 1.5 %. A brick sagging slowly to just above the trip is not a thump case, because the outputs stay linear.
  5. PE4259 tuning cap and its ≈18–20 dB isolation at 2.4 GHz come with layout (#34). The jumper costs about 0.3 dB.
  6. C47/C48 (10 mm radial bipolar) and K1 heights must be checked against the mezzanine stack in 1U before #33 fixes the standoffs.
  7. UK: the GBP figures are conversions. Confirm live quotes and stock before #40.
  8. Region (UK rules, being re-decided): the receiver has no PA, and no part value on this board depends on the region.
     - **LNA:** ADR-0015 (PR #86) finds that a per-receiver LNA adds only 0.7 dB behind the rack LNA. This board never had a discrete LNA or its bias/match parts, so nothing is removed and nothing is saved.
     - The BT40E has no nRF21540, so there is nothing to bypass (ADR-0021).
  9. ~~Custom footprints come with layout~~: done in #34 (`hw/rx/footprints_rx.py`): BT40E from the p.11 drawing; TQ2SA land pattern from the Panasonic TQ datasheet p.11 (SA suggested mounting pad); C47/C48 = Nichicon UEP1J470MPD 10 × 16 mm, 30.1 mm above the main board (closes item 6 for #33, hw/REVIEW.md). The #34 layout also mounts J1 as a THT header on the underside (mezzanine retention), and the footprint has **no hole at 14** (#116 review S1): the header is XFCN PZ254V-12-26P (LCSC C22465887) with pin 14 cut, and the main-board socket (#33) is the **BOOMELE C64320 2×13 female with contact 14 pulled and the cavity plugged** (#34, ADR-0018 amended; was the Harwin M20-7831346 + M20-003 key).

## Amendment 2026-11-01: receiver module BT40NE → BT40E (ADR-0021, #112)

- **Why:** ADR-0021 (PR #103) puts the rack antennas in the wings. The wings need system NF ≤ 21.1 dB; the BT40E gives 11.5 dB behind PR #95's QPL9057 + QPQ1907 + Wilkinson chain, every stage stays ≥ 6 dB under P1dB (the BT40NE's always-on nRF21540, P1dB −18 dBm, did not), and the receiver never transmits in v1 (ADR-0004). The pack keeps the BT40NE (ADR-0007).
- **Datasheet checks** (Fanstel *BT40/F/E/N/NE Product Specifications* v1.09, July 2024):
  - **RF port:** u.FL receptacle on the module, the only antenna port (p.1 Model Summaries "u.FL"; p.11 drawing). The PE4259 RFC → C22 → J5 → 50 mm U.FL jumper → BT40E u.FL path is unchanged.
  - **Pinout:** p.14 "Pin Assignments of BT40" (shared by the BT40 and BT40E): the same pad names and nRF5340 pins as the BT40F/NE table (pp.16–17), F5 = NC. The nine BT40NE FEM pads (Z6, A6, C2, C6, D1, D2, E0, E1, E2) are plain GPIO; this board uses none of them, so the **GPIO map above and the firmware pins do not change**. P1.05 (E1) stays unconnected.
  - **Footprint:** 14 × 16 × 2.0 mm, 16 castellated + 45 LGA pads + H0–H3 ground pads (p.11), not the BT40NE's 15 × 29.9 mm. `openpack:Fanstel_BT40E` comes with layout (#34).
  - **Decoupling:** crystals and both DC/DC inductors are on the module, "no external component is required" (p.26); the supply must be ripple-free, with a ferrite + ≥ 47 µF only for a noisy one (p.27). +3V3 is a TLV76733 LDO, so C10 10 µF + C11 100 nF at VDD and C12 100 nF at VDDH stay as they are.
  - **HFXO:** Fanstel sets the internal load capacitors to 11 pF for the BT40E (12.5 pF for the BT40NE, p.18). The rx board target (when it exists) sets that; the DK has its own crystal.
- **Certification:** FCC ID **X8WBT40F** / ISED 4100A-BT40F cover the BT40E, tested with the 6 dBi ANT060 dipole (p.1, p.3); TELEC 201-210217/01; "CE, RCM: Compliant". No Fanstel UKCA or EU DoC is published (as for the BT40NE, `docs/analysis/module-antenna.md`). The receiver is receive-only, so the rack's UK DoC under the Radio Equipment Regulations 2017 covers EN 300 328 receiver requirements (blocking) and EN 301 489-1/-17 for the finished rack; ask Fanstel for the BT40E EN 300 328 report before #40.
- **Firmware:** the #107 nRF21540 node stays in the DK net-core overlay for the pack. Receiver builds (`SB_CONFIG_OP_ROLE_RX=y`) add `fw/boards/role_rx_cpunet.overlay`, which disables it and drops `&radio { fem }`; `fw/src/rx/rx.c` fails to compile if the node or `CONFIG_OP_FEM_NRF21540` is still enabled.
- **BOM:** BT40E at Digi-Key UK £9.7765 qty 100 cut tape (803 in stock, 10 wk, read 2026-11-01) = $12.86 at 0.76. Sub-board $34.58 → **$30.68** (£26.35 → £23.38): −$3.90 / −£2.97 per sub-board, **−$31 / −£24 per rack** at Digi-Key UK. ADR-0021's −$58 compares Fanstel direct ($9.55) with the BT40NE at Digi-Key; buying both direct gives −$31 too ($13.47 − $9.55 = $3.92 × 8).
- **Gone:** consequences item 2's "module ANT_SEL → u.FL" and item 8's FEM bypass; the receiver half of #105's ANT_SEL open item.
