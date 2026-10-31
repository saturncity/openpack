# hw/pack

The body-pack board is captured in SKiDL (`pack.py`). Decisions: ADR-0006 (front end), ADR-0007 (module), ADR-0012 (pinouts, bias filter, pad map).

- `python hw/pack/pack.py` (repo venv with `skidl` and `schematizer`) runs ERC, then writes `out/pack.net` (KiCad netlist), `out/bom.csv` (read by `audit.py` for PK-12), `out/sch/*.kicad_sch` (KiCad 9, one sheet per block) and `out/svg/*.svg` (previews). `--no-sch` skips the slow schematic render.
- `symbols.py` writes `openpack.kicad_sym`, box symbols built from datasheet pin tables. `prices.py` holds qty-100 prices, each with its source.
- Checks: `tests/test_pack_sch.py` (ERC clean, BOM current, key nets) and `tests/test_spice_preamp.py` (the same front end in ngspice).
- Footprints prefixed `openpack:` (BT40NE, SJ1-3543 jack, 18650 holder) don't exist yet. They come with layout.
