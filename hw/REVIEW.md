# Layout image review (#34)

Process (docs/agents/hands-off.md, "PCB layout review"): `kicad-cli` renders every copper layer and the top and bottom views to PNG. An agent reviews the images against the checklist (decoupling, return paths, antenna keepout, boost loop area, connector positions against the enclosure), fixes the layout script and repeats until the checklist is clean. The fab's automated DFM runs at upload, which is an end-of-project step. One section per board.

## Pack board (`hw/pack`)

**Result: checklist clean. DRC 0 errors and 0 unconnected against the JLCPCB rules. Fit check passes.** Fab DFM upload is still to do (end of project).

| | |
|---|---|
| Board | 73.4 × 35.0 mm, 4 layers, 1.6 mm, ENIG, one corner notched for the lid post. All parts on top (single-sided assembly). 75 footprints, 358 tracks, 283 vias (206 GND) |
| Stackup | JLC04161H-7628: L1 signal + GND pour / 0.2104 mm 7628 (εr 4.4) / L2 solid GND / 1.065 mm core / L3 GND pour + power / 0.2104 mm / L4 signal + GND pour |
| Rules | `hw/pack/pack.kicad_dru` (JLC 4-layer minimums: 0.09 mm track and space, 0.15/0.25 mm via, 0.3 mm to edge). The router works to 0.15 mm clearance, 0.2 mm signal and 0.4 mm power tracks, and 0.6/0.3 mm vias, so DFM has margin |
| DRC | `kicad-cli pcb drc`: **0 errors, 0 unconnected**. 26 warnings, all cosmetic or justified: silk over copper or edge (22, refdes on dense parts) and starved thermal (4, see below) |
| Regenerate | `python3 hw/pack/layout.py` (system python with KiCad 10 `pcbnew`): netlist → placement → routing → pours → DRC → `out/fab` → `out/render` → `fit.py`. Each run takes about 80 s and is deterministic apart from UUIDs |
| Renders | `hw/pack/out/render/`: `L1_F.Cu` … `L4_B.Cu`, `top_assembly`, `3d_top`, `3d_bottom`, `fit_top`, `fit_side` |

### Checklist

| Item | Finding | Status |
|---|---|---|
| **Antenna keepout** | Fanstel BT40/F/E/N/NE v1.08 p.20 says the antenna area must extend 9.8 mm past the board edge (option 1). The BT40NE's antenna section (v = 19.0–29.9 mm, from the p.13 drawing) overhangs the x = −28 edge by **10.9 mm**, so the board has no copper under it on any layer. The overhang points at the left wall, away from the cell (≥ 16 mm in y), and rides 0.6 mm above the clip bosses. That is why the board is raised 1.4 mm (`mech/pack.py` z0 = 5.0). L1 is GND poured under the module, as p.21 asks, with no L1 tracks under it except the LGA fan-out stubs | ✓ |
| **RF / via fence** | A GND via fence at 1.5 mm pitch (≤ λ/20 in FR4 at 2.45 GHz) runs along the antenna edge and the module's top edge. A 3 mm perimeter fence plus 5 mm interior stitching ties L1/L3/L4 to L2 | ✓ |
| **50 Ω line** | Microstrip on L1 over L2 (h 0.2104 mm, εr 4.4, t 35 µm), Hammerstad–Jensen with Wheeler's thickness correction (`layout.py` `microstrip_z0`): **w = 0.346 mm → Z0 = 50.0 Ω, εeff 3.33**. Sensitivity is about ±3.7 Ω per ±0.05 mm, so 0.30 mm gives 53.7 Ω and 0.40 mm gives 46.3 Ω. Netclass rule `RF_50R` is in the .kicad_dru. **This board carries no RF trace.** The BT40NE's nRF21540 → u.FL path is inside the module, and the whip pigtail plugs into the module's own u.FL, so a carrier trace would only add a second connector. The width is recorded for the ADR-0007 fallback (BT40N + external u.FL pad) | ✓ (n/a on this board) |
| **nRF21540 path** | Internal to the module. Its nine control pads (Z6 A6 C2 C6 D1 D2 E0 E1 E2) are left unconnected, per ADR-0012 | ✓ |
| **Boost loop** | TPS61023 cell copied from TI SLVSF14B fig. 10-1. The inductor sits under the IC. SW leaves the pin between the pad columns and runs **3.5 mm** to L1. The output caps C2/C3 bridge VOUT↔GND right beside the pins, with their GND vias at the cap pads. The hot loop (C2 → VOUT → FET → GND → C2) is about 2.5 × 1.7 mm. The input cap C1 sits next to VIN with its own via. L2 is unbroken under the cell. SW is on L1 only | ✓ |
| **Analog separation** | Boost to ADC (U4→U2) is 14 mm. Boost to op-amp (U4→U3) is 28 mm. Boost to jack is 47 mm. A tagged analog region (x ≥ 8, y ≤ 11.5) is closed **on every layer** to the boost, battery, USB, LED, UART and SWD nets. Analog nets route on L1 only, over solid L2. The digital nets that end at U2 (I2S, SHDNZ) arrive on L4 and come up through three staggered vias at the QFN | ✓ |
| **Decoupling** | PCM1840: AVDD/AREG/VREF go to their 100 nF/1 µF/10 µF caps through straight "comb" stubs (≤ 2 mm), DREG and IOVDD through 0.5 mm doglegs. AVSS and MSZ tie straight into the exposed pad, which has its own via. OPA1656: 100 nF 2.2 mm from V+, 10 µF beside it, V− = GND pin with a via. BT40NE: C29 100 nF sits right above VDD pad 9 / VSS pad 10 (loop under 2 mm). C32 (VDDH, pad F4 is under the module) is 4 mm away through the F4 via, the closest possible spot outside the module. LDOs and U7 have their caps at the pins | ✓ |
| **Return paths** | L2 is solid apart from via antipads (`L2_In1.Cu.png`). Every SMD GND pad has its own via to L2 (`gnd_fanout`). Before the fix, long digital runs on L1 cut the L1 pour; they now go to L4 (layer costs), and L1 keeps a near-solid pour. L4 signals (USB pair, I2S, LEDs) reference L3, which is a GND pour crossed by a few power tracks. Where they cross, L2 is the reference 1.07 mm away. Accepted for FS USB, 3 MHz BCLK and LEDs | ✓ |
| **Connectors vs enclosure** | `hw/pack/fit.py` (box model, the CI gate) and `tests/mech/test_pack_fit.py` (CadQuery, STEP + per-part boxes) check this.<br>• **Jack J1:** Same Sky SJ1-354X datasheet (09/12/2024). Body front sits on the wall's inner face (x 46.4), so the 3.6 mm M6 bushing passes the 1.6 mm wall with 2.0 mm left for the nut. Axis z 11.8 = JACK_Z (5.2 mm above the board).<br>• **USB-C J2:** y 18 = USB_Y, shell 8.94 mm in a 9.6 mm opening, mouth z 8.2 = USB_Z.<br>• **Lid:** LED pairs sit under light-pipe chimneys at (8, 20) and (16, 20). The switch fork's stalk runs in a 4.6 × 2.3 mm slot, travel included.<br>• **Clearances:** the tallest part (jack, 9.6 mm) tops out 5.0 mm below the lid. THT legs clear the bosses and rests | ✓ |

### Fixes made during review (each found in the renders or DRC, then fixed in `layout.py`)

1. **Digital runs chopped the L1 pour.** The first pass put USB, I2S and LED runs on L1 (`L1_F.Cu` showed ~50 mm slots). Fix: per-class layer costs (digital prefers L4, power L3, analog L1). L1 is now near-solid.
2. **VCM took a 28 mm loop around the jack.** The divider pads were interleaved with GND pads. Fix: R6/R8/R7/C11 in a row with an explicit bus above them, now **4.9 mm**.
3. **+3V3A circled U2 on L1.** It was treated as an L1-only analog signal, and the loop blocked the I2S escape. Fix: it routes as a local supply (L3 allowed).
4. **AREG's 10 µF cap was unreachable** behind the 100 nF caps' GND vias. Fix: the caps sit in a row with pin 1 up, and comb stubs run from each pin.
5. **C25/C27 rotated with GND toward the IC.** DRC flagged two shorts. Fix: rotated 270°.
6. **I2S FSYNC/SDOUT could not escape** the 0.5 mm-pitch QFN. Fix: staggered fan-out vias for pins 21/22/23 (C25 moved 0.2 mm), placed before the GND fan-out.
7. **Castellated module pads tagged "under module"** were unroutable, which left VBAT_SENSE and nRESET open. Fix: tighter no-route tag.
8. **The router put vias inside the TC2030 keepout.** Fix: footprint rule areas are now router obstacles.
9. **The J2 shield pads were 0.225 mm from the edge** (rule 0.3). Fix: J2 moved 0.2 mm in. J2's GND pins tie straight to the shield, with no vias between the USB pins. VBUS routes before CC and D±.
10. **The BT1 lead pad was 1.9 mm from a standoff.** Fix: BT1 moved 2 mm.
11. **Library footprint USB4105** has 0.194 mm from its NPTH to a pad. The hole-clearance rule is set to 0.15 mm, within JLC's capability.

### Coordinator follow-ups (PR #104)

- **SJ1-3543 footprint (done).** Taken from the Same Sky SJ1-354X datasheet, p.2:
  - body 12.0 × 11.6 × 9.6 mm, M6×0.5 bushing 3.6 mm
  - pins 1 sleeve / 2 tip / 3 ring on Ø1.5 holes, 3.0 and 8.0 mm behind the connector edge, rows 2.5 mm apart
  - switch pins 4/5 aren't fitted on the -3543, so they are omitted
  - the three anchor legs are plated and tied to GND
  - axis height 5.2 mm, scaled from the front view (±0.3)

  The front-end parts moved off the larger body; tip → ESD/22 pF/bias is about 5 mm.
- **Board retention (done).** Two Ø2.2 mm holes (H1 (−25, −3.5), H2 (36, 26)) take M2 × 6 thread-forming screws into Ø5.6 printed bosses with a 1.8 mm pilot, 3 mm deep (`mech/pack.py` `PCB_SCREWS`). Two plain Ø4 rests at (−25, 25.5) and (30, −3.5). `fit.py` checks that the holes and bosses line up.
- **Light pipes and switch extension (done, `mech/pack.py`).**
  - Light pipes: chimneys Ø5.7 (bore 2.5, wall 1.6) hang from the lid to 0.4 mm above the LEDs. They are open bores; a 2.5 mm clear acrylic rod (15.4 mm) is optional. The lid now prints outer-face-down so the chimneys point up.
  - Switch: a printed fork (`switch_ext`, prints lying flat) straddles SW1's right-angle actuator, which sticks out 2 mm toward −y and slides 1.5 mm along x (KiCad footprint F.Fab). Its 2.0 × 1.7 mm stalk rises to 0.4 mm below the lid surface in a 4.6 × 2.3 mm slot.
  - The C&K datasheet (littelfuse.com) returned 403, so the actuator height isn't pinned. The prongs span 0.3–3.6 mm above the board to cover it. Check it on a real switch.
- **Cell holder → printed cradle (done, priced).** The MYOUNG BH-18650-B1BA002 holder is SMT, and the commercial leaded holder broke PK-12, so both are dropped. `mech/pack.py` `holder()` is now a cradle printed as part of the base:
  - two end blocks, each with a 0.5 mm slot (1.6 mm walls each side) and a U-window lip, plus side rails and 0.5 mm floor pads
  - contacts: MYOUNG **MY-18650-04-J** (+ plate with 1.8 mm dimple, LCSC C19184125, $0.1181 @ 50–149) and **MY-18650-05-J** (− plate + coil spring, free length 11.6 ± 0.8, LCSC C19184124, $0.1084)
  - each contact has a solder tail (Ø0.8 hole), bent 90° out through a notch in its block's back wall and wired to the BT1 pads
  - plate faces 76 mm apart, so the spring sits at **4.2 / 6.2 / 9.2 mm** for 70 / 68 / 65 mm cells (never solid, ≥ 0.6 mm preload); `fit.py` checks this
  - the plate's contact centre is 9.75 mm above its bottom edge, which is the cell axis
  - the door window is 2.4 mm longer, so a cell can be pushed into the spring

  Current: the contacts have no stated rating. The class figure for 0.3 mm phosphor bronze is about 1 A, against a 199 mA pack peak. Spring + plate + leads + traces is estimated at 0.10 Ω (20 mV at peak). The `audit.py` cutoff path now includes it, and the cutoff stays 3.2 V. **Closes the old holder-fit open item.**
- **Pigtail (done, priced).** BAT Wireless **BWIPX1-SMA-1.13L150** (IPEX/MHF1, 1.13 mm coax, 150 mm, 6 GHz), LCSC C784404, **$0.6015 @ 100**, 1908 in stock. Cut off the SMA, keep ~100 mm, and solder 31 mm of 0.9 mm tinned wire on as the whip (est. $0.03).
  - Loss: 0.10 m × ~3.6 dB/m + one IPEX pair ~0.1 dB = **0.46 dB**, under the new explicit `audit.py` allowance `PIGTAIL_IL_MAX_DB = 0.6`.
  - Before this, the link budget declared EIRP = conducted + 2 dBi with no feed loss. Conducted headroom makes the loss up: UK 7.5 dBm, US 18.5 dBm, BT40NE max 19.1.
- **Screws (priced).** 2 × M2-0.89 × 6 PT pan-head thread-forming screws, Fastener Superstore 585907, $0.112 each from a 5000-piece carton. LCSC and Accu had no listing I could read.
- **PK-12: $33.34** at qty 100 (was $34.98), a margin of $1.66. Line by line:
  - holder $1.36 → contacts $0.23
  - pigtail est. $1.00 → $0.60 + whip $0.03
  - screws +$0.22
  - cell leads +$0.02

  UK (`hw/bom/uk_total.py`): £26.58 ex VAT = $34.81 at the assumed 1.31 rate.

### Independent review follow-ups (#104 review, 2026-11-01)

- **M1 battery path (fixed).** BAT+ → F1 → Q1 → SW1 → VSYS now routes on **L1 (35 µm) at 1.0 mm**: new router class `bat`, L1 only, routed first.
  - Narrower sections are 0.4 mm necks of ≤ 1.36 mm, and only inside a 1.2 mm zone around pads too small for 1 mm (SOT-563/SOT-23-5 pins).
  - SW1's on-throw moved from pin 1 to **pin 3** (`pack.py`), so the battery feed and VSYS no longer cross at the switch.
  - Track resistance from the board is **40 mΩ** for all four nets (the reviewer measured ≈ 150 mΩ on In2).
  - `audit.py` now builds the cell path from the board (tracks) plus estimates for spring, plate and leads: **121 mΩ, over the old 100 mΩ allowance**. The cutoff computes to **3.2012 V, so it rounds up to 3.3 V** (1.2 mV over 3.2). **3.3 V accepted** (ADR-0012 amended): runtime at 3.3 V is 17.5 h ≥ 16 h (PK-7, asserted in `audit.py`), and the red LED (3.4 V) still sits above it.
  - `test_battery_path_on_l1_wide` asserts the layer, the widths, the neck lengths and ≤ 50 mΩ.
- **M2 test points (folded in).** TP3–TP11 from `review-104-tps` (415194b) are now in `pack.py` and `layout.py`. TP9–TP11 (I2S) and TP5 moved, because at their original spots they blocked the 1 mm VSYS corridor.
- **S1 (belt clip, fixed).** The clip inserts moved to (−24, 3) / (−24, 17), under the board and clear of the antenna overhang. Bosses stop 0.3 mm under the board, so the inserts are M2 × 3 heat-set. Still under or near the antenna: the lid-post screws at (−30, 26.9) and (−43.9, 26.9). Use nylon there if the PCB-antenna fallback matters. The board-copper keepout is ✓; the enclosure metal check is only partly ✓.
- **S2 (pigtail route, defined).** `mech/pack.py` `PIGTAIL`: from the u.FL at z 10.1, along y = 12 at z 11 (tie-down at x 5), over J2, to the whip exit at (42.5, 27.5, 20). Route is 81 mm, bend radius 6 mm (≥ 5 × OD). `fit.py` checks bends, the swept OD + 0.5 mm against every part, the light pipes, the switch fork and the walls; `pigtail()` is in the CadQuery interference set.
- **S3 (JLC outputs, done).**
  - `bom_jlc.csv` has an LCSC # on every line. Each code was checked against LCSC's product record.
  - `CONSIGN` (not at LCSC): F1 SF-1206F300-2, and the BT40NE (Fanstel only). R7 is C25760 (0402WGF1803TCE).
  - `DNP` (excluded from the CPL): BT1 cradle contacts (off-board), J1 (THT, hand-solder), J3 and TP pads.
  - CPL rotations use a footprint correction table (`outputs.py` `ROT_CORR`: SOT-23* +180, QFN +270, SOIC +270, after the community JLC rotation DB). Tests check both files.
  - SOT-563 (U4), USB4105 and JS102011SAQN have no table entry. Check them in JLC's CPL preview at DFM.

### Accepted warnings

- `starved_thermal` (4): the L1 pour reaches the J2 USB GND pads A1/A12/B1/B12 from one side only (corrected per #104 review S4; they tie straight to the shield). The zone's minimum spoke count can't be set from the KiCad 10 Python API, and the `min_resolved_spokes` rule does not override it. Each of these pads already has its own via to L2, so the pour is a second path. Downgraded to a warning in `pack.kicad_pro`.
- Silkscreen (22): passive refdes are hidden (F.Fab only). The remaining IC and connector refdes overlap copper in dense spots, which is cosmetic.

### Open items (must close before ordering)

1. ~~SJ1-3543 footprint provisional~~: done from the datasheet (see above). Still to check: axis height (5.2 ± 0.3) on a real part.
2. **BT40NE antenna wiring is unverified.** Datasheet p.22 says "The nRF21540 in BT40X is hardware-wired to the PCB trace antenna. ANT-SEL pin is not used." If that holds for the BT40NE, the u.FL/whip (PK-5) may not be driven at all. Ask Fanstel which path the BT40NE's FEM drives (ADR-0012 item 2). The keepout here supports either path.
3. ~~Holder~~: replaced by the printed cradle + MYOUNG contacts (done). Still to check: contact current rating (not published; class ~1 A vs 0.2 A peak) and the spring resistance estimate.
4. ~~PCB retention~~: done (2 × M2 + 2 rests).
5. ~~Light pipes / switch extension~~: done. Still to check: the SW1 actuator height.
6. ~~Pigtail~~: BWIPX1-SMA-1.13L150 cut to ~100 mm, 0.46 dB, priced (done).
7. **No 3D models are installed**, so the STEP is the bare board. The fit uses courtyard × datasheet height boxes (`outputs.py` `HEIGHT`).
8. **USB D± are routed as two 0.2 mm tracks**, not a 90 Ω coupled pair (~50 mm on L4). That is fine for full-speed 12 Mb/s.
9. **Fab DFM (end of project):** upload `hw/pack/out/fab/gerber` to JLCPCB's DFM check and attach the report. `bom_jlc.csv` has no LCSC numbers yet. Check the CPL rotations against JLC's preview (KiCad and JLC rotation conventions differ for some packages). Nothing has been uploaded and no account has been created.
