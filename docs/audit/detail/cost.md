# OpenPack cost anatomy (audit of commit 6f0d592, 2026-11-01)

All figures GBP ex VAT unless marked. **Q** = quoted (a distributor page was read, per the `source` column), **E** = estimate (class price or reviewer range, marked `est.` in the repo), **A** = my own estimate assembled from repo lines (not in the repo). Receiver sub-board lines are USD qty-100 figures converted at 0.76 (`hw/rx/prices.py:10`), so they are conversions, not UK quotes, except the BT40E.

Sources: `.ws/.venv/bin/python3 audit.py` (output saved at `/tmp/claude-1000/-home-lenzj-openpack/e6c06cca-2213-4031-baf0-9c208949eb5f/scratchpad/audit_out.txt`, Audit 5 lines 215-231, receiver BOM 232-292, Audit 6 361-445), `hw/rack/prices.py`, `hw/rx/prices.py`, `hw/pack/prices.py`, `hw/rack/out/bom.csv`, `hw/rx/out/bom.csv`, `docs/shopping-list.md`, ADR-0014/0016/0018/0021, `docs/design-log.md` RK-1..RK-7k, `mech/rack.py`, `hw/rack/layout.py`, `hw/rx/layout_rx.py`, `host/channel_plan.py`, `git show report-ib-ia:docs/report/REPORT.md` (C4, C9, D6, E).

---

## 1. Headline numbers (audit.py, `audit_out.txt` line 444)

| Block | GBP | Source |
|---|---:|---|
| Main board + host + cables (`hw/rack/out/bom.csv`, 76 lines) | 709.04 | 343.90 of it is E lines |
| 8 receiver sub-boards (8 x 23.38) | 187.04 | converted USD, `hw/rx/out/bom.csv` |
| Antennas, coax, adapters (`ANTENNA_KIT` lines 1-4, `hw/rack/prices.py:109-115`) | 294.86 | Q (ITM Components, RS) |
| Two Thor LS003 stands + two HGX-PMT07 mounts (`hw/rack/prices.py:116-119`) | 310.56 | Q (owner-given) |
| **Rack total** | **1,501.50** | audit.py line 1293: `main_gbp + 8 * rx_gbp + rp.ANTENNA_KIT_GBP` |
| Like for like without stands (RK-7k) | 1,190.94 | |
| Target (RK-7k, design-log line 556) | 800-830 | |

**Per channel (8 channels):** £187.69 with stands; £148.87 without (report D6 says "about £149"). Of that £148.87, only **£23.38 is the receiver itself**; **£88.63 per channel is the fixed main board/host/case** (£709.04 / 8), and **£36.86 per channel is antennas + coax**.

Pack, for comparison: $33.34 at qty 100 ex cell (`audit_out.txt` line 113), module BT40NE $13.47 of it (Fanstel direct); $36.63 at Digi-Key prices. About £25 per pack at the report's 1.31 rate. **One pack costs one sixth of one rack channel.**

Cost drift over the project (same rack, three snapshots):
- ADR-0018 as first accepted (PR #95, `docs/adr/0018:64`): main board + host + cables **£426.32**, 8 sub-boards £210.80 (BT40NE), antennas £340.56 -> **£977.68**. That version priced the main board PCB at **£25 est. for "~400 x 150 mm"** and a **£60 est. generic steel 1U case** (`git show f9b4df7:hw/rack/prices.py`, EXTRAS last two lines).
- RK-7k baseline "the rack was £953.92" (after the BT40E swap, -£24).
- Final (#34/#126): **£1,501.50**. Drivers of the +£548: PCB line £25 -> £40 -> **£300** (+£275; RK-7k), case £60 -> **£140.76 Hammond** (+£80.76; owner-fixed), **stands +£310.56** (new, ADR-0021 4 m booms), far-wing coax CA3N050 -> CA3N075 (+£42.22; RK-7h). Offsets: N-BNC adapter instead of a £37.09 jumper (-£57.38), u.FL jumpers 16 x £4.48 -> 16 x £1.02 (-£55.36), BT40E (-£24).

---

## 2. Rack cost by block and the top 12 line items

### 2a. Main board + host + cables (£709.04), by function (summed from `hw/rack/out/bom.csv`)

| Block | GBP | % of 709 | Q/E |
|---|---:|---:|---|
| Main-board PCB order (5 x 412 x 321.5 mm 4-layer ENIG, framed stencil, extended-part fees, DHL ~2 kg, UK import VAT) | 300.00 | 42 % | **E** (reviewer range 250-350; "quote before ordering", RK-7a/RK-7k). Note: this line already *includes* import VAT, so the ex-VAT total is slightly inconsistent (shopping-list.md line 226). |
| Case: Hammond RM1U1913SBK | 140.76 | 20 % | Q (Rapid Online) |
| Host: CM4 2 GB/8 GB no-wireless £79.20 + CM4IO £26.15 + ribbon £1.30 + 12 V pigtail £3.00 | 109.65 | 15 % | Q except pigtail |
| Power: brick £14.50, UK cord £8.35, 20 x TPS2595 eFuses £11.16, buck/LDO/inductor £2.12, fuse/TVS/FET £1.58, DC jack £1.22, caps | 39.59 | 6 % | mostly Q |
| RF front end + Wilkinson copper: 2 x BNC £13.90, 2 x QPL9057 £9.20, 2 x QPQ1907 £5.64, ESD/bias-T parts, 14 x 100 R thin film £1.12 | 31.74 | 4 % | BNC E, rest Q |
| XLR outputs: 8 x NC3MAH £16.64 + 16 x SMAJ58CA £5.76 | 22.40 | 3 % | Q |
| RF distribution: 16 x U.FL receptacles £5.44 + 16 x 100 mm u.FL jumpers £16.32 | 21.76 | 3 % | Q/E |
| Rear panel I/O: etherCON £12.78, Cat6 £2.00, USB-C panel lead £3.83 | 18.61 | 3 % | Q |
| Host UART fan-out: 2 x SC16IS752 £11.84, crystals, headers | 12.29 | 2 % | Q |
| Spacers/standoffs | 8.00 | 1 % | E |
| Slot sockets + 16 LEDs | 1.84 | | E |
| Small R/C | 2.40 | | E |

**Three lines (PCB order, case, CM4+CM4IO) are £575.91 = 81 % of the main board block and 38 % of the whole rack.** Everything electrical that actually does the rack's job (RF chain, splitter, eFuses, XLRs, UART fan-out, u.FL distribution) is about £130.

### 2b. Top 12 single line items across the rack (one rack)

| # | Item | GBP | Q/E | What forced it |
|---|---|---:|---|---|
| 1 | Main-board PCB order, 5 x 412 x 321.5 mm 4-layer (`bom.csv:73`) | 300.00 | E | R9 (1U, 8 XLR) + ADR-0014 52 mm slot pitch -> 412 mm wide; RK-7a "one board filling the case" -> 321.5 mm deep; 4 layers for 50 ohm microstrip Wilkinson (ADR-0018, RK-7c) |
| 2 | 2 x Thor LS003 4 m winch stands (`prices.py:116`) | 281.66 | Q | ADR-0021 wing install: panel 4.0 m up (3.7-4.5) to meet R1 at UK 9 dBm EIRP. Listed as an optional cut (venue booms) |
| 3 | 2 x L-com HG2409P-NF 8 dBi patch (`prices.py:109`) | 144.24 | Q | ADR-0016: directional antennas to reject audience Wi-Fi so R1 passes under EN 300 328 (ADR-0015 stop-and-ask) |
| 4 | Hammond RM1U1913SBK case (`bom.csv:74`) | 140.76 | Q | R9 "1U rackmount"; part fixed by the owner's parts list (RK-7k: "fixed by the owner") |
| 5 | CA3N075 75 ft CA-400 coax, far wing (`prices.py:112`) | 88.02 | Q | ADR-0021 (both antennas in the wings) + Audit 5 cable routing: far wing needs 13.6-21.5 m (RK-7h) |
| 6 | 8 x BT40E module, £9.78 each (`hw/rx/out/bom.csv:52`) | 78.21 | Q (DK UK) | ADR-0002 FDMA, one carrier pair per pack -> one radio per pack (R1, R3); ADR-0021 BT40E not BT40NE (no FEM to overload) |
| 7 | Raspberry Pi CM4 2 GB / 8 GB eMMC, no wireless (`bom.csv:63`) | 79.20 | Q | R11 remote management (REST/WebSocket, Ethernet) + R1 "no wireless on the host" (ADR-0018, RK-5); owner-fixed |
| 8 | CA3N030 30 ft coax, near wing (`prices.py:110`) | 45.80 | Q | ADR-0021 / RK-2 coax budget |
| 9 | 2 x HGX-PMT07 mast mounts (`prices.py:118`) | 28.90 | Q | ADR-0021 (mount on a 35 mm stand top) |
| 10 | CM4 IO Board SC0326 (`bom.csv:64`) | 26.15 | Q | ADR-0018 RK-5: vendor carrier instead of a CM4 on the main board (R13 "vendor board, no new Ethernet/power design") |
| 11 | 8 x TQ2SA-12V relay, £2.43 each (`hw/rx/out/bom.csv:24`) | 19.46 | E | ADR-0014 mute: no thump into the PA on brick failure (R5). Mute circuit adds ~$4.2 per channel |
| 12 | 8 x PCM5102A DAC, £2.13 each (`hw/rx/out/bom.csv:54`) | 17.02 | Q | R9 "one analog XLR per channel" (one DAC + driver per channel) |

Runners-up: 2 x N-BNC adapter £16.80 (Q), 8 x NC3MAH £16.64 (Q), 16 x u.FL jumpers £16.32 (Q), brick £14.50 (Q), 2 x TE BNC £13.90 (E), 2 x SC16IS752 £11.84 (Q), 8 x OPA1656 £11.19 (Q), 20 eFuses £11.16 (Q), 2 x QPL9057 £9.20 (Q).

Note the pattern: the top 5 lines (£954.68, 64 % of the rack) are **PCB area, metal, antennas, cable and stands**. Not one of them is a semiconductor. The entire RF signal chain of the rack (2 LNA, 2 BAW, 8 modules, 8 DACs, 8 op-amps, 2 UART bridges) is under £150.

### 2c. Receiver sub-board (£23.38 each, `audit_out.txt` 232-291)

BT40E £9.77 (42 %), TQ2SA relay £2.43, PCM5102A £2.13, OPA1656 £1.40, PCB 48 x 90 mm 4-layer £1.14 (E, qty-100 panel share), u.FL jumper £1.14 (E), 3 x U.FL receptacle £1.02, 2 x TLV767 £0.61, TPS3808 £0.61, PE4259 £0.31, header £0.30, passives/diodes ~£2.5. The mute (relay + supervisor + FET + diodes, ADR-0014) is ~£3.2 = 14 % of the board. QUESTIONS.md Q14 guessed "Receiver ~$150-250 in parts" for the **whole rack**; the 8 sub-boards alone are $245 (ADR-0014 line 51).

---

## 3. Why the main board is 412 x 321.5 mm

The size is the product of two independent decisions, neither of which was ever costed as a board-area decision.

### 3a. Width 412 mm = 7 x 52 + 48: set by the receiver sub-board before any rack mechanics existed

- `hw/rx/layout_rx.py:39-46` (PR #34 receiver layout): *"No rack mechanics exist yet (#33), so this defines them: a 48 x 90 mm mezzanine ... Eight slots at >= 52 mm pitch = 416 mm, inside a 19" 1U case (~425 mm inside)."* `slot_pitch_min=52.0` (line 50) is exported in `hw/rx/out/fab/mech.json`.
- `hw/rack/layout.py:65-69` reads it: `PITCH = RX_MECH["slot_pitch_min"]` and asserts `(N_SLOTS - 1) * PITCH + SUB_W <= BW`, i.e. 7 x 52 + 48 = **412.0 exactly**.
- Why 48 x 90 mm per receiver: the receiver is a mezzanine standing up on a 2 x 13 header (ADR-0014 "Board split"), carrying the full analog output stage (OPA1656 driver, two 10 x 16 mm bipolar 47 uF caps, relay, supervisor), the DAC, two LDOs, the PE4259 switch and the module. ADR-0014's requirements table rejected XLR-on-each-sub-board because "vertical cards don't fit 44 mm", so the cards lie flat and each card is 48 mm wide -> 8 flat cards side by side fill the whole 19" width.
- Consequence for RF: the eight splitter ports have to sit behind eight receivers spread over 400 mm, so each 1:8 Wilkinson tree carries 834 mm (A) / 754 mm (B) of 50 ohm distribution line plus 252 mm of divider arms (RK-7c, `hw/rack/out/rf_routed.json`). That is why the as-routed loss is 13.66 dB against the 9.03 dB ideal split and the 11 dB ADR-0018 target, and why SPEC RK-5 was amended to <= 14 dB in #126. **The splitter geometry did not set the board size; the board size (receiver pitch) set the splitter loss.**

### 3b. Depth 321.5 mm = the case's inside depth 323.85 mm minus 2.35 mm: "one board filling the 1U case"

- Design-log RK-7a (line 443-451): options were "one board filling the case; a narrow backplane strip plus a host tray joined by cables". Chosen: one board, 412 x 321.5 mm, 444 footprints, 6267 vias. The #126 review "kept the full-size board" and only moved the front edge from 323.0 to 321.5 mm.
- `hw/rack/layout.py:17-21` shows the depth budget: y 0-33 rear connectors, y 33-62 tree B + 16 u.FL ports, y 70-160 the receivers (90 mm long), y 78-93 tree A under the receivers, **y 200-323 "host: SC16IS752 x 2, ribbon header, CM4 IO board on 10 mm spacers above; front LEDs at the edge"**. The CM4IO (160 x 90 mm, `layout.py:92-96`) is mounted on four M2.5 spacers that stand on the main board at y 228-318, and the 16 front-panel LEDs are side-looking LEDs on the board's front edge (RK-7a) so the board had to reach the front panel.
- So the rear 165 mm of depth is functional (connectors, RF, receivers) and the **front ~155 mm exists only to carry the CM4IO's mounting holes, two UART bridges and the LED row**. Roughly 48 % of the board area (412 x 155 of 412 x 321.5) is a mechanical tray for a vendor board and 16 LEDs.
- Before #34, ADR-0018/PR #95 had priced the main board as "~400 x 150 mm" at £25 est. (`git show f9b4df7:hw/rack/prices.py`). The layout PR more than doubled the area and the #126 review re-priced the order as the whole JLC batch (5 boards minimum, large framed stencil, DHL for ~2 kg, import VAT) at £300.

### 3c. The 1U chassis decision chain

- R9 says "1U rackmount" (REQUIREMENTS.md line 19) and it is ranked 9th of 15. The agents treated 1U as a hard dimension (SPEC SYS-1, RK-1) and then selected the case from the owner's parts list (Hammond RM1U1913SBK, 330 mm deep, £140.76; RK-7k "fixed by the owner"). The earlier estimate had been a £60 "~250 mm deep steel case with blank rear panel".
- The 40.09 mm inside height forced flat mezzanines (ADR-0014) -> 48 mm card width -> 412 mm board. The 323.85 mm inside depth was then simply filled (RK-7a). Lid clearance ended at 3.39 mm, side wall 1.65 mm, and the Hammond cover-screw lugs may touch the board edges (open risk 18). A 1U case was over-served: everything was engineered to the millimetre to fit one specific aluminium extrusion that costs more than all eight XLRs, both LNAs, both filters and both UART bridges together.

### 3d. What a smaller alternative would have looked like, and what the repo lets us say about savings

| Alternative | What changes | Saving (repo numbers where they exist) |
|---|---|---|
| **(i) Shorten the board to ~165-200 mm** (stop behind the receivers; mount the CM4IO on the case floor; put the LEDs on a cheap 2-layer front strip or use panel LEDs with a 16-way ribbon) | Same schematic, half the 4-layer area. PR #95 priced a 400 x 150 mm board at £25 est. (A: a 412 x 170 mm 5-board order is plausibly £120-180 all-in vs £300; the JLC 4-layer area charge itself is only ~USD 70/m2 per shopping-list line 222, so most of the £300 is batch minimum, stencil and freight) | **A: ~£120-180 saved**; nothing else changes. RK-7a listed the option ("narrow backplane strip plus a host tray") and did not cost it. |
| **(ii) Receivers on a cheap 2-layer bus board, RF by coax** | Only power/UART/audio on the backplane (no 50 ohm copper -> 2 layers, no ENIG needed). Splitter either a small separate 4-layer card (2 x 1:8, roughly 60 x 100 mm) or off the shelf. ADR-0018 line 43 rejected "a central splitter with 16 coax runs to the slots" on two grounds: PIMD distance worsens 1.2 -> 1.7 m (because the *lower* loss drives the nRF5340 harder) and "16 coax runs would have to fit in 1U". The repo also notes it is ~2 dB better in NF. | **A:** the 16 jumpers already exist (£16.32). The 2 dB NF gain is spare (margin is 8.2 dB). PIMD could be restored with a 2 dB pad (pence). Saving is the 4-layer-area premium of (i) plus ENIG; the repo gives no 2-layer quote. |
| **(iii) No backplane at all**: 8 receivers as stand-alone USB "dongles" on a hub, XLR on each card, splitter card feeding u.FL | Loses the per-slot eFuses, keyed sockets, mute-relay supply sequencing; keeps 8 XLR. Would need the receivers redesigned for 5 V only (the OPA1656 driver runs from +12 V for +18 dBu headroom, ADR-0014). | Not costed in repo. Kills the £300 line but needs a re-spin of the receiver. |
| **(iv) Off-the-shelf 1:8 splitter + star of u.FL/SMA jumpers** | No splitter copper, no QPQ1907/QPL9057 layout. Commercial 1:8 2.4 GHz dividers are typically a few tens of pounds each (A, no repo quote). Their loss (~10-11 dB) is *less* than the routed trees (13.66 dB), so the PIMD argument in ADR-0018 applies and a small pad is needed. | **A:** likely cost-neutral to slightly positive versus the Wilkinson copper, but removes the only reason for a 4-layer main board. |
| **(v) Drop the CM4 + CM4IO (£105.35) for a Pi Zero 2 W with Wi-Fi disabled or an RP2040/STM32 USB-UART hub + the booth laptop as host** | ADR-0018's R1 rationale was "no wireless on the host"; the SC0680 CM4 is the no-wireless SKU. ADR-0018 table also scored a Pi 4/5 SBC as "partial". | **A:** -£60 to -£90. The repo did not cost a sub-£30 host. |
| **(vi) Generic 1U/2U steel case** | PR #95's own estimate was £60; a 2U case would also have allowed vertical cards (ADR-0014 rejected them only for 44 mm) and so a narrower backplane. | **-£80.76 against the Hammond (repo numbers).** |

A defensible, same-architecture target from the repo's own figures: (i)+(v)+(vi) is roughly **-£300 to -£350**, i.e. a rack of ~£850-900 like for like, close to the £800-830 target **without touching R1**. The agents' D6 conclusion that "part swaps cannot fix the cost" is only true of the top 5 lines as a set; it is not true of the PCB area, host and case lines individually, which were never optimised because the board was treated as the "one large board that is the most expensive item in the rack and the most likely to change" (report E) rather than re-sized.

---

## 4. Minimal bench prototype from the existing designs (no rack, no splitter, no LNA, whip antennas, laptop host)

Repo prices; **A** marks my aggregation. Shopping-list "Packs x4" = £133.85 for four packs' parts at qty-4 prices with spares (shopping-list.md line 331), so ~£33.5/pack of parts; "Receivers x4" = £85.87 (~£21.5 each) plus shared-passive lines.

### Option A: 2 packs + 1 nRF5340-DK as the receiver (cheapest)

| Item | GBP ex VAT | Q/E/A | Repo source |
|---|---:|---|---|
| Pack parts x 2 (BT40NE £16.34 each at DK UK qty 4, PCM1840, OPA1656, boost, jack...) | ~70 | A from Packs x4 £133.85 | shopping-list.md line 75, 331 |
| Pack PCB 10 pcs 4-layer 73.5 x 35.1 mm + stencil | 36.00 | E | shopping-list.md 221-222 |
| 2 protected 18650 cells | 14.00 | E (not sourced) | line 148 |
| Nitecore UI2 charger | 16.63 | Q | line 304 |
| PETG 1 kg (enclosures) | 11.67 | Q | line 313 |
| nRF5340-DK (receiver role, `SB_CONFIG_OP_ROLE_RX=y`, UART to laptop via onboard J-Link VCOM) | 36.58 | Q | line 73 |
| PCM5102A I2S DAC breakout (Adafruit 6250) for audio out of the DK | 3.70 | Q | line 66 |
| Tag-Connect TC2030-IDC-NL (program the pack boards from the DK's debug-out) | 46.00 | Q | line 289 |
| Solder paste 35 g | 29.37 | Q | line 152 |
| Micro-USB cables x 3, Dupont wires | 12.50 | E | lines 264-265 |
| Lav mic + TRS cable (Thomann) | 18.50 | E | lines 276-277 |
| **Subtotal, working 2-pack link on the bench** | **~£295** | A | |
| + 2nd nRF5340-DK (TX peer before pack boards are soldered) | 36.58 | Q | line 73 |
| + logic analyser (end-to-end latency, R3) | 20.44 | Q | line 69 |
| + tinySA Ultra+ £140 (Lab401, FR) + 20 dB + 10 dB attenuators £61.81 + u.FL-SMA pigtails £4.38 (EN 300 328 2482 OBW check, open risk 2) | 206.19 | Q | lines 286, 67; shopping.py 90-98 |
| + PPK2 (R8 runtime) | 80.17 | Q | line 72 |
| **Everything the repo's Phase 5 bench plan wanted, minus the rack** | **~£640** | A | |

Shipping lines in the list (~£128 for the full order) would scale down but Lab401, Knives&Tools, Thomann each add £8-15.

### Option B: real receiver sub-board instead of the DK (+~£90, A)

Receiver parts for 1-2 boards ~£25-30 each (BT40E £9.78 at DK UK; relay, DAC, op-amp, LDOs...) + receiver PCB 10 pcs £36 + stencil £8 (E, lines 223-224). Caveat: the sub-board is a mezzanine; J1 (`ADR-0014` pin table) expects +12 V and +5 V and routes UART, nRESET, BOOT and the balanced audio through the 2 x 13 header, and XLRs live on the main board. A bench build needs a trivial 2 x 13 breakout with a 12 V brick, a 5 V regulator, a USB-UART (£5, A) and a flying XLR. Nothing in the repo provides that breakout. The DK (Option A) is the quicker path; the sub-board is only needed to test the mute relay, +18 dBu driver and PE4259 antenna switch.

### What the bench build cannot test

R1 under audience Wi-Fi (needs the antennas, the wing geometry and a full house: G5/G6), the Wilkinson loss, the rack NF, PIMD near the panels, the CM4 host. It does test: codec, latency (R3), audio chain (R2, R5), battery (R8), firmware, 2482 MHz legality, and the pack as a product.

---

## 5. Scaling the current architecture to 32 packs in one venue

### Cost (straight multiplication, repo numbers)

- 4 racks x £1,190.94 = £4,764 like for like; the stands/antennas could be shared (one pair + 1:4 external splitter, not designed) or duplicated (4 x £605.42 = £2,422). **A: £5,100-7,200 for 32 channels, £160-225 per channel.** The fixed per-rack £709 (case, PCB, CM4) never amortises because every 8 channels buys another case, another 412 x 321.5 mm board and another CM4; the architecture has no 16- or 32-slot variant.
- Antenna feed: each rack has 2 BNC (R10). Four racks from two wing panels need an external 1:4 (6 dB more loss ahead of each rack's LNA, eating the 8.2 dB NF margin to ~2 dB) or 8 panels (which is the "8-16 antennas" R10 was written against).

### Spectrum: the hard limit (`host/channel_plan.py`, AUDIT-2 B1, ADR-0002, ADR-0016)

- Rules: carriers 2 MHz wide on a **3 MHz minimum spacing** (`MIN_SPACING = 3`, line 15; 2 MHz neighbours collide, bsim #76); fA in 2402-2440, fB >= fA + 40 (line 41-43); UK top carrier 2482. The band 2403-2482 holds **27 carriers at 3 MHz**, and the fA/fB windows hold 13 and 14 -> **at most 13 carrier pairs = 13 packs in one venue, whatever the number of racks**.
- Gap carriers clear of Wi-Fi 1/6/11: **8 in the UK** (2423 2426 | 2448 2451 | 2473 2476 2479 2482, `channel_plan.yaml` line 4), 7 in the US. AUDIT-2 (line 14) and `audit_out.txt` line 53: "10 x 2 MHz carriers fit in gaps ... need 16 for 8 packs x 2 copies". Already at 8 packs, 8 of the 16 carriers sit under Wi-Fi; R1 rests on each pack keeping one gap copy plus the install rule. **Packs 9-13 would have both copies under Wi-Fi** and no diversity against bursts; ADR-0016/0021's R1 case does not cover them. If the venue runs Wi-Fi 13, four gap carriers are lost (yaml line 7) and even 8 packs degrade.
- Near-far rule (`NEAR_SPACING = 5`, line 16) further constrains any denser plan.
- Sharing a carrier pair between packs is TDMA, which the project rejected: at 2 Mbps even 2 packs per pair with 2 copies is 103 % of a 1 ms frame (`audit_out.txt` line 20, "C' ... FAIL"); AUDIT-2 B1 option 2 ("two packs per carrier pair, time-staggered ... needs a beacon, i.e. a downlink. Not v1") conflicts with ADR-0004 (one-way link) and ADR-0001/R3 latency.

**Plain statement: the current air interface cannot reach 32 channels in one venue. Its ceiling is 13 packs by carrier count and 8 packs by the Wi-Fi-gap argument that R1 depends on. 32 channels needs a different PHY plan (4 Mbps nRF54L15 and/or TDMA with a downlink, both named but not designed in AUDIT-2 B1/B5), not more racks.** The rack architecture, which only adds cost linearly, is the lesser of the two scaling problems.

---

## 6. Cost-structure lessons for the next attempt

1. **Cost the receiver end before the first rack ADR, and put a cap in SPEC.** SPEC/AUDIT had a pack cap (PK-12 <= $35) but "no per-receiver cap ... so none asserted" (`audit_out.txt` line 292, repeated in ADR-0014). Q14's "$150-250 for the receiver" was a guess that nobody turned into a requirement, so £1,501 could not fail a test. Every rack ADR says "R12: pack BOM unchanged" and treats rack cost as out of scope (ADR-0016, ADR-0021 requirement tables).
2. **Treat board area as a cost line with an owner.** The width came from a receiver-layout comment written before any rack mechanics existed (`hw/rx/layout_rx.py:39`), the depth from "fill the case" (RK-7a). The alternative ("narrow strip + host tray") was listed and never priced. A 10-minute area-x-layers estimate at #33 would have shown the 412 x 321.5 mm 4-layer board was 20 % of the rack.
3. **Do not let a vendor board dictate your PCB.** Half the main board depth exists to carry the CM4IO's four mounting holes. Mount vendor boards to the chassis, not to the RF backplane.
4. **Do not put RF distribution on the backplane unless the backplane is already 4-layer for another reason.** The Wilkinson copper is what makes the big board 4-layer, ENIG and controlled impedance; and the receiver pitch then made the splitter 2.7 dB lossier than its own model. A 2 x 1:8 splitter card of ~60 cm2 plus the 16 jumpers that are already in the BOM separates the two problems.
5. **Treat "1U" as a preference ranked 9th, not a tolerance budget.** 3.39 mm lid clearance, 1.65 mm side clearance, flat mezzanines, a £140.76 extrusion and an unresolved lug interference (open risk 18) all came from honouring one word in R9 to the millimetre, while R12 (cost) was ranked 12th but is what killed the project. When a lower-ranked requirement starts driving the cost of a higher-ranked one, stop-and-ask.
6. **Owner-fixed parts still need a price flag.** The case and CM4 were "fixed by the owner" (RK-7k) at £220 together against £139 in the earlier estimate; the agents reported it rather than asking whether the owner knew the delta.
7. **Separate venue infrastructure from the product.** £605 of the £1,501 (40 %) is antennas, coax and stands: a consequence of R1 under UK power, not of the rack. Reporting them inside "rack cost" made the receiver look worse than it is and hid that the electronics are ~£500. The shopping list did mark the stands as an optional cut; the headline number did not.
8. **Re-run the cost audit whenever a layout PR changes a board's area or a part's quantity break.** The PCB line went £25 -> £40 -> £300 across two PRs; the £300 is still an estimate because "the JLC quote page needs a browser". The project closed on a number that was 23 % estimate (£343.90 of £1,501.50 in E lines) and whose largest component had never been quoted.
9. **Design the receiver for the venue's spectrum ceiling first.** 13 carrier pairs is the whole band; an 8-channel rack that cannot be joined by a second one in the same house is a product for one size of show. The channel-count ceiling should have been in SPEC next to R9.
10. **Cheap receiver pattern to try next time:** one radio module per channel on a 2-layer power/UART bus board (no RF copper), one small 4-layer splitter card or an off-the-shelf divider plus a pad, a £15-30 USB-UART/host bridge driving the booth laptop (or a Pi Zero 2 W with Wi-Fi disabled), a generic case, XLRs on a flying rear strip. All of those pieces already exist in this repo's BOMs; only the big board does not.
