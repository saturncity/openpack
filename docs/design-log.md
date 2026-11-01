# Design log

One entry per difficulty or consideration met while building a part of OpenPack. Each entry gives the problem and the options weighed, what was chosen and why (with links), the residual risk, and whether it needs a bench check. Decisions with a wider reach live in `docs/adr/`; this log keeps the reasoning behind the smaller ones.

## Rack layout (#34)

The rack main board (`hw/rack/layout.py` → `hw/rack/rack.kicad_pcb`) and its 1U chassis fit (`mech/rack.py`). Schematic: PR #95, ADR-0018. Review record: `hw/REVIEW.md`, rack section.

### 1. Board size and the case

- **Problem:** eight 48 × 90 mm receivers at the ADR-0014 52 mm pitch, two RF chains, a CM4 IO board and every rear-panel connector have to fit a 1U case. The owner fixed the case: Hammond RM1U1913SBK (330 mm deep).
- **Options:** (a) one board filling the case; (b) a narrow backplane strip with the host on its own tray and cables between them.
- **Chosen:** (a). The board is **412.0 × 323.0 mm**, 4 layers (JLC04161H-7628), and fills the 415.30 × 323.85 × 40.09 mm inside (Hammond drawing). Every panel connector is on the board, and the CM4 IO board sits on 10 mm spacers above it. No inter-board wiring except the 40-way ribbon and the 12 V pigtail.
- **Margins (`mech/out/rack_fit.json`):** {MARGINS}.
- **Risk:** a 0.133 m² 4-layer board is the dearest single PCB in the project (£40 est.). Get a JLC quote before ordering.
- **Bench:** fit the populated board into the case once; check the lid clears the receivers.

### 2. Routing a 412 × 323 mm board without Freerouting

- **Problem:** Freerouting is not available. The pack's grid router (`hw/pack/router.py`) rasterises at 0.1 mm, so a whole-board grid is 13 M cells per layer.
- **Chosen:** `hw/rack/wrouter.py` routes each connection in a window round the pad and the nearest connected copper (3/10/30 mm margins). The first pass still failed the longest host nets (about 270 mm from the CM4 header to the rear bias eFuses): A* ran out of its 900 k expansion budget on near-ties, not out of room. The budget now scales ×12 for windows longer than 150 mm.
- **Risk:** the run takes about an hour, and each placement change means a full re-run.
- **Bench:** none.

### 3. 50 Ω lines and the Wilkinson trees

- **Problem:** ADR-0018 needs a 1:8 Wilkinson per antenna on FR-4, ≤ 11 dB worst-port loss, ≥ 20 dB isolation, ≥ 15 dB return loss.
- **Chosen:** near-microstrip on L1 over the solid L2 plane, with a 0.5 mm gap to the L1 pour. Widths come from the 2D field solve in `hw/rx/rf_line.py`: 0.35 mm gives 50.2 Ω, 0.17 mm gives 70.3 Ω, and λ/4 = 18.02 mm. The gap is a DRC rule (`rack.kicad_dru`, "RF pour gap"), and the netclass clearances carry no 0.09 mm override (#116 review M1). `hw/rack/rf_routed.py` re-models the trees as drawn in scikit-rf: lines, bends, junctions, resistor parasitics, A's two vias, and ±10 % width × εr 4.2/4.6 corners.
- **As routed:** {WILK}.
- **Risk:** the FR-4 loss tangent (0.02) and the bend and junction models are estimates; the distribution lines are long because the ports have to sit behind each receiver.
- **Bench: yes.** VNA one tree, input to each port and port to port.

### 4. The LNA path at 50 Ω up to the pins

- **Problem:** the first pass used 0.25 mm (59.5 Ω by the field solve) into the QPL9057 and QPQ1907 pins, and its diagonal into LNA pin 7 grazed GND pin 6.
- **Chosen:** every through-line from the BNC to the BAW output is 0.35 mm. Each line enters its pin straight along the pin axis, which leaves 0.2 mm to the GND pins either side (RF clearance 0.15). Only the shunt-part stubs (ESD, choke, 18 nH) stay 0.25 mm; each is ≤ 1.5 mm, under λ/45.
- **As routed:** {FE}.
- **Risk:** small.
- **Bench:** covered by the VNA check in entry 3.

### 5. QPL9057 bias pin beside its RF input

- **Problem:** VBIAS (pin 1) sits 0.5 mm from RF_IN (pin 2), and the footprint does not mirror between chains A and B. The router keeps 0.5 mm from RF copper, so it could not leave pin 1. On chain B the bias resistor had been placed across the RF line from the pin.
- **Chosen:** a hand-drawn 0.25 mm stub from pin 1 to its 100 pF/1 µF cap beside the pin (`rf_frontend()`). On chain A the bias resistor shares the stub; on chain B the router joins the resistor to it on In2, under the L2 plane.
- **Risk:** none known.
- **Bench:** no.

### 6. Buck switch node

- **Problem:** the TPS62933's SOT-583 has SW, BST, SS and FB on one 0.5 mm-pitch side. A 1.5 mm SW track cannot leave pin 5, and it walled in the three small nets (BUCK_EN, BUCK_FB and BUCK_SS all failed).
- **Chosen:** SW is a small F.Cu pour (`BUCK_SW_ZONE`) from pin 5 to the inductor and the boot cap, as in TI's layout example (SLUSEA4D fig. 10-1). BST leaves pin 6 to the boot cap, SS climbs past pin 8 to its cap, FB goes straight up to the divider, and EN goes left with the 100 nF VIN cap at pins 3/4.
- **Risk:** the output caps sit 4–6 mm from the inductor, fed through the B.Cu +5V pocket.
- **Bench: yes.** Check 5 V ripple and the SW ringing at 3 A.

### 7. eFuse current-limit resistors

- **Problem:** the TPS2595 ILM pin (7) is on the far side of the package from where the schematic-led placement put its resistor. All eight +5 V slot eFuses, one +12 V slot eFuse and the input eFuse failed to route.
- **Chosen:** each ILM resistor sits just above-right of pin 7, pad 1 inboard, a 1 mm hop.
- **Risk:** none.
- **Bench:** no (the current limit itself is verified in #95's tests).

### 8. Parts swapped at layout (owner list, 2026-11-01)

- **39 nH bias-T choke, LCSC C142171 (Chilisin CS0603-39NJ):** its SRF is 2.2 GHz, below the band. Above SRF it looks like its 0.13 pF self-capacitance. With the SRF anywhere from 2.0 to 2.44 GHz, the choke is ≥ 1.2 kΩ at 2.44 GHz, which costs about 0.002 dB on a 50 Ω line; the far end is RF-grounded by 100 pF + 10 nF. It is rated 600 mA against the 0.52 A worst-case bias eFuse limit. Accepted. **Bench:** VNA S21 through the bias-T, part of entry 3's check.
- **Crystal, AKER C3E-14.7456-18-3030-R (LCSC C6523919), ESR 100 Ω, −20…+70 °C:**
  - Pierce start-up needs gm_crit = 4·ESR·ω²·(C0 + CL)² = **0.99 mA/V** (CL 14 pF from 2 × 22 pF + 3 pF stray; C0 3 pF est.).
  - A 3.3 V unbuffered CMOS stage gives about 8 mA/V (est.; NXP publishes none for the SC16IS752), so the margin is about **8×** against the usual 5×.
  - The load mismatch (14 vs 18 pF) pulls it by about +28 ppm, harmless for a UART. The temperature range covers a wing.
  - **Bench: yes.** It must still start with 500 Ω in series (5 × ESR).
- **6.8 µH inductor:** Bourns SRP5030T-6R8M (Irms 4.0 A, Isat 4.3 A, DCR 76 mΩ, Bourns datasheet), bought in the UK and consigned. LCSC's C177249 is only 3.5 A, and the buck peaks at about 3.4 A at 3 A out.
- **Fuse, LCSC C27515:** this is Littelfuse 0451004.MRL in the 2410 case (6.1 × 2.5 mm, LCSC record). Main's footprint name `Fuse_Littelfuse_NANO2_451_453` did not exist. The board uses KiCad's `Fuse_Littelfuse-NANO2-451_453`, the 2410 land (1.96 × 3.15 mm pads, 4.91 mm centres), not an 1808.
- **The other codes are in `hw/rack/outputs_rack.py`:** C85833, C160315, C5154126, C125113/4, C88373, C9138, C64320 (keyed: contact 14 pulled, no hole at 14), C361616. The BNC (TE 5415025-1 or Molex 73138-5033) and the PJ-063AH jack come from UK distributors.

### 9. Wing coax: one CA3N030 per wing does not reach the far wing

- **Problem:** the brief priced one L-com CA3N030 (30 ft, 9.14 m) per wing. Audit 5 routes the cables from the rack in one wing along the floor, across the stage at grid height and up each 4 m boom (ADR-0021).
  - The far wing needs **15.2 m (6 m stage), 18.3 m (9 m), 21.5 m (12 m)** with 5 % slack and 1 m dressing.
  - Even the smallest venue needs 13.6 m (6 × 6 m stage). With the rack at centre-front, each wing still needs 9.9–14.7 m.
- **Options:** two CA3N030 (does not reach); CA3N030 + CA3N050 (stages ≤ 6 m wide only); CA3N030 + CA3N075 (every venue in ADR-0021).
- **Chosen:** CA3N030 near + **CA3N075 far** (£88.02, +£42.22 against the brief). The far run is 22.86 m × 0.223 dB/m + 0.3 dB HG2409P lead + 0.1 dB adapter + 3 × 0.15 dB mated pairs = **5.95 dB**, inside the RK-2 6 dB budget. The near run is 2.89 dB.
- **N socket to BNC plug adapter (RS 285-6398, £8.40) instead of the LCCA30301-FT1.5 lead (£37.09):** £28.69 less per wing, one mated pair fewer, 0.1 dB.
- **Risk:** a venue wider than 12 m, or a rack sited further away, needs the 100 ft lead, which overruns RK-2 by 0.9 dB.
- **Bench / site:** measure the two runs at the first venue.

### 10. 100 mm u.FL jumpers and the PIMD distance

- **Problem:** the 100 mm Taoglas CAB.6012 jumpers (3.1 dB/m) lose about 0.5 dB less than the 200 mm leads. Third-order IMD rises 3 dB for every 1 dB of drive, so the radio's PIMD margin with a pack on axis drops by about 1 dB.
- **Chosen:** keep the short jumpers (cheaper, lower NF). PIMD now holds from **1.6 m on axis** (Audit 6) instead of 1.5 m; `tests/test_rack_rf.py` asserts 2 m. ADR-0021's install rule keeps packs off axis anyway (headroom +12 dB).
- **Risk:** an actor standing on axis within 1.6 m of a boom antenna.
- **Bench:** no; covered by the twin.

### 11. Rear panel: the USB-C service port

- **Problem:** the Adafruit 4056 panel lead (The Pi Hut 103462) is 28 mm across its ears. Mounted flat it would hit XLR 1 and XLR 2.
- **Chosen:** mount it upright between them, using the Premier Cable drawing C12984-001 (Adafruit product files): flange 28 × 8.5 mm, M3 × 12 screws 20 mm apart, 13 × 13 mm overmold running 40.5 mm back. The cut-out is a 4.0 × 9.6 mm slot (Type-C shell 8.94 × 3.26 mm + 0.35 mm a side, R2 ends) plus two 3.2 mm holes at ±10 mm, centred 21 mm above the case floor. `mech/rack.py` models the flange and the overmold.
- **Risk:** the drawing gives no flange thickness (4.5 mm est.).
- **Bench:** dry-fit before drilling.

### 12. Cost

- **Rack total {TOTAL} ex VAT** (UK VAT 20 % on top, so {TOTAL_VAT} inc VAT):
  - main board, host and cables {MAIN};
  - eight receivers {RX8};
  - antennas, coax and adapters {ANT};
  - two Thor LS003 stands and two HGX-PMT07 mast kits £310.56.
- **Against the £800–830 target:** like for like with the earlier £953.92 (no stands), the rack is **{LIKE}**, over the target. The case (£140.76) and the CM4 (£79.20) are fixed by the owner. The far-wing coax (entry 9) adds £42.22.
- **Risk:** 16 lines are still class estimates (£84 of the main board).
- **Bench:** no.
