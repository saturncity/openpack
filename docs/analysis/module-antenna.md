# Does the BT40NE drive its u.FL through the nRF21540?

#105, part of #6. 2026-11-01. Triggered by the pack layout PR #104 (`hw/REVIEW.md` open item 2), which quotes Fanstel spec v1.09 p.22: *"The nRF21540 in BT40X is hardware-wired to the PCB trace antenna. ANT-SEL pin is not used."* Numbers come from `python3 audit.py` on main `e483a35`. This note recommends; it changes no ADR and no `hw/**` file.

**Answer: yes.** On the BT40NE the nRF21540 PA/LNA feeds both the PCB antenna and the u.FL. The module selects between them with the nRF21540's ANT_SEL, wired internally to nRF5340 P1.05 (module pad E1). The p.22 sentence describes the **BT40X**, Fanstel's 2020 name for the PA + PCB-antenna-only module that is now the **BT40N**. The FCC grant X8WBT40N certifies the BT40NE with a 6 dBi dipole on the external port at full PA power. That configuration is only possible if the u.FL sits behind the FEM. **No module change is needed on the pack or the receiver.** One firmware/bench item remains: drive ANT_SEL to the u.FL level. Which level that is still has to be confirmed (§4).

## 1. Evidence

### 1.1 The "BT40X" sentence is about the PCB-only part

- The Fanstel *BLE 5.1, 802.15.4 Modules, BT40/F/E/X/XE*, Draft v0.51, Aug 2020, pp.4–5 [S2] defines two parts:
  - **BT40X** = nRF5340 + nRF21540 + "Integrated PCB trace antenna", 15×28 mm;
  - **BT40XE** = nRF5340 + nRF21540 + "An u.FL connector for external antenna".

  Its p.17 nRF21540 section reads "BT40X uses nRF21540 power amplifier. Control codes to be provided."
- The current spec, *BT40/F/E/N/NE* v1.09, July 2024 [S1], renames the family to BT40N / BT40NE (15×29.9 mm), with the same SoC + FEM and the same pad map. Two leftovers keep the old name:
  - p.22: "The nRF21540 in BT40X is hardware-wired to the PCB trace antenna";
  - p.25: "This EV board can also be used for BT40, BT40E, and BT40X modules". The draft's version of that line read "BT40X, and BT40XE".

  Fanstel's nRF52840 family uses the same suffixes (BT840X = PA + PCB antenna, BT840XE = PA + u.FL), and the v1.09 pin table still cites them ("NC for BT840X/XE").
- So "BT40X" in the sentence = BT40N. That reading is an inference from the naming. §1.2 settles the question independently of it.

### 1.2 The FCC filing certifies the BT40NE's external port at full PA power

FCC ID **X8WBT40N** [S4]:

| Item | Value | Source |
|---|---|---|
| Grant | 2023-05-23, TCB Kiwa, DTS 15C, **Single Modular Approval**, 2402–2480 MHz, **0.082 W conducted** (19.1 dBm) | grant |
| Models | Main BT40N, series **BT40NE**, "Model Difference: Antenna" | Test Report_BLE ISL-23LR0019FCBLE p.6 [S5] |
| Antenna 1 | **Dipole, Fanstel ANT060, 6 dBi**, 2400–2485 MHz. Spec sheet: YH-2.4G-SMA-J195, ≤ 6 dBi, omni, SMA-J | [S5] p.6, Dipole Ant Spec [S6] |
| Antenna 2 | PCB ("F type"), **0.88 dBi** peak (0.41 / 0.18 / 0.88 dBi at 2400 / 2450 / 2500 MHz) | [S5] p.6, antenna report ISL-23LR0019ANT "ANT_BT40NF" [S7] |
| Conducted power | 19.137 / 17.63 / 18.386 dBm at 2402 / 2442 / 2480 MHz, nRF5340 at 0 dBm into the PA | [S5] §6.3 |
| MPE | Dipole EIRP 27.1 dBm, PCB ("PIFA") 22.0 dBm (19.137 dBm conducted + gain + 2 dB tune-up), **at 20 cm** | RF Exposure ISL-23LR0019FMPE [S8] |
| Grant condition | "…installed to provide a separation distance of at least 20 cm from all persons…" | grant |
| Modular letter | "External Antenna with unique non standard antenna port, PCB and Dipole Antenna" | [S9] |

The BT40N has no connector, so the 6 dBi dipole can only attach to the BT40NE's u.FL. The report measures 19.1 dBm conducted, the MPE exhibit adds the dipole's 6 dBi to that full PA output, and Fanstel's own "+25.1 dBm radiated" for the BT40NE [S1 p.1, S3] is the same sum (19.1 + 6). The BT40N's "+20.0 dBm radiated" is 19.1 + 0.88 dBi. **The u.FL is on the FEM side.**

Supporting evidence in [S1]:
- The pin table (pp.16–19) wires P1.05 to nRF21540 ANT-SEL, and the devicetree sample (p.22) includes `ant-sel-gpios = <&gpio1 05 …>`.
- The nRF21540 has two antenna ports, ANT1 and ANT2. ANT_SEL = 0 selects ANT1 and 1 selects ANT2 in RX/TX, and both are isolated in power-down [S10].
- On the BT40N "ANT-SEL pin is not used", because only one port is wired. The BT40NE uses the second port for the u.FL.

### 1.3 Variants

Prices are qty 100 unless stated. "Fanstel" = fanstel.com [S3]. Digi-Key UK pages were read 2026-11-01 [S11].

| Variant | Antenna / connector | nRF21540 in path to that connector | Max TX (conducted / radiated, FCC) | RX sensitivity | Certified antennas | UK availability, price |
|---|---|---|---|---|---|---|
| BT40F | PCB trace | no FEM | +3.4 / +4.3 dBm | −98 dBm @1M (nRF5340) [S1 p.1] | X8WBT40F, PCB | Fanstel $9.92 |
| BT40 | PCB trace | no FEM | +3.4 / 0 dBm | −98 dBm @1M | X8WBT40F, PCB | Fanstel $7.88 (1–999) |
| BT40E | **u.FL only** | no FEM | +3.4 / +9.4 dBm (ANT060) | −97.5 dBm (Digi-Key) | X8WBT40F; "certified with ANT060, a 6 dBi antenna, in all regions" [S1 p.1] | Fanstel $9.55; **Digi-Key UK £9.78, 803 in stock, 10 wk** |
| BT40N (ex BT40X) | PCB trace only | **yes, hard-wired** to the PCB antenna; ANT_SEL unused [S1 p.22] | +19.1 / +20.0 dBm | not stated (nRF5340 + 13 dB FEM LNA) | X8WBT40N, PCB 0.88 dBi | Fanstel from $13.10, $11.49 @1K; no Digi-Key UK page found |
| **BT40NE** (ex BT40XE) | PCB trace **+ u.FL** | **yes, to both**; port chosen by ANT_SEL (P1.05) | +19.1 / **+25.1 dBm** (ANT060) | not stated (as BT40N) | X8WBT40N, **ANT060 6 dBi dipole** and PCB 0.88 dBi (FCC/ISED). CE/RCM/TELEC tested with **ANT000, 0 dBi**, nRF5340 at −6 dBm [S1 p.21] | Fanstel $13.47 (#31), $12.24 @1K; **Digi-Key UK £12.52, 624 in stock, 10 wk** (£16.34 @1) |
| BT40NF | not a product | — | — | — | Appears only as the title of the FCC PCB-antenna report "ANT_BT40NF" [S7] | none |
| "U" / u.FL variants | none in the BT40 family | — | — | — | Fanstel's u.FL suffix is **E** (BT40E, BT40NE) | — |

Neither Fanstel's site nor a web search turned up a Fanstel EU DoC or UKCA declaration for any BT40 variant. The product page says only "Europe: Compliant" [S3].

## 2. The three questions

1. **Does the pack module drive an external antenna through the FEM?** Yes. With ANT_SEL at the u.FL level, the PK-5 whip gets the full nRF21540 output. ADR-0012 item 2 ("which ANT_SEL level routes to the u.FL") is the only open part.
2. **If not, which does?** Not needed. For the record, the BT40NE is the only BT40 variant with the FEM in the external-port path. ADR-0007's fallback, "BT40N fitted with an external u.FL pad", **is not viable**: the BT40N's FEM is hard-wired to the PCB trace and the module has no RF pad.
3. **Does the receiver sub-board have the same issue?** No. `hw/rx/rx.py` feeds PE4259 RFC → J5 u.FL → 50 mm U.FL jumper → BT40NE u.FL. That path goes through the module's nRF21540 LNA, as `audit.py` Audit 3 assumes (13 dB / NF 2.7, system NF 8.6 dB). Two receiver notes:
   - Module-internal P1.05 must select the u.FL here too.
   - The board's own net named `ANT_SEL` (pad D6, P1.01, PE4259 CTRL) is a different signal. Renaming it, e.g. `RX_ANT_AB`, would avoid confusion in a later hw PR.

## 3. Link budget, pins, BOM

**Link budget (audit.py terms): no change.** The pack keeps `WHIP_DBI = 2`:
- UK: 7 dBm conducted + 2 dBi = 9 dBm EIRP. Indoor n=3 range 35 m without the module LNA, 38 m with it.
- US: 18 dBm conducted + 2 dBi = 20 dBm EIRP. Range 82 / 87 m.

The receiver chain is unchanged. The 50 mm U.FL jumper (~0.5 dB, est.) ahead of the module LNA moves the system NF from 8.57 to 8.64 dB.

For scale, here is what the feared failure would have cost: the PA reaching only the PCB antenna (a BT40N, or ANT_SEL left on the wrong port). The regions limit EIRP, so on paper nothing moves:
- UK: 8.1 dBm conducted + 0.88 dBi = 9 dBm.
- US: 19.1 + 0.88 = 20.0 dBm, Fanstel's BT40N radiated figure.

The loss is body proximity. The 0.88 dBi was measured in free space [S7]. Inside a PETG pack on a belt, the trace antenna sits 1–2 cm from the body, next to the 18650. Assume (est., Phase 5 measures) 5–10 dB more loss than the whip's 10 dB `body_db`. With `link_range_m(…, body_db=15 / 20)`:

| `body_db` | UK n=3 (no module LNA) | UK free space | US n=3 |
|---|---|---|---|
| 10 (whip, current) | 35 m | 211 m | 82 m |
| 15 (PCB antenna, est. low) | 24 m | 119 m | 56 m |
| 20 (PCB antenna, est. high) | **16 m**, fails the 20 m assert | 67 m | 38 m |

Wrong-port ANT_SEL with the whip fitted is worse than any row here. The whip would see only the nRF21540's ANT1↔ANT2 isolation, which the PS states and we have not read, so the link would be lost entirely. That is why §4 item 1 is a gate.

**Pins and footprint: no change.** The BT40NE pad map in ADR-0012 / `hw/pack/symbols.py` already leaves the nine FEM pads (including E1 = P1.05 ANT_SEL) as no-connect. For reference only:
- BT40N: same footprint and pads, but no u.FL, so no whip.
- BT40E: different footprint (14×16 mm BT40 pads, not the 15×29.9 mm BT40F pads); the nine FEM pads become GPIO; no FEM.

**BOM: $0 delta.**
- Pack: $34.60 on current main (`audit.py` Audit 2), $0.40 under PK-12. The Digi-Key UK price (£12.52 ≈ $16.47 at the rx BOM's 0.76 rate) would put it at ~$37.6, over $35. `audit.py` already prints this at the US Digi-Key price ($37.89). Buying from Fanstel direct, or reaching the 1K break ($12.24), remains a PK-12 dependency.
- Receiver: $34.58/sub-board, no cap. An optional saving, unrelated to this finding, is already in ADR-0015: BT40E on the 8 rx modules saves £2.75/sub-board at Digi-Key UK (£22/rack). It costs a footprint change and the 0.7 dB module-LNA NF benefit.

## 4. Open items and certification

1. **ANT_SEL level (gate before Phase 5 RF tests).** Firmware has no `nordic,nrf21540-fem` node yet (`fw/` has no `ant-sel` entry). The node must carry `ant-sel-gpios = <&gpio1 5 …>` and select the u.FL on both boards.
   - Fanstel's sample flags it `GPIO_ACTIVE_HIGH` but does not say which port is which.
   - Ask Fanstel, or measure: conducted power at the u.FL with P1.05 low vs high.
   - A Nordic DevZone thread cites an erratum asking for ANT_SEL held low in power-down (not checked against the errata sheet); confirm the port is re-selected at wake.
2. **PCB antenna overhang (#104).** With the whip as the radiator, the 10.9 mm overhang and its keep-out are not needed for radiation. Keeping them preserves a firmware-only fallback to the PCB antenna. Their cost is board length only.
3. **FCC (US region).** The single modular grant covers only the 6 dBi ANT060 dipole and the 0.88 dBi PCB antenna, at ≥ 20 cm from persons.
   - Our 31 mm quarter-wave wire whip (~2 dBi) is lower gain but a different type (monopole). §15.204(c)(4) and KDB 996369 allow "same type, equal or lower gain" without a new filing, so the whip is arguably not covered.
   - A body-worn pack also breaks the 20 cm condition. The FCC SAR-based exemption, §1.1307(b)(3)(i)(B) at 2.44 GHz, is 2.8 mW at 0.5 cm, 10 mW at 1 cm and 38 mW at 2 cm. At 20 dBm EIRP (ERP ≈ 61 mW, ≈ 26 mW time-averaged at 42.4 % duty), the whip needs to be ≳ 2 cm from the body to be exempt.
   - Shipping the US region needs a Class II permissive change by Fanstel (whip + portable exposure) or an OpenPack change-in-ID filing. That is a cost and schedule item for the US only.
4. **UK (default region).** There is no modular-grant concept. OpenPack, as manufacturer, issues the UK Declaration of Conformity under the Radio Equipment Regulations 2017 for the finished pack with its whip. It covers:
   - EN 300 328 V2.2.2 radiated at the declared 9 dBm EIRP;
   - EN 301 489-1/-17;
   - EN 62368-1;
   - RF exposure by EN 62479, since 7.9 mW EIRP is below its 20 mW low-power exclusion.

   Fanstel's CE test used a 0 dBi antenna at a different power setting, so its report supports the module's parts of the file but not our antenna. Ask Fanstel for the EN 300 328 report and DoC; none is published.

## Recommendation

- **Keep the BT40NE on both boards.** The whip (PK-5), the ADR-0012 pigtail, R10 and the `audit.py` link budget stand as designed.
- **Amend ADR-0007 (separate PR):** delete the "BT40N + external u.FL pad" fallback, and record X8WBT40N's antenna list and its 20 cm / US-only re-filing need.
- **Close ADR-0012 item 2** once ANT_SEL polarity is confirmed with Fanstel or on the bench, and put `ant-sel-gpios` in the FEM devicetree node for pack and rx.

## Sources

- [S1] Fanstel, *BLE 5.3, 802.15.4 Modules, BT40/F/E/N/NE Product Specifications*, Ver 1.09, July 2024. Model Summaries p.1, block diagrams pp.4–5, Pin Functions pp.16–19, "Settings for Certification Testings" p.21, "Control Nordic nRF21540 Power Amplifier" p.22, p.25. https://fanstel.squarespace.com/s/BT40F_BT40N-Product-Specifications.pdf
- [S2] Fanstel, *BLE 5.1, 802.15.4 Modules, BT40/F/E/X/XE*, Draft Ver 0.51, Aug 2020, pp.4–5, 17, 18. https://media.digikey.com/pdf/Data%20Sheets/Fanstel%20PDFs/BT40_F_E_X_XE_Draft_V0.51_Aug2020.pdf
- [S3] Fanstel product pages, read 2026-11-01: https://www.fanstel.com/bt40f-nrf5340 and https://www.fanstel.com/buy1/bt40n-nrf5340-ble-53-module-with-nrf21540-power-amplifier-jghg7
- [S4] FCC ID X8WBT40N, grant and exhibit list: https://fccid.io/X8WBT40N (mirror of FCC EAS; apps.fcc.gov refused direct access)
- [S5] Test Report_BLE, ISL-23LR0019FCBLE, §1.1 and §6.3: https://fccid.io/X8WBT40N/Test-Report/Test-Report-BLE-6540301
- [S6] Dipole Ant Spec (YH-2.4G-SMA-J195): https://fccid.io/X8WBT40N/Test-Report/Dipole-Ant-Spec-6540307
- [S7] Antenna test report ISL-23LR0019ANT ("ANT_BT40NF"), PCB antenna gain: https://fccid.io/X8WBT40N/Test-Report/ISL-23LR0019-ANT-BT40NF-report-6540310
- [S8] RF Exposure, ISL-23LR0019FMPE §3: https://fccid.io/X8WBT40N/RF-Exposure-Info/RF-Exposure-Info-6540303
- [S9] Modular Approval Request (KDB 996369 D01 / §15.212), item 4: https://fccid.io/X8WBT40N/Letter/Modular-Approval-Request-6540246
- [S10] Nordic, nRF21540 Product Specification, "Antenna control" (ANT_SEL truth table) and pin assignments (ANT1 pin 2, ANT2 pin 3, ANT_SEL pin 8): https://docs.nordicsemi.com/r/bundle/ps_nrf21540/page/chapters/device_control/doc/antenna_control.html (content read via search index; the page refused direct fetch)
- [S11] Digi-Key UK, read 2026-11-01: BT40NE https://www.digikey.co.uk/en/products/detail/fanstel-corp/BT40NE/22107427, BT40E https://www.digikey.co.uk/en/products/detail/fanstel-corp/BT40E/13174285
- 47 CFR §1.1307(b)(3)(i)(B) (SAR-based exemption), §15.204(c)(4), §15.212; FCC KDB 996369 (modular transmitters). EN 62479:2010 (low-power RF exposure exclusion).
