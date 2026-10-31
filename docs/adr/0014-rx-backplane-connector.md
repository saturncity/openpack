# ADR-0014: Receiver sub-board: backplane connector pinout, antenna switch, DAC and balanced driver
Status: accepted. 2026-10-31. Issue #32. Schematic `hw/rx/rx.py` (SKiDL), driver `hw/spice/rx_driver.cir`, tests `tests/test_rx_sch.py`, `tests/test_spice_rx_driver.py`.
- **Context:** RX-1/RX-8 fix the parts (nRF5340 module, SPDT switch, PCM5102, balanced driver, UART, I2S) and the levels (+18 dBu max, −20 dBFS = −2 dBu, Zout ≤ 100 Ω), not the board split, rails, connector or GPIO map. QUESTIONS.md keeps I2S on the backplane for a future digital add-on. ADR-0011 left the antenna GPIO a weak stub. Sources: TI PCM5102A SLAS859C (pins, 2.1 Vrms FS, 1 kΩ min load, 470 Ω/2.2 nF filter, BCK PLL); pSemi PE4259 DOC-03694-5.01 (pins, Table 5 truth table, RF ports DC-blocked, 0.5 dB IL / 20 dB isolation at 2 GHz); TI OPA1656 SBOS901C (4.5–36 V, CM (V−)…(V+)−2.25 V, swing 0.25 V, AOL range 0.5 V from the rails at 2 kΩ); Fanstel BT40 spec v1.08 (pads, ADR-0012); Zephyr `nrf5340_cpuapp_common-pinctrl.dtsi` (uart0 TX P0.20, RX P0.22).
- **Decision:**
  - **Board split.** Each sub-board is a mezzanine on the rack's main board (#33): a 2×13 2.54 mm header underneath, u.FL coax from the splitters. XLRs sit on the main board at the rear panel. Balanced audio crosses the connector already protected. Boards are swapped with the rack off. Live insertion is survivable: TVS on both rails, 1 kΩ in series with every host-driven line and 100 Ω with every module-driven line, so the GPIO ESD diodes carry at most ~3 mA.
  - **Rails.** +12 V (brick) for the driver through 10 Ω + 100 µF. +5 V from one rack buck (the CM4 needs one anyway) feeds two TLV75533P: +3V3 (module, DAC DVDD, switch) and +3V3A (DAC AVDD + CPVDD).
  - **RF.** J3 ANT_A / J4 ANT_B → 10 pF DC blocks → PE4259 RF2 / RF1 → RFC → J5 → 50 mm U.FL jumper → module u.FL. **ANT_SEL = P1.01 (pad D6), net-core GPIO, 100 k pull-down: low = antenna A** (`op_rx_ant_select(0)`), high = B. The module's own nRF21540 ANT_SEL (P1.05) must pick its u.FL port.
  - **GPIO.** UART TX P0.20 (C5), RX P0.22 (D5), the DK console pins, no flow control (P0.21 is a FEM pad). I2S master BCK P0.24 (C3), LRCK P0.23 (C4), SDOUT P0.13 (B6). DAC XSMT P0.12 (B5, pulled low = muted until firmware un-mutes). LEDs P1.09/P1.10. MCUboot recovery BOOT P1.02 (pad 1, 10 k pull-up). Slot ID P1.11–P1.13 (10 k pull-ups, the backplane grounds bits). nRESET pad 14. SWD on Tag-Connect pads.
  - **DAC.** PCM5102A: I2S (FMT = 0), 3-wire BCK PLL (SCK = GND, BCK = 32 or 64 fs), DEMP off, **low-latency filter (FLT = 1)**: 3.5/fs = 73 µs instead of 22/fs = 458 µs, about 330 µs off SPEC §2's 400 µs line. Mono on OUTL; OUTR is left open.
  - **Driver.** OPA1656 on +12 V, two inverting stages, so both + inputs sit at VCM = 6 V and the CM never moves (limit 9.75 V, 9.15 V at 11.4 V). Leg A = −3.65k/(2.0k + 470) = −1.478 → XLR 3 (cold); leg B = −1 × leg A → XLR 2 (hot, in phase with the DAC). Each output: 22 Ω → BAV99 clamp to the rails → 47 µF 63 V bipolar (phantom-tolerant) → 22 Ω → connector, with 100 k bleed.
- **Numbers (`tests/test_spice_rx_driver.py`):** 0 dBFS = **+18.00 dBu**, −20 dBFS = **−2.00 dBu**. 20 Hz–20 kHz −0.06/+0.00 dB into 10 kΩ. **Zout 88 Ω** balanced at 1 kHz (350 Ω at 20 Hz, from the DC blocks). At 0 dBFS into 2 kΩ, outputs 1.27–10.05 V on an 11.32 V rail, ≥ 0.77 V clear of the 0.5 V swing limit. 12 V rail → out −96 dB at 1 kHz (−46 dB at 20 Hz). Output noise **−103.7 dBu** (20 Hz–20 kHz), 9.7 dB under the DAC's own floor (−94 dBu). Into a legacy 600 Ω load: −2.0 dB at 20 Hz, reported only.
- **BOM** (`hw/rx/out/bom.csv`, printed by `audit.py`): **$29.70 / £22.61 per sub-board** at qty 100, with the BT40NE at DigiKey ($16.76; Fanstel direct $13.47 gives $26.41). GBP is converted at 0.76, ex VAT, not a UK quote. SPEC/AUDIT give no per-receiver cap. QUESTIONS.md Q14 guessed "receiver ~$150–250 in parts" for the whole rack, but 8 sub-boards alone come to ~$238 before the main board, splitters, CM4 and panel.

## Backplane connector J1 (sub-board side, 2×13 2.54 mm; odd pins one row, even the other)

| Pin | Net | Dir (sub-board) | Note |
|---|---|---|---|
| 1 | `GND` | — | |
| 2 | `GND` | — | |
| 3 | `AUD_HOT` | out | XLR pin 2, DC-blocked, phantom-tolerant |
| 4 | `AUD_COLD` | out | XLR pin 3; XLR pin 1 = main-board chassis/GND |
| 5 | `GND` | — | guard between audio and power |
| 6 | `GND` | — | |
| 7 | `+12V` | in | driver rail, ≤ 30 mA |
| 8 | `+12V` | in | |
| 9 | `+5V` | in | LDOs, ≤ 120 mA (module RX + DAC) |
| 10 | `+5V` | in | |
| 11 | `GND` | — | |
| 12 | `GND` | — | |
| 13 | `BP_I2S_BCK` | out | 100 Ω series; future digital add-on, leave open if unused |
| 14 | `GND` | — | |
| 15 | `BP_I2S_LRCK` | out | 100 Ω series |
| 16 | `BP_I2S_SDOUT` | out | 100 Ω series |
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

| R-id | Mezzanine + XLR on main board (chosen) | XLR on each sub-board | Inverting driver, +12 V (chosen) | Non-inverting + inverter, +12 V | ±5 V charge pump | FLT low latency (chosen) | FLT normal |
|---|---|---|---|---|---|---|---|
| R9 1U, 8 XLR | ✓ fits 1U flat | partial: 8 vertical cards don't fit 44 mm | ✓ | ✓ | ✓ | – | – |
| R3 latency | – | – | – | – | – | ✓ −330 µs | ✗ |
| R5 audio | ✓ | ✓ | ✓ +18 dBu, −103.7 dBu noise | partial: + input swings to 8.7 V vs the 9.15 V CM limit at 11.4 V | partial: 0.34 V swing margin | ✓ (stop band past 24 kHz) | ✓ |
| R11 remote mgmt | ✓ UART + reset + boot on the connector | ✓ | – | – | – | – | – |
| R12 cost | ✓ one header | ✗ 8 PCB XLRs + panel fit | ✓ | ✓ | ✗ +1 IC | ✓ | ✓ |

- **Consequences / open items:**
  1. #33 must follow this pinout. Its main board carries the XLRs, the CM4 UART fan-out, the front LEDs (with their resistors), the slot straps and the rack buck. Mechanical keying (asymmetric standoffs) is needed because a 2×13 header can be fitted rotated.
  2. Firmware owes a devicetree overlay for the rx board: I2S pinctrl, `op_rx_ant_select()` driving P1.01 from the net core (MCUSEL = network), XSMT, slot read, and the module ANT_SEL → u.FL.
  3. PE4259 tuning cap and isolation at 2.4 GHz (≈18–20 dB) come with layout (#34). The jumper adds ~0.3 dB loss.
  4. Power-up thump: VCM ramps with τ ≈ 2.3 s through the output caps. Mute the desk first, or add a relay later.
  5. Phantom short: a cable charged to 48 V and then shorted puts ≤ 2 A for ~1 ms through a BAV99 (rated 4 A at 1 µs, 1 A at 1 ms). Bench-test it, and use a 1 A Schottky pair if it fails.
  6. UK owner: GBP figures are conversions; each line's UK distributor and stock must be confirmed with live quotes before #40.
  7. Region (UK rules, being re-decided): the receiver has no PA, and the BT40NE's nRF21540 serves only as the LNA here. No part value on this board depends on the region. If the pack drops to +10 dBm and a module without a FEM is chosen, the receiver keeps the BT40NE for the LNA (re-check the module price then).
  8. The custom footprints (BT40NE) come with layout.
