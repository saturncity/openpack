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

### Rules file finding (from the receiver review, 2026-11-01)

- **`pack.kicad_dru` was never loaded.** KiCad 10 drops the whole rules file when one rule does not parse, and gives no message. Here the culprit was `min_resolved_spokes`. So the "JLC minimums" in the DRC lines above were not being checked.
- **Fix:** the rule is gone. With the real rules, the pack is still **0 errors and 0 unconnected**. It now has 12 extra `text_thickness` warnings, because the IC refdes are 0.12 mm against JLC's 0.15 mm (cosmetic).
- **The JLC copper-clearance rule is gone too (#116 review M1).** Being unconditional, it overrode the netclass clearances, so a `kicad-cli` refill would have poured at 0.09 mm. The board-setup minimum of 0.1 mm is the floor, and the netclasses (0.127 mm) apply. Pack outputs are regenerated: DRC is 0 errors and 0 unconnected, and `test_pour_gaps_at_least_netclass` checks for gaps of at least 0.125 mm on the committed fill.
- `test_dru_rules_are_loaded` appends a probe rule and checks that it fires.

## Receiver sub-board (`hw/rx`)

**Result: DRC 0 errors, 0 warnings, 0 unconnected against the JLCPCB rules (`rx.kicad_dru`, proven loaded). Checklist clean apart from the open items below.** Fab DFM upload is still to do (end of project).

| | |
|---|---|
| Board | **48.0 × 90.0 mm**, 4 layers, 1.6 mm, ENIG. Mezzanine on the rack main board (#33): J1 is a 2×13 2.54 mm THT header on the **underside**, pin 14 pulled (ADR-0014), with two M3 standoff holes at the far end. 115 parts, 597 tracks, 478 vias (340 GND). All SMD parts are on top |
| Stackup | JLC04161H-7628, as on the pack: L1 signal + GND pour / L2 solid GND / L3 GND pour + digital / L4 GND pour + a few links |
| Rules | `hw/rx/rx.kicad_dru` adds three rules to the JLC minimums: `RF_50R` width 0.30–0.32 mm, RF gap ≥ 0.25 mm, and no Power/Audio_I track on inner copper, at any width. It has **no custom copper-clearance rule** (#116 review M1), so the netclasses apply: Default 0.127 mm, Power/Audio_I 0.15 mm (IPC-2221 B4, coated, 31–100 V needs 0.13 for the P48 nets), RF 0.25 mm. The zones' own 0.2 mm clearance also holds. The router works to 0.15 mm clearance, 0.2 mm signal, 0.5 mm current paths and 0.6/0.3 mm vias |
| Regenerate | `python3 hw/rx/layout_rx.py` (about 40 s). The run is deterministic apart from UUIDs. The zone fill is the one `kicad-cli` saves, so the gerbers carry the netclass RF gap |
| Renders | `hw/rx/out/render/`: `L1_F.Cu` … `L4_B.Cu`, `F/B.Silkscreen`, `F/B.Mask`, `F/B.Paste`, `top_assembly`, `bottom_assembly`, `3d_top`, `3d_bottom`. All were looked at, plus 100 px/mm crops of the RF, relay/J1, driver and module areas |
| Tests | `tests/test_rx_layout.py` (CI `pcb` job): DRC; rules loaded; saved fill = DRC fill; fresh fab outputs; gerbers regenerate identically; netlist ↔ pad parity; RF width/gap; current-path layers and widths; no digital net in the analog region; BOM/CPL coverage; CPL rotations; mech record |

**Floor plan (y up from the J1 edge):**
- **J1 strip (y < 7):** the audio pins 1–6 are on the left and the digital pins 13–26 on the right, as ADR-0014 orders them.
- **Left column, bottom to top (the audio path):**
  - K1 relay, contacts on the left and coil end to the right;
  - C48 and C47, the 47 µF BP radials;
  - the four S1J clamps, R47/R50;
  - the OPA1656 with its feedback parts and decoupling;
  - C40, then the PCM5102A (analog pins face left, I2S pins face right);
  - the RF block at the top.
- **Middle column:**
  - the +12 V/+5 V TVS over J1 pins 7–10;
  - D7/Q1 coil drive by the coil end;
  - R1/D9/C7 hold-up;
  - the TPS3808;
  - the VCM network;
  - U5 (+3V3A).
- **Right:** the BT40E (top), U4 (+3V3), TC2030, the backplane series resistors over J1 pins 13–26, and test points.

### Checklist

| Item | Finding | Status |
|---|---|---|
| **Module / keepout** | **BT40E footprint** (`footprints_rx.py`), from Fanstel p.11: 14 × 16 mm, 16 castellations at the module edges, 45 LGA pads at 1.5/1.2 mm pitch, H0–H3. The module sits in the top-right corner with its u.FL end 0.5 mm from the top edge, so the J5 → module jumper plugs in from the board edge.<br>The BT40E has **no PCB antenna** (u.FL only, ADR-0021), so there is no antenna copper keepout. Instead, L1 under the module is a GND pour with no tracks except the LGA fan-out stubs (`TAG_MODULE`). LGA signals leave through vias between the pad rows, on L3. | ✓ |
| **RF line** | **50 Ω grounded coplanar waveguide on L1 over L2**, `RF_50R`: **w = 0.31 mm, gap 0.25 mm → 51.5 Ω bare copper, ≈ 49.3 Ω under JLC's LPI mask** (εeff 2.94). It is sized with a 2D quasi-static field solve of this stackup (`hw/rx/rf_line.py`: FD Laplace, 5 µm grid, h 0.2104 mm, εr 4.4, 35 µm copper).<br>The closed-form conductor-backed CPW formula (Wadell/Ghione, also KiCad's calculator) was tried first and gave 0.39 mm. It is wrong for gap > h: at the microstrip limit it reads 57 Ω where Hammerstad–Jensen gives 50. The numbers are **raw, with no calibration offset** (#116 review N1).
  - The solver reads 51.35 Ω on the 0.346 mm microstrip. Hammerstad–Jensen with the mixed-dielectric thickness term gives ≈ 50.9 Ω, so the pack's own 0.346 mm line is ≈ 51 Ω, not 50.
  - The reviewer's independent FD solve gives 52.4 Ω for this line, or 49.3 Ω with 15 µm of mask.
  - Grid check: a 2.5 µm grid moves the result by 0.7 Ω.
  - Neighbours, raw: 0.30 mm → 52.3 Ω, 0.32 mm → 50.7 Ω.<br>Route: J3/J4 → 10 pF → PE4259 RF2/RF1 → RFC → 10 pF → J5. The longest line is 4.6 mm (0.07 λ in FR4), so impedance control at the fab is not needed. | ✓ |
| **Via fence** | 38 GND vias 1.0 mm off each RF line at 1.2 mm pitch (λ/28 in FR4). L1 has a perimeter fence at 3 mm pitch and stitching on a 4 mm grid. The u.FL ground pads and the PE4259 GND pin each have their own via. | ✓ |
| **Analog / quiet ground** | The analog column (DAC analog side, driver, clamps, coupling caps, relay contacts, J1 audio pins) is a tagged region, **closed on all three routing layers** to every digital and switching net: I2S, UART, SWD, LEDs, slot straps, ANT_SEL, OUT_EN, XSMT_EN, RLY_G/RLY_COIL, raw +12 V, +5 V and +3V3 (`test_noisy_nets_outside_analog_region`). Under it, L2 is solid and L3/L4 are unbroken GND pours, so no digital return current flows under the audio path.<br>I2S reaches the DAC's right-hand pins on L3 (stripline between the L2 plane and the L4 pour). The +3V3A LDO (U5) sits 11 mm from the DAC, on purpose; it is the analog supply. | ✓ |
| **Regulators / relay coil vs audio** | U4 (+3V3 LDO) is 27.5 mm from the op-amp and 32.6 mm from the DAC. Q1/D7 (coil drive) is 37 mm from the op-amp. The coil pins (1/10) are at K1's right-hand end. The coil current loop is +12 V J1 pins 7/8 → K1.1 → K1.10 → Q1 → GND vias, all outside the analog region.<br>The audio-leg tracks come within **2.0 mm** of the coil pins only inside K1's own footprint, where the contacts are. That cannot be avoided with a DPDT relay and is accepted. | ✓ |
| **Current paths** | Following the #104 M1 lesson, +12V, +12V_R, +12VA, +5V, +3V3, +3V3A, RLY_COIL and all ten audio-leg nets (phantom short: 0.9 A peak) are 0.5 mm on **L1/L4 only** (35 µm). They neck to 0.3 mm for ≤ 1.7 mm at small pads.<br>The only 0.2 mm +3V3 copper is three logic ties (PCM5102A FLT, PE4259 VDD at 9 µA, and its 100 nF). `test_current_paths_outer_and_wide` asserts the layers, ≥ 60 % full width per net, necks ≤ 2 mm, ties ≤ 20 mm. The `rx.kicad_dru` rule forbids these classes on inner layers. | ✓ |
| **Decoupling** (pin → cap pad) | **PCM5102A:** DVDD 1.9 mm, LDOO 1.9, AVDD 2.1, CPVDD 2.4, CAPP/CAPM 2.6 (L-stubs drawn before the GND fan-out), VNEG 3.7.<br>**OPA1656 V+:** 100 nF 1.9 mm, 10 µF 4.4 mm.<br>**LDOs:** U4 in 2.0 / out 2.6; U5 in 3.2 / out 3.4.<br>**Others:** TPS3808 1.5, PE4259 2.3.<br>**BT40E VDD (pad 9):** 3.2 / 4.5 mm. VDDH (F4, under the module) is 7.3 mm away through its fan-out via. Fanstel needs no external parts on an LDO-fed rail (p.26). | ✓ |
| **Backplane connector** | J1 follows ADR-0014. Pin 1 is at (8.76, 5.54) from the bottom-left corner: odd pins on the upper row (y 5.54), even pins on y 3.0, pairs every 2.54 mm in +x. The header is on the underside, so as seen from the top this mirrors the order the footprint gives on top. `place_j1` asserts the order, and `mech.json` records it for #33.<br>TVS D1/D2 sit right over the +12 V/+5 V pins. GND pins 5/6 guard audio from power. The digital series resistors are in two rows over pins 13–26. | ✓ |
| **Test points** | Following the #104 M2 lesson: **TP1–TP13**, Ø1 mm pads: +12V, +12VA, +5V, +3V3, +3V3A, GND on both the analog and the digital side, I2S BCK/LRCK/SDOUT (logic analyser), VCM, ANT_SEL, RLY_G. SWD is on the TC2030. | ✓ |
| **JLC assembly files** | `bom_jlc.csv` gives every placed part an LCSC # **read from its LCSC/JLC record on 2026-11-01**. The `LCSC source` column names the manufacturer part that was found. That includes K1 (C2684447, TQ2SA-12V-Z, the taped TQ2SA-12V).<br>Only the BT40E is CONSIGN (not at LCSC; Digi-Key UK 13174285). DNP: J1 and C47/C48 (THT, hand-solder), R33–R35 (not fitted), TPs, TC2030.<br>The CPL uses the pack's rotation table (SOT-23* +180, SOIC +270, checked by test), and DNP parts are not in it. | ✓ |
| **Silkscreen** | Refdes sit inside the IC and relay bodies. Passives keep theirs on F.Fab. J3/J4 are labelled "ANT A"/"ANT B", and there is a "J1 underside, pin 1" marker. DRC shows 0 silk warnings. | ✓ |

### Fixes made during review (found in the renders, crops or DRC, then fixed in `layout_rx.py`)

1. **The PE4259 GND pin had no via.** RF1/RF2 came in horizontally on either side of it, which left no room. Fix: both lines now enter the pins at 45°, which opens a wedge for pin 2's stub and via.
2. **Dangling tracks on L4 (I2S).** The router grew a net's tree from the raw A* cells. After string-pulling, a later branch could start at a cell the laid track no longer passed, which left two unconnected items. Fix: the tree now grows only from the committed segments. The pack's copy of this loop has the same latent bug, but its board shows 0 unconnected.
3. **CAPP/CAPM/VNEG were unreachable.** The CPGND/AGND fan-out vias took the room between the TSSOP pins and the caps. Fix: the caps sit in line with their pins, with L-stubs drawn before the GND fan-out.
4. **PCM5102A FLT (+3V3) was unreachable for a 0.5 mm rail track**, behind the I2S pins. Fix: no-current straps route as 0.2 mm logic ties, listed in `LOGIC_TIES` and tested.
5. **The RF gap in the gerbers was 0.20 mm, not 0.25.** The pcbnew fill used the zone clearance; netclass clearances only reach the filler through the project file. Fix: the board is saved from `kicad-cli pcb drc --refill-zones --save-board`. `test_saved_fill_is_the_drc_fill` runs DRC without a refill.
6. **The rules file was not loaded** (pack and rx; see the pack note above). Fix: the bad rule is removed and a probe test added.
7. **RF width from a formula outside its range** (0.39 mm → 46 Ω real). Fix: the field solve gives 0.31 mm.
8. **The COLD leg looped round J1 on L1** (`L1_F.Cu`, bottom left), and R49/R52 sat far from the relay. Fix: the 22 Ω/100 k pairs sit in the strip between J1 and K1. HOT reaches pin 3 on L1; COLD drops to L4 and passes under pin 2 to pin 4. No crossing.
9. **Digital bundle on L4.** Twelve backplane lines ran up to the module on L4, splitting its pour. Fix: digital prefers L3 (stripline between the L2 plane and the L4 pour), and L4 is now near-solid.
10. **The analog region left out the driver's feedback parts** (R43/R44/C42 at x 12.6–15.4). Fix: the region is widened and TP1 (+12 V) moved out of it.
11. **Decoupling too far.** The OPA1656 V+ 100 nF was 4.8 mm away. The TLV76733 in/out caps were on the wrong sides (6 mm). The TPS3808 cap was 4.3 mm away. Fix: 1.9 mm, 2.0/2.6 mm and 1.5 mm.
12. **Silk overlaps** (K1/D7, U6/C40, J3/U3 refdes over pads). Fix: refdes moved inside the bodies and the antenna labels added.

### Independent review follow-ups (#116 review, 2026-11-01)

- **M1, pour clearance (fixed).** The unconditional `JLC copper clearance` (0.09 mm) rule overrode every netclass. It produced 493 pour gaps of 0.0905 mm, 157 of them under 0.13 mm on the P48 audio nets.
  - The rule is deleted in `rx.kicad_dru` and `pack.kicad_dru`, and both boards are refilled and regenerated.
  - `test_pour_gaps_per_class` appends probe rules (≥ 0.125 mm everywhere, ≥ 0.15 mm to Audio_I) and runs DRC on the committed fill without a refill: 0 hits. A 0.16 mm control probe does fire.
  - The outer-copper rule now catches any Power/Audio_I track on an inner layer, whatever its width (N6).
- **S1, pin-14 key (fixed).**
  - J1 is now `openpack:PinHeader_2x13_P2.54mm_Key14`: the stock footprint with **pad 14 deleted, so there is no hole**, and "KEY" silk at the empty position on both sides. A full 26-pin header cannot be fitted.
  - The header is XFCN **PZ254V-12-26P** (LCSC C22465887, 2401 at JLC), with pin 14 cut before hand-soldering.
  - The main-board socket is the one #33 already chose (ADR-0018): **Harwin M20-7831346 with a Harwin M20-003 polarising key in position 14**, both from DigiKey UK. ADR-0014 now points to it. The key plugs the socket, and the missing hole stops a full header, so neither side can be fitted wrong on its own.
  - `test_j1_key_has_no_hole_at_14` checks the footprint, the board, the BOM and the ADR.
- **S2, RF grounds (fixed).** The GND pads of J3/J4/J5, the PE4259 and the BT40E (castellation 10, LGA, H0–H3) now have a **solid zone connection** (`zone_connect 2`). Every other GND pad keeps its thermal relief. `test_rf_ground_pads_solid` checks this. DRC is still 0/0/0.
- **S3, K1 orientation (fixed, preview check kept).**
  - The footprint has a filled dot and a "+" beyond pad 1 (coil +), outside the body.
  - The CPL now adds **+270° for `Panasonic_TQ2SA`**, so K1 is at 180°. The reasoning: the datasheet top view (the drawing JLC/EasyEDA parts follow) has the pin rows horizontal, with pin 1 bottom-left and 10 above it. That is KiCad's part turned +90°, which is the SOIC rule.
  - EasyEDA's own footprint for C2684447 could not be fetched (HTTP 403), so K1 is still the first part to check in JLC's CPL preview.
  - `test_polarized_parts_pin1_marker_and_cpl` covers the relay, all diodes, Q1, the electrolytics and every IC. Each must have a silk marker on its pin-1 side (KiCad's pin-1 triangle, the cathode bar, "+" or a dot), and its CPL rotation must equal the board rotation plus its package correction.
- **N1:** the calibration offset is dropped; raw and masked figures are recorded above.
- **N2 (accepted):** the 44 vias under the BT40E LGA are tented, with about 0.36 mm from via edge to pad. Order JLC's "epoxy-filled and capped" via option if the DFM report flags them.
- **N3 (fixed):** C44 (VCM 100 nF) is now 2.4 mm from U6 pin 5, down from 6.6 mm.
- **N4 (noted):** the audio legs are not mirror images, a difference of about 10 mΩ and < 1 pF. The low-frequency balance is set by C47/C48 at ±20 %. That matters for 20–50 Hz CMRR, so the tolerance belongs in ADR-0014's numbers if it is ever specified.
- **N5 (open):** there are no labelled pads on DRV_OUTA/B, XSMT or OUT_EN. Probe at K1's pads, the R37/R38 node and R62 for now, and add pads at the next schematic pass.
- **N7 (noted):** `rx.py` emits its hierarchical sheets in a varying order. The netlist content is identical, and CI does not diff it.

### Mechanical record for the rack (#33)

There is no rack mechanics yet, so this layout defines it (`layout_rx.MECH` → `hw/rx/out/fab/mech.json`):

- **Board:** 48.0 × 90.0 × 1.6 mm.
- **J1:** pin 1 at (8.76, 5.54) mm from the bottom-left corner, on the J1 (short) edge, header on the underside.
- **Standoffs:** two M3 at (3.4, 86.6) and (44.6, 40.0).
- **Stack height:**
  - main-board 2×13 socket (8.5 mm) + header body 2.5 mm = sub-board underside 11.0 mm above the main board;
  - tallest top part: C47/C48, Nichicon **UEP1J470MPD**, a 47 µF 63 V bi-polar radial, 10 × 16 mm, L + 1.5 mm max (Nichicon CAT.8100L), so **17.5 mm** seated;
  - so the sub-board top is **30.1 mm above the main-board top** (11.0 + 1.6 + 17.5);
  - 1U leaves about 35 mm there (44.45 − 2 × 1.2 mm sheet − 5 mm standoff − 1.6 mm main board), which is 4.9 mm spare;
  - next tallest: K1 at 5.6 mm (TQ datasheet) and C7 at 5.4 mm;
  - `test_mech_record` checks the sum.
- **Rack fit:** 8 slots at ≥ 52 mm pitch = 416 mm, inside a 19″ 1U case (~425 mm inside).
- **Socket:** #33's socket must be a 2×13 female with position 14 plugged (ADR-0014). The U.FL inputs J3/J4 are at x 8.8 mm, 4.5 mm and 11 mm below the top edge, for the splitter coax.

### Open items (must close before ordering)

1. ~~TQ2SA land pattern provisional~~ **(closed).** The footprint now follows the Panasonic TQ datasheet (© 2019, the LCSC C2684447 PDF), p.11, "Surface-mount terminal, SA type", "Suggested mounting pad (Top view)": 1.0 × 2.94 mm pads, 2.54 mm pitch, **9.56 mm between the row centres** (±0.1); body 14 × 9 × 5.6 mm. The relay sits as before; DRC is still 0/0/0.
2. **The BT40E u.FL position (12.05, 14.6) is scaled from the p.11 drawing.** It is F.Fab only, so it does not affect copper. The pad grid is dimensioned on the drawing.
3. ~~LCSC codes~~ **(closed).** All 39 placed BOM lines carry a code read from its LCSC product record or JLC parts search on 2026-11-01. The manufacturer part found is recorded in each line.
   - **All 13 earlier codes checked out.** C88374 is Hirose's 80-piece-reel suffix of the same U.FL.
   - **The 17 `MATCH` lines are now real parts:**
     - resistors: UNI-ROYAL 3.65k C67235, 4.99k C25903, 249k C11425, 9.76k C270420;
     - ceramic capacitors: Murata 2.2 nF C0G C385029, Samsung 2.2 µF X7R C100082, 10 µF 25 V 1206 C14860;
     - electrolytics: Honor 47 µF/22 µF 25 V 5 × 5.4 C696191/C15848, FOSAN 100 µF 25 V 6.3 × 5.4 C7469933;
     - ICs: TI TLV76733DGNR C2873382, TPS3808G01DBVR C19653;
     - discretes: onsemi BSS138 C52895, Nexperia BAT54,215 C85084, onsemi S1J C184326, MDD SMF15A C123802 and SMF5.0A C193402.
   - **The relay is no longer consigned:** C2684447.
   - **Stock at JLC is low on two parts:** TLV76733DGNR (583) and the relay (2245). Re-check both at order time.
4. ~~C47/C48 height~~ **(closed).** The part is Nichicon UEP1J470MPD, 10 × 16 mm (17.5 mm max). It fits the stack with 4.9 mm spare (see the mechanical record). If #33 needs more room, a 12.5 mm-tall 33 µF (UEP1J330MPD, 10 × 12.5) would change the 20 Hz corner; that needs a new SPICE run first.
5. **CPL:** SOT-363 (PE4259), HVSSOP-8 (TLV76733), the TSSOP-20 and the relay have no rotation-table entry. Check them in JLC's CPL preview.
6. **Board size:** the right half below the module (x 30–48, y 14–56) is sparse. Moving the +12 V/supervisor block there would free about 10 mm of height (48 × 80) if rack depth gets tight.
7. **No 3D models are installed** (as on the pack), so the STEP is the bare board.
8. **PE4259 isolation (ADR-0014 item 5):** the two input lines are 1.3 mm apart only at the switch pins, with the GND pin via between them. Measure A↔B isolation on the bench.
9. **Fab DFM (end of project):** upload `hw/rx/out/fab/gerber` and attach the report.
