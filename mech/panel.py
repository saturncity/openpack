"""1U rear panel for the receiver rack (RK-1): 8 XLR male, 2 BNC, RJ45, USB-C, 12 V DC. Run: python mech/panel.py"""
import cadquery as cq
from pathlib import Path

W, H, T = 482.6, 44.45, 3.0            # EIA-310 1U
EAR_X, EAR_Y, EAR_D = 232.55, 15.875, 7.1   # rack-ear holes
XLR_D, XLR_PITCH, XLR_X0 = 24.0, 34.0, -208.0   # Neutrik D-size cutout; flange 26 x 31
XLR_SCREW = (19.0, 24.0, 3.2)          # M3 pair, diagonal, offsets dx, dy, dia
BNC_D, BNC_X = 9.5, (70.0, 90.0)
RJ45 = (16.0, 14.0, 125.0)             # w, h, x
USBC = (9.4, 3.6, 150.0)
DC_D, DC_X = 11.0, 175.0
OUT = Path(__file__).parent / "build"

def panel():
    p = cq.Workplane("XY").box(W, H, T, centered=(True, True, False))
    holes = [(sx * EAR_X, sy * EAR_Y, EAR_D) for sx in (-1, 1) for sy in (-1, 1)]
    dx, dy, d = XLR_SCREW
    for i in range(8):
        x = XLR_X0 + i * XLR_PITCH
        holes += [(x, 0, XLR_D), (x - dx / 2, -dy / 2, d), (x + dx / 2, dy / 2, d)]
    holes += [(x, 0, BNC_D) for x in BNC_X] + [(DC_X, 0, DC_D)]
    for x, y, dia in holes:
        p = p.cut(cq.Workplane("XY").center(x, y).circle(dia / 2).extrude(T))
    for w, h, x in (RJ45, USBC):
        p = p.cut(cq.Workplane("XY").center(x, 0).rect(w, h).extrude(T))
    return p

def export():
    OUT.mkdir(exist_ok=True)
    p = panel()
    cq.exporters.export(p, str(OUT / "panel.stl"), tolerance=0.02, angularTolerance=0.1)
    cq.exporters.export(p, str(OUT / "panel.step"))
    return p

if __name__ == "__main__":
    export()
