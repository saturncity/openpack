# mech

CadQuery pack enclosure (`pack.py`) and 1U rear panel (`panel.py`), all printed. Parameters sit at the top of each file; the PCB is a placeholder envelope until #31.

    pip install cadquery trimesh rtree matplotlib
    python mech/pack.py && python mech/panel.py   # STL/STEP -> mech/build/ (gitignored)
    python mech/render.py                         # PNGs -> mech/renders/
    pytest tests/mech                             # interference, wall >= 1.6, overhang, 180 mm bed, PrusaSlicer (skips if absent)

Pack body 96 x 62 x 22.8 mm (PK-11 limit 100 x 65 x 25), printed clip excluded. 31 mm whip exits the top face >= 40 mm from the cell (PK-5).

Print note (Bambu A1 mini, 180 x 180 x 180, 0.4 mm nozzle, PETG on textured PEI, no enclosure needed): nothing needs supports. Base floor-down; lid inner-face-down; door outer-face-down (snap arms up); clip on its side (y up) so layers run along the spring arm; panel segments front-face-down, strips back-face-up. Panel = 3 segments (166/153/164 mm) + 2 backing strips, M3 bolts from the front into heat-set inserts; ears 5 mm thick.
