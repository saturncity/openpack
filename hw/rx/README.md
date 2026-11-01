# hw/rx

Receiver sub-board (one per pack, eight per rack), captured in SKiDL (`rx.py`). Decisions: ADR-0021 (module: BT40E, no FEM; the pack keeps ADR-0007's BT40NE), ADR-0011 (antenna logic), ADR-0014 (this board: backplane pinout, GPIO map, DAC, balanced driver).

- `python hw/rx/rx.py` (venv with `skidl==3.0.0`) runs ERC, then writes `out/rx.net` (KiCad netlist), `out/bom.csv` (USD + GBP + UK distributor per line, printed by `audit.py`), `out/sch/*.kicad_sch` (KiCad 9, one sheet per block: power, mcu, rf, dac, driver) and `out/svg/*.svg`. `--no-sch` skips the schematic render.
- `symbols_rx.py` writes `openpack_rx.kicad_sym` (the pack's symbols plus PCM5102A, PE4259, U.FL, BAV99, TVS, backplane header). `prices.py` holds qty-100 prices with sources.
- Checks: `tests/test_rx_sch.py` (ERC 0/0, BOM current, UART/I2S/ANT_SEL pads, straps, polarity, backplane pinout = ADR table) and `tests/test_spice_rx_driver.py` (`hw/spice/rx_driver.cir`: level, headroom, flatness, CM and swing vs rails, Zout, hum, noise; `rx_driver_load.cir`: phase margin and step into 10 nF + 600 ohm, phantom short; `rx_driver_power.cir`: power cycle through the mute relay).

## PCB (#34)

- `python3 hw/rx/layout_rx.py` (system python with KiCad 10 `pcbnew`): `out/rx.net` → placement → RF pre-route + via fence → GND fan-out → routing (the pack's `hw/pack/router.py`) → pours → `kicad-cli` DRC (refill saved) → `outputs_rx.py` (gerbers, drill, `bom_jlc.csv`, `cpl_jlc.csv`, `rx.step`, `mech.json`, renders of every layer). About 40 s.
- `footprints_rx.py` writes `openpack.pretty` (BT40E from Fanstel p.11, TQ2SA, land pattern provisional). `rf_line.py` is the 2D field solve behind the 0.31 mm / 0.25 mm 50 Ω line (needs the `.ws` venv for numpy/scipy). `rx.kicad_dru` holds the JLC rules.
- Checks: `tests/test_rx_layout.py` (CI `pcb` job). The review is the receiver section of `hw/REVIEW.md`.
