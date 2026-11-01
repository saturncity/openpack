# ADR-0018: Rack main board: LNA + BAW filter + 1:8 Wilkinson per antenna, fused slots, CM4 IO board as the host carrier
Status: accepted. 2026-11-01, amended after the #95 review, the owner's wing-antenna constraint and ADR-0021 (gain plan, BT40E receivers). Issue #33. Schematic `hw/rack/backplane.py` (SKiDL, ERC 0/0). Splitter model `hw/rack/wilkinson.py`. Numbers `python3 audit.py` Audit 6. Tests `tests/test_backplane_sch.py`, `tests/test_rack_rf.py`.
- **Context:** RK-1..RK-3 fix the rear panel, the RF chain (LNA NF ≤ 2 dB, input P1dB ≥ −10 dBm, IIP3 ≥ 0 dBm, then a 1:8 splitter, with a 6 dB coax budget) and a CM4 host. ADR-0014 fixes the slot connector (key at 14). ADR-0016 fixes the antennas and the R1 margin. **New owner constraint (2026-11-01): the panels go in the wings**, so actors walk past them and the worst near pack is ~0.5 m from an 8 dBi panel (UK 9 dBm EIRP).
- **Sources:**
  - Qorvo QPL9057 Rev. F: pins, EVB, |S21| table, spec table. The spec table is tested at 3.5 GHz only, so its values serve here as a worst-case proxy.
  - Qorvo **QPQ1907 Data Sheet 040820**: pins **1 IN, 2/3/5 GND, 4 OUT**; IL by Wi-Fi channel over 2402.5–2481.5 MHz; attenuation table.
  - **nRF21540 OPS v0.5.2**: RX P1dB −18.0 dBm minimum. Nordic's 2022 nRF21540 webinar: "no bypass mode support".
  - **nRF5340 PS v1.1** §7.26.16.5–7: PRX,MAX 0 dBm; C/I 2M BLE ±4 MHz −22/−47 dB, ≥ 6 MHz −54 dB; PIMD,2M,BLE −22 dBm. The PS gives no out-of-band blocking figure.
  - TI TPS2595 SLVSE57C; TI TPS62933 SLUSEA4D; NXP SC16IS752 Rev. 9.1; Infineon ESD101-B1; Raspberry Pi CM4 and CM4IO datasheets; pSemi PE4259.
  - DigiKey UK and The Pi Hut pages, read 2026-11-01.
- **Decision:**
  - **RF, per antenna.** The chain is:
    1. BNC (TE 5415025-1 since #34; was Amphenol 112487) → ESD103 (±15 V, 0.09 pF);
    2. bias-T: 39 nH choke (#34: Chilisin CS0603-39NJ, LCSC C142171, SRF 2.2 GHz, still > 1 kΩ shunt in band; was LQW18AN), 100 pF + 10 nF, **1 Ω 2512 (1 W)**, SMF12A;
    3. TPS259541 bias eFuse: 0.46–0.52 A, off by default, EN and FLT on host GPIOs;
    4. 100 pF DC block → ESD101 → **QPL9057** (EVB values) → **QPQ1907 BAW** → 3-stage microstrip Wilkinson → 8 u.FL.
    - The 1 Ω 2512 dissipates 0.27 W at the worst-case limit, 27 % of its rating; the test asserts ≤ 50 %.
    - The QPQ1907 pinout is now the datasheet's. A test walks the RF path through series elements only, from BNC to every slot port.
  - **Filter choice.** No UK-stocked 2.4 GHz filter was found that specifies IL over all of 2400–2483.5 MHz *and* rejection over 2370–2400 MHz:
    - The Qorvo QPQ1907 and 885128 and the Akoustis A10424 specify IL only over 2402.5–2481.5 and rejection only over 2300–2370.
    - The Broadcom ACPF-7A24 specifies IL over 2401–2480 (≤ 2.9 dB), ≥ 35 dB over 2300–2370 and 25 dB typical over 2370–2380, but no UK distributor lists it.
    - The QPQ1907 stays: DigiKey UK, £2.82, 7,548 in stock. Audit 6 charges the 2403 and 2482 carriers 2.2 dB plus a 2 dB skirt allowance (estimate, S2P not read) and credits 0 dB of rejection at 2370–2400.
  - **Power:**
    - **4 A fast fuse (0451004.MRL) ahead of** the reverse-polarity P-FET and the SMBJ12A. A 15–24 V brick then opens the fuse, rather than failing the TVS or putting 24 V on the TPS2595.
    - Then the TPS259541 input eFuse (3.5 A, UVLO 9.98/9.15 V), TPS62933 5 V, TLV76733 3.3 V, per-slot TPS259541 (+12 V) and TPS259531 (+5 V) at 0.49 A, and a 1.5 A CM4IO feed.
    - The NT1 tie and the BNC bulkhead bodies both bond GND to the panel.
  - **Slots:**
    - **Harwin M20-7831346** socket with a **Harwin M20-003 polarising key in position 14** (8 per rack in the BOM).
    - Slot-ID straps, LEDs (Lite-On LTST-C191KGKT and KRKT, 560 Ω), XLR NC3MAH with SMAJ58CA on pins 2/3.
  - **Host:**
    - **CM4002008 (SC0680, no wireless) from The Pi Hut UK, £79.20, qty 1.** SC0681 (16 GB) at the same price is the drop-in alternative. DigiKey UK had 0 in stock.
    - The official CM4IO (SC0326) on a 40-way ribbon.
    - CM4 UART0/3/4/5 for slots 0–3, plus two SC16IS752 on SPI1 for slots 4–7. Their GPIOs drive nRESET/BOOT as software open drain.
    - Ethernet through an etherCON NE8FDP; USB-C service through a lead to the CM4IO rpiboot port.
  - **CI:** scikit-rf is installed, and the cross-check fails rather than skips under `CI`. `backplane.py --no-sch` is re-run and the symbol library, netlist (build timestamp stripped), BOM and ERC report must not change.
- **Numbers** (Audit 6, worst-case limits):
  - **QPL9057 at 2442 MHz:** |S21| 23.1 dB (21.5 dB minimum proxy for NF), NF 0.48 typ / 0.90 max, IIP3 ≥ +5.9 dBm, input P1dB ≥ −7.6 dBm.
  - **Wilkinson:** 10.61 dB (scikit-rf 10.24), isolation ≥ 30.3 dB, RL 36/39 dB. It holds εr 4.2–4.6 and ±10 % etched width.
  - **System NF, receivers on the BT40E (ADR-0021), worst-case LNA:**
    - with the ADR-0016 coax (4.2 dB): 9.68 / 8.12 / 9.68 dB at 2403 / 2442 / 2482;
    - at the 6 dB budget: **11.48 / 9.92 / 11.48 dB**. The band edges include the 2 dB skirt estimate.
    - RK-5's limit is now the **wing need of 21.1 dB** (Audit 7: noise costs ≤ 0.5 dB of the R1 margin for the weakest wing pack), not Audit 4's 9.30 dB, which assumed a 10 m front-of-stage pack.
  - **Gain plan: no pad, BT40E** (ADR-0021).
    - Assumptions: near pack UK 9 dBm **on axis** (worst; the ADR-0021 rule keeps it off axis); Wi-Fi ×3 at 6 m in the beam.
    - Margins against P1dB − 6 dB, PRX,MAX − 6 dB and PIMD:

| near pack | QPL9057 in (margin) | radio total (margin) | PIMD margin | C/I margin ≥ 6 MHz / −4 MHz |
|---|---|---|---|---|
| 0.5 m | −16.7 (+3.1) | −8.3 (+2.3) | −18.9 | +8.0 / −24.0 |
| 1.0 m | −20.6 (+7.0) | −12.3 (+6.3) | −6.9 | +14.0 / −18.0 |
| 1.5 m | −22.0 (+8.4) | −13.8 (+7.8) | +0.2 | +17.6 / −14.4 |
| 4.0 m | −23.2 (+9.7) | −15.1 (+9.1) | +2.3 | +26.1 / −5.9 |

    - Nothing compresses even at 0.5 m on axis. PIMD holds from 1.5 m on axis, and under the rule (Audit 7: worst headroom +12.0 dB UK).
    - The BT40NE's nRF21540 would sit at −16.0 dB at 0.5 m, which is why it was dropped.
    - A class-3 phone (B40 at 2390 MHz, unfiltered ahead of the LNA) needs ≥ 2.7 m from a panel. ADR-0021's rule (crew phones in airplane mode in the wings) covers this.
    - The −4 MHz C/I is a channel-plan / R1 matter, covered by ADR-0021's bsim runs.
  - **BOM, GBP ex VAT:** main board, host and cables **£426.32** (£113.26 of it estimates); 8 sub-boards £210.80; antennas £340.56; **rack £977.68**.
- **Requirements check** (carrier and UART fan-out):

| R-id | CM4IO + ribbon, CM4 UARTs + 2× SC16IS752 (chosen) | CM4 on the main board | CM4IO + USB hub + 2× FT4232H | Pi 4/5 SBC |
|---|---|---|---|---|
| R1 | ✓ no-wireless CM4; audio runs without the host | ✓ | ✓ | partial: Wi-Fi off in software |
| R9 | ✓ 160 × 90 mm beside the main board | ✓ | ✓ | partial: cabling |
| R11 | ✓ GbE, every UART + reset + boot | ✓ | ✓ | ✓ |
| R13 | ✓ vendor board; SC16IS752 pins from its datasheet | partial: new Ethernet/power design | ✗ FT4232H datasheet unreadable (403) | ✓ |
| RK-3 | ✓ eMMC | ✓ | ✓ | partial: SD card |
| R12 | partial: +£26 board +£12 UARTs | ✓ | partial | partial |

- **Consequences / open items:**
  1. **Gain plan: resolved by ADR-0021.** The receivers move to the BT40E (no FEM) with no pad, and the panels go on 4 m wing booms. Every stage stays ≥ 6 dB under P1dB, and system NF is 11.5 dB against the 21.1 dB wing need. The pad and switched-pad options are dropped; none was built. #95's stop-and-ask is closed.
  2. QPQ1907: get the S2P to replace the 2 dB skirt estimate at 2403/2482 and the 0 dB credit at 2370–2400. The ACPF-7A24 would be the better filter if a UK source appears.
  3. The nRF21540 P1dB (2019 objective spec) only matters for the pack now: the receivers have no FEM.
  4. Firmware and host:
     - config.txt: `enable_uart=1`, then one `dtoverlay=` line each for uart3, uart4, uart5 and spi1-2cs;
     - SC16IS752 overlays for CE0 and CE1 (the stock `sc16is752-spi1` overlay covers one chip, so the second needs a custom overlay), `spi-max-frequency` ≤ 4 MHz, IRQ 24/25, xtal 14745600;
     - drop `console=serial0`.
  5. Layout (#34):
     - Take the Wilkinson widths from JLC's calculator with solder mask, or open the mask over the tree;
     - give the TL net-ties real track geometry;
     - check that the 200 mm u.FL cables reach slots 0 and 7;
     - the QPL9057 input match;
     - follow the QPQ1907 land pattern from the datasheet.
  6. Confirm that the M20-003 key seats in the M20-78 dual-row socket on the first unit (Harwin lists it for M20 female families).
  7. No panel USB-C to micro-USB lead was found (£8 estimate). TPS259541 has a 20-week lead time.
