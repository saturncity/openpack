# mech

CadQuery pack enclosure (`pack.py`) and 1U rear panel (`panel.py`). Parameters sit at the top of each file; the PCB is a placeholder envelope until #31.

    pip install cadquery trimesh rtree matplotlib
    python mech/pack.py && python mech/panel.py   # STL/STEP -> mech/build/ (gitignored)
    python mech/render.py                         # PNGs -> mech/renders/
    pytest tests/mech                             # interference, wall >= 1.6, overhang, PrusaSlicer (skips if absent)

Pack: 96 x 62 x 24.9 mm incl. belt clip (PK-11 limit 100 x 65 x 25), PETG, 31 mm whip exits the top face >= 40 mm from the cell (PK-5).
Print orientation: base floor-down, lid and door inner-face-down, clip arm-down. The panel (482.6 mm) needs a large bed or an aluminium cut.
