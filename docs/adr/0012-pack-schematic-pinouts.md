# ADR-0012: Pack schematic: Sennheiser SK jack pinout, BT40NE pad map, front-end protection, cell cutoff
Status: accepted. 2026-10-31. Issue #31, PR #75 (amended after review). Schematic: `hw/pack/pack.py` (SKiDL), BOM `hw/pack/out/bom.csv`.
- **Context:** PK-1 asked to confirm the Sennheiser SK pinout in Phase 4. The #31 review asked for an RC-filtered mic-bias rail. ADR-0007 left the BT40NE pinout unverified. Sources:
  - Sennheiser *ew 100 G4 instruction manual*, "Pin assignment", p. 137. 3.5 mm mic plug: **tip = Mic+, ring and sleeve = ground**. Line plug: ring = Line+, tip and sleeve = ground.
  - Fanstel *BT40/F/E/N/NE Product Specifications* v1.08, Pin Functions. BT40N/NE use the BT40F pads; 9 pads drive the internal nRF21540.
  - TI PCM1840 SBAS989: 2.5 kΩ per input pin, 2 Vrms *differential* full scale, IOVDD 3.0–3.6 V, MSZ/FMT/MD pin modes.
  - TI OPA1656 SBOS901: input common-mode range (V−) to (V+) − 2.25 V, output swing within 0.25 V of the rails, input current ≤ 10 mA.
  - DPA's own adapter datasheet was not reachable. Dealers list the **DAD6034** (MicroDot → locking 3.5 mm) as made for Sennheiser ew "audio and plug-in power".
- **Decision:**
  - **Jack and bias.** J1 tip = MIC (5 V via 2.2 kΩ, R5); ring and sleeve = GND. Line plugs are not supported in v1 (R6 is mics only). Mic bias = **+5V_BIAS: boost 5 V through 100 Ω + 47 µF** (fc 34 Hz). Jack = Same Sky SJ1-3543 (M6 threaded bushing); fallback Switchcraft 35RAPC3BH3.
  - **Front end.** Tip ESD diode TPD1E10B06 and a 22 pF C0G shunt. Hot plug shorts the tip and kicks PRE_NP below ground: BAV199 (low leakage) clamps PRE_NP to the rails, and 100 Ω (R20) feeds both op-amp + inputs. Op-amp bias **VCM = 180k/100k → 1.77 V**, which keeps +IN at 1.19–2.36 V at 0.6 Vrms (CM limit 2.70 V).
  - **BT40NE pad map.**
    - Power: VDD (pad 9) = VDDH (F4, own 100 nF) = 3.3 V LDO (nRF5340 normal-voltage mode).
    - USB D+/D−/VBUS on E4/E5/F6; SWD on 14–16.
    - I2S BCLK/FSYNC/SDIN on C3/C4/C5 (P0.24/P0.23/P0.20); ADC SHDNZ on D5 (P0.22).
    - Cell sense AIN0 (pad 5), tapped at the cell. LEDs on Z0–Z3 (P1.09–P1.12). UART test pads B1/C1.
    - FEM pads Z6 A6 C2 C6 D1 D2 E0 E1 E2 are no-connect. Firmware's `nordic,nrf21540-fem` node must use: SCK P1.15, MOSI P1.08, MISO P0.25, CSN P1.06, TX_EN P0.21, RX_EN P0.27, PDN P0.26, MODE P1.04, ANT_SEL P1.05.
  - **PCM1840.** I2S slave (MSZ=0, FMT1=FMT0=1); low-latency filter (MD0=1, R3); DRE on (MD1=1). Path 1 (×2) on IN1, path 2 (×1, Q7) on IN2, INxM AC-grounded.
  - **Power.** BAT+ goes through a 3 A chip fuse (Bourns SF-1206F300, 23 mΩ, about 5 mV drop) in case someone fits an unprotected cell. A 0.5 A PTC (~1 Ω) was rejected: it costs about 0.2 V of 3.3 V headroom. Firmware **shuts down below 3.3 V cell, measured under load** (amended 2026-11-01, #34/#104: was 3.2 V). Derivation in `audit.py`: IOVDD 3.0 V + LDO 67 mV + path 54 mV (the cell path now includes the cradle spring estimate and the battery tracks measured from the layout, 121 mΩ) + ADC error 80 mV = 3.201 V, rounded up to 3.3 V. Runtime at 3.3 V (85 % of the cell usable) is asserted against PK-7 in `audit.py`. No buck-boost.
  - **LEDs.** Lite-On LTST-C191K*KT AlInGaP parts (Vf ~2.0 V) with 1 kΩ, about 1 mA each. **PK-8 thresholds:**
    - The single-ended pin swings at most about VREF/2 = 1.375 V peak, i.e. −6.3 dBFS of the 2.83 V-peak differential full scale. The PK-2 max (0.6 Vrms) reads −7.7 dBFS on path 1.
    - So amber "peak" at ≥ −10 dBFS and red "clip" at ≥ −7 dBFS. Red means past the design maximum, within 0.7 dB of the analog clip.
- **Numbers (`tests/test_spice_preamp.py`, ngspice in CI with `-rP` printing them; independent MNA cross-check):**
  - Noise: **0.967 µV A-wtd** in ngspice (MNA cross-check 0.961; 0.94 before R20).
  - 5 V rail → preamp output: −33.6 dB at 1 kHz; asserted ≤ −30 dB.
  - ADC pin: 1.17 V peak, below 1.375 V. Op-amp +IN: 1.21–2.37 V (asserted 0.2–2.50 V).
  - OPA1656 +IN: ≤ 2.50 V, asserted.
  - BOM: **$34.98** at qty 100 excluding the cell, with BT40NE at Fanstel direct ($13.47). It is $38.27 at the Digi-Key module price; `audit.py` prints both. PCB assembly and conformal coating are excluded.
- **Consequences / Phase 4 signoff items:**
  1. Fit a real Sennheiser plug (spare 099112) and a DPA DAD6034 to the SJ1-3543 thread. If they don't lock, swap to the Switchcraft (+$1.68, which would exceed $35 at the current margin: re-check then).
  2. Confirm from the EV-BT40NE schematic that the nRF21540 runs from module VDD, and which ANT_SEL level routes to the u.FL. Bond the whip pigtail shield to PCB ground.
  3. The X8WBT40N grant is still unverified (ADR-0007).
  4. The single-ended swing limit is inferred: confirm on the bench.
  5. TPS61023 PFM ripple can reach the audio band. The RC filter alone gives −29 dB at 1 kHz but only −10 dB at 100 Hz: bench-check it.
  6. THD of the X7R audio coupling caps: bench-check it.
  7. Battery holder: confirm the MYOUNG BH-18650-B1BA002 contact span takes 68–70 mm button-top protected cells; else use a Keystone 1043-class holder (about +$3, over $35).
  8. Custom footprints, plus the USB4105 paired-pad numbering (A1/B12 …).
  9. The 10 µF ADC coupling caps settle in about 0.1 s after SHDNZ release (PK-13 still fine): expect a thump on the first frames.
- **Requirements check:**

| R-id | Result | Basis |
|---|---|---|
| R6 | ✓ | Pinout from the manual; 5 V/2.2 kΩ bias; DPA via DAD6034, bench-unverified |
| R5 | ✓ | 0.967 µV; rail filtered |
| R2 | ✓ | No clip at 0.6 Vrms in op-amp CM, output swing, or ADC pin |
| R12 | ✓ | $34.98 (Fanstel price) |
| R7 | ✓ | Removable protected 18650, reverse FET, no charger |
| R8 | ✓ | 17.5 h with the 3.3 V cutoff (amended 2026-11-01; was 18.6 h at 3.2 V) |
| R4 | ✓ | Recessed switch only |
| R14 | ✓ | LEDs |

Rejected: a TPS63802 buck-boost for full-discharge 3.3 V. It meets the same rows, costs ~$1, and breaks $35.
