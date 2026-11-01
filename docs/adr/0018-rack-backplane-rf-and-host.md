# ADR-0018: Rack main board: LNA + BAW filter + 1:8 Wilkinson per antenna, fused slots, CM4 IO board as the host carrier
Status: accepted. 2026-11-01. Issue #33. Schematic `hw/rack/backplane.py` (SKiDL, ERC 0/0). Splitter model `hw/rack/wilkinson.py`. Numbers `python3 audit.py` Audit 6. Tests `tests/test_backplane_sch.py`, `tests/test_rack_rf.py`.
- **Context:** RK-1..RK-3 fix the rear panel (8 XLR, 2 BNC with switchable 12 V bias-T, RJ45, USB-C service, 12 V brick), the RF chain (LNA NF ≤ 2 dB → 1:8 splitter → 8 modules, 6 dB coax budget) and a CM4 host. ADR-0014 fixes the slot connector (key at 14). ADR-0016 (PR #93) fixes the antennas: 2 × 8 dBi patch on 15.2 m coax (4.2 dB), install rule ≥ 4 m to actors, Wi-Fi ≥ 4.4 m behind / ≥ 12.2 m in front, 3 dB R1 C/I margin. Open: the parts, the splitter, the power tree, how 8 UARTs reach the CM4, and the carrier. The owner is UK-based.
- **Sources:** Qorvo QPL9057 datasheet Rev. F (pins, EVB, S/noise parameters, abs max). TI TPS2595 SLVSE57C (pins, Eq. 4 R_ILM = 2000/(I − 0.04), UVLO 1.2/1.1 V, EN ≤ 6 V, variants). TI TPS62933 SLUSEA4D (pins, 5 V/3 A reference design). NXP SC16IS752 Rev. 9.1 Table 2 (TSSOP-28 pins, SPI mode, IRQ 1 kΩ). Infineon ESD101-B1 datasheet (±5.5 V, 0.1 pF). ESD103-B1 (±15 V, 0.09 pF): from Infineon's datasheet v2.0 as quoted by Farnell/LCSC listings; the PDF itself was not read. Raspberry Pi CM4 datasheet (Table 1 alt functions, 5 UARTs) and CM4IO datasheet (12 V jack, on-board 5 V, J2 nRPIBOOT, micro-USB rpiboot, 40-way J8). DigiKey UK pages (GBP, stock) on 2026-11-01. JLCPCB JLC04161H-7628 stackup.
- **Decision:**
  - **RF chain, per antenna** (`rf_a`, `rf_b`): BNC (Amphenol 112487, 4 GHz) → **ESD103-B1-02EL** (±15 V, 0.09 pF; survives the bias) → **bias-T**: 39 nH LQW18AN (SRF 3.28 GHz, 1 A) to 100 pF + 10 nF, 10 Ω, SMF12A, fed by a **TPS259541 eFuse** (0.49 A limit, 13.7 V clamp). EN is a host GPIO with a 100 k pull-down, so the bias is **off by default** (the HG2409P is passive) and a DC-shorted antenna trips the eFuse; FLT goes to the host → **100 pF DC block** → **ESD101-B1-02EL** at 0 V (the LNA is HBM class 1B) → **QPL9057** per its EVB (5.1 k bias, 18 nH choke, 100 pF blocks, SD tied low) → **QPQ1907 BAW band-pass** (2402.5–2481.5 MHz, ≤ 2.2 dB), after the LNA so its loss barely costs NF → 1:8 Wilkinson → 8 u.FL → 200 mm u.FL cables to each sub-board's J3 (A) / J4 (B).
  - **Splitter:** a 3-stage corporate Wilkinson in L1 microstrip over L2 on JLC04161H-7628 (h 0.2104 mm, εr 4.4 per JLCPCB, tan δ 0.02 est.). 50 Ω = 0.387 mm; 70.7 Ω arms = 0.196 mm × 17.76 mm (λ/4 at 2441.75 MHz); 100 Ω 0402 thin-film isolation resistors (7 per tree); compact tree (feeds 5/10/6/5 mm). The arms are `TL` parts (net-tie copper) so the netlist keeps each divider explicit.
  - **Power:** 2.1 mm jack (PJ-063AH) → AO4407A P-FET reverse protection (12 V Vgs zener) → SMBJ12A (VC 19.9 V, under the TPS2595 20 V abs max) → **TPS259541 input eFuse**: 3.5 A, UVLO on at 9.98 V / off at 9.15 V. Then:
    - TPS62933 5 V / 3 A (TI reference design);
    - TLV76733 3.3 V;
    - **per slot, a TPS259541 on +12 V and a TPS259531 (5.7 V clamp) on +5 V**, 0.49 A each, dV/dt 22 nF (≈ 0.2 A inrush). A shorted sub-board trips only its own eFuses, auto-retries, and the other seven keep running;
    - a 1.5 A eFuse to the CM4IO over a JST VH pigtail.
    - All power FLT pins are wire-ORed to one host GPIO.
    - Load (est.): slots 8 × 42 mA at 12 V, CM4IO 0.75 A (its 9 W budget), the 5 V rail ~1.1 A (0.5 A from 12 V), so ~1.6 A, or 2.6 A with both bias-Ts at their limit. That is under the 3.5 A input limit and the 5 A brick.
    - Chassis (XLR pin 1 and shells) bonds to GND once, at NT1.
  - **Slots:** the ADR-0014 socket (Sullins PPPC132LFBN-RC; position 14 plugged), slot-ID straps (bit 0 = GND, 1 = open), I2S NC, front LEDs (560 Ω, ~2 mA, green lock / red peak) and an XLR NC3MAH. Pin 2 is hot, pin 3 cold; pin 1 and the shell go to chassis. **SMAJ58CA on pins 2 and 3** (VRWM 58 V ≥ P48 52 V max).
  - **Host carrier: the official Raspberry Pi CM4 IO Board (SC0326)** with a **CM4 without wireless** (CM4002008 = SC0680), on a 40-way ribbon (pin n to pin n) to the main board's J2.
    - UARTs: CM4 UART0/3/4/5 (GPIO14/15, 4/5, 8/9, 12/13) serve slots 0–3. Two SC16IS752 on SPI1 (CE0/CE1, IRQ GPIO24/25, 14.7456 MHz) serve slots 4–7.
    - The SC16IS752s' 16 GPIOs drive every slot's nRESET/BOOT as **software open drain**: they reset to inputs (released), and the host drives output-low to assert.
    - Bias EN/FLT on GPIO22/23/26/27, power fault on GPIO6. HAT-ID GPIO0/1 and the CM4IO rails are left unconnected.
    - Ethernet: the CM4IO RJ45, by a 0.3 m patch to a rear **Neutrik NE8FDP etherCON** feedthrough.
    - RK-1 "USB-C service": a panel USB-C to micro-USB lead into the CM4IO rpiboot port (plugging it in disables the hub; J2 nRPIBOOT forces USB boot).
  - **Module LNA stays on (BT40NE on the receivers).** At the 6 dB coax budget, with the nRF21540 bypassed, system NF is 10.27 dB, worse than the 9.30 dB Audit 4 / ADR-0016 used. With it on, NF is 8.50 dB. Firmware therefore keeps it on and bypasses it on RSSI (radio input > −6 dBm, back on below −12 dBm). This retires ADR-0015's "BT40E on the rx modules" option.
- **Numbers** (`audit.py` Audit 6, worst-case datasheet limits unless marked typ):
  - **QPL9057 at 2442 MHz:** gain 22.4 dB, NF 0.48 typ / **0.90 max** (RK-2 ≤ 2 dB), IIP3 +14.6 typ / **+6.6 dBm worst**, input P1dB −4.3 typ / **−6.9 dBm worst** (RK-2 per PR #93: ≥ −10 / ≥ 0). Abs max +27 dBm.
  - **Wilkinson 1:8, 2400–2483.5 MHz:** IL 10.56–10.61 dB (ideal 9.03; scikit-rf MLine 10.24), imbalance 0.00 dB, output-to-output isolation ≥ 30.3 dB, RL in 36.3 / out 39.2 dB. εr 4.2–4.6 keeps isolation ≥ 20 dB and RL ≥ 15 dB. Audit 6 adds 0.5 dB for junctions and bends.
  - **System NF at the antenna connector**, module LNA on (bypassed): **6.70 (8.47) dB** with the ADR-0016 4.2 dB coax, **8.50 (10.27) dB** at the 6 dB budget. The worst case gives −92.5 dBm sensitivity and a 44 m indoor range at UK 9 dBm. Receiver noise uses **0.01 dB of the 3 dB R1 margin**.
  - **Compression:**
    - Install rule (near pack at 4 m at US 20 dBm, 3 Wi-Fi channels and a B40 phone at rule distance, short coax): −22.9 dBm at the LNA input, **16.0 dB below P1dB**.
    - Everything off-rule (pack at 1 m; Wi-Fi 1/6/11 and a B40 phone 2 m in front): −9.1 dBm, 2.3 dB below the worst P1dB (4.9 below typical).
    - IM3 is −84 dBm per 2 MHz, against a −43 dBm wanted signal.
    - The near pack reaches the radio at −4.6 dBm (rule, module LNA on) and −6.5 dBm (off-rule, bypassed), against a 0 dBm maximum.
  - **BOM, one rack, GBP ex VAT:**
    - main board, host and cables **£396.88** (£112.98 of it estimates);
    - 8 sub-boards £210.80 (converted USD);
    - antennas £340.56 (ADR-0016);
    - **rack £948.24**. No cap is set.
- **Requirements check** (carrier and UART fan-out: no QUESTIONS.md default covers them):

| R-id | CM4IO + ribbon, CM4 UARTs + 2× SC16IS752 (chosen) | CM4 on the main board (custom carrier) | CM4IO + USB hub + 2× FT4232H | Pi 4/5 SBC instead of a CM4 |
|---|---|---|---|---|
| R1 dropouts | ✓ CM4 without radio; host crash leaves audio running (slots power on without it) | ✓ | ✓ | partial: on-board Wi-Fi must be disabled in software |
| R9 1U, 8 XLR | ✓ 160 × 90 mm board beside the main board, ~25 mm tall (est., item 5) | ✓ smaller | ✓ | partial: USB/Ethernet face the wrong way, 2 extra cables |
| R11 remote mgmt | ✓ GbE, every slot UART + reset + boot | ✓ | ✓ | ✓ |
| R13 sim/design first | ✓ the vendor board needs no new design; the SC16IS752 pinout was read from its datasheet | partial: Ethernet magnetics, CM4 pinout and power are new, unverified design | ✗ the FT4232H datasheet could not be read (ftdichip.com 403); 64-pin part | ✓ |
| RK-3 boot ≤ 60 s | ✓ eMMC | ✓ | ✓ | partial: SD card |
| R12 cost (rack; no cap) | partial: +£26.15 board +£11.84 UARTs | ✓ cheapest | partial: +~£15 | partial |

- **Consequences / open items:**
  1. **QPQ1907: the pinout (assumed 1 in / 3 out / 2, 4, 5 GND) and the stop-band rejection at 2390 MHz were not read** (qorvo.com rate-limited). Confirm both before layout (#34). With no filter credit, an LTE B40 phone reaches the radio at −11.2 dBm (rule) to +4.6 dBm (off-rule), and the nRF5340 blocking limit for that offset is unverified. If either fails: add a second BAW or pick a B40-coexistence part.
  2. **Stock (DigiKey UK, 2026-11-01):**
     - CM4 SC0680 is 0 in stock; the fallback is 4 GB SC0684/5 at £85.93, no-wireless status to be verified;
     - TPS259541 stock was not shown (20-week lead);
     - DMP3013SFV is 0 in stock, hence the AO4407A;
     - no panel USB-C to micro-USB lead was found (£8 est.).
     - Confirm all of these before #40.
  3. **Firmware and host:**
     - nRF21540 LNA on, with the RSSI bypass above;
     - config.txt: `enable_uart=1`, `dtoverlay=uart3,uart4,uart5`, `spi1-2cs`, and two SC16IS75x overlays (IRQ 24/25, xtal 14745600); drop `console=serial0` from cmdline.txt, since UART0 is slot 0;
     - the host drives the SC16IS752 GPIOs as open drain (never output-high).
     - Slot k = UART map `SLOT_UART` in `backplane.py`.
  4. Layout (#34):
     - the Wilkinson junctions and resistor pads (0.5 dB allowed);
     - the two trees kept apart;
     - QPL9057 input match (S11 −7.5 dB at 2.4 GHz unmatched; R 0 Ω pad left for tuning);
     - the CM4IO and SC16IS752 clocks kept away from the LNAs.
     - Then VNA-measure IL and isolation in Phase 4/5.
  5. Mechanical: check the 1U fit of the CM4IO beside the main board, ADR-0014 item 6 (sub-board heights), and the LED light pipes to the front panel.
  6. Bias-T: 0.49 A is the TPS2595 minimum limit. An active antenna drawing more than ~0.4 A at 12 V is out of scope.
  7. The tan δ, the u.FL cable loss (1.0 dB) and the front-end loss (0.4 dB) are estimates; the VNA check in item 4 replaces them.
