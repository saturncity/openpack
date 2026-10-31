"""1U rear panel for the receiver rack (RK-1), PRINTED in 3 segments for a 180 x 180 mm bed (Bambu A1 mini),
joined by two printed backing strips: 4x M3 bolts from the front into M3 heat-set inserts per seam.
Run: python mech/panel.py -> mech/build/panel_seg{0,1,2}.stl, panel_strip{0,1}.stl, panel_full.step
Axes: x along the panel, y up, z through it; front face z=0 (on the bed), ear pads and strips behind (z>0)."""
import cadquery as cq
from pathlib import Path

W, H, T = 482.6, 44.45, 3.0            # EIA-310 1U
EAR_PAD_T, EAR_PAD_X0 = 5.0, 222.0      # panel is 5 mm thick from |x| >= 222 (rack screws)
EDGE_MARGIN, BED, BED_MARGIN = 3.0, 180.0, 5.0
EAR_X, EAR_Y, EAR_D = 232.55, 15.875, 6.5   # rack-ear holes (M6 clearance)
XLR_D, XLR_PITCH, XLR_X0 = 24.0, 38.0, -208.0   # Neutrik D-size cutout
XLR_SCREW = (19.0, 24.0, 3.2)          # M3 pair, diagonal: dx, dy, dia
BNC_D, BNC_X = 9.5, (90.0, 108.0)
RJ45 = (16.0, 14.0, 130.0)             # w, h, x
USBC = (9.4, 3.6, 152.0)
DC_D, DC_X = 11.0, 172.0
LED_D, LED_X = 3.1, (196.0, 204.0, 212.0)    # power, rack status, host link
SEAMS = (-75.0, 77.6)                  # in gaps between cutouts (checked by tests)
BOLT_DX, BOLT_Y, BOLT_D = 3.4, 17.4, 3.4
INSERT_D, STRIP_T, INSERT_DEPTH, STRIP_PAD_HX, STRIP_BAR_HX = 4.2, 6.0, 4.4, 7.1, 3.0
OUT = Path(__file__).parent / "build"

def cutouts():
    """[(name, 'c'|'r', x, y, d | (w, h))] in panel coords, origin at panel centre"""
    c = [(f"ear{i}", "c", sx * EAR_X, sy * EAR_Y, EAR_D) for i, (sx, sy) in enumerate((a, b) for a in (-1, 1) for b in (-1, 1))]
    dx, dy, d = XLR_SCREW
    for i in range(8):
        x = XLR_X0 + i * XLR_PITCH
        c += [(f"xlr{i}", "c", x, 0, XLR_D), (f"xlr{i}a", "c", x - dx / 2, -dy / 2, d), (f"xlr{i}b", "c", x + dx / 2, dy / 2, d)]
    c += [(f"bnc{i}", "c", x, 0, BNC_D) for i, x in enumerate(BNC_X)] + [("dc", "c", DC_X, 0, DC_D)]
    c += [(f"led{i}", "c", x, 0, LED_D) for i, x in enumerate(LED_X)]
    c += [("rj45", "r", RJ45[2], 0, RJ45[:2]), ("usbc", "r", USBC[2], 0, USBC[:2])]
    c += [(f"bolt{i}{j}{k}", "c", s + sx * BOLT_DX, sy * BOLT_Y, BOLT_D) for i, s in enumerate(SEAMS) for j, sx in enumerate((-1, 1)) for k, sy in enumerate((-1, 1))]
    return c

def cutter(kind, x, y, s, t=T + EAR_PAD_T):
    w = cq.Workplane("XY").workplane(offset=-1).center(x, y)
    return (w.circle(s / 2) if kind == "c" else w.rect(*s)).extrude(t + 1)

def bbox(kind, x, y, s):
    w, h = (s, s) if kind == "c" else s
    return x - w / 2, x + w / 2, y - h / 2, y + h / 2

def box(x0, x1, y0, y1, z0, z1):
    return cq.Workplane("XY").box(x1 - x0, y1 - y0, z1 - z0, centered=False).translate((x0, y0, z0))

def full():
    p = box(-W / 2, W / 2, -H / 2, H / 2, 0, T)
    for sx in (-1, 1):   # ear pads, behind the face
        p = p.union(box(min(sx * EAR_PAD_X0, sx * W / 2), max(sx * EAR_PAD_X0, sx * W / 2), -H / 2, H / 2, T - 0.1, EAR_PAD_T))
    for _, k, x, y, s in cutouts():
        p = p.cut(cutter(k, x, y, s))
    return p

def segments():
    xs = (-W / 2, *SEAMS, W / 2)
    f = full()
    return [f.intersect(box(xs[i], xs[i + 1], -H, H, -1, 10)) for i in range(3)]

def strips():
    out = []
    for s in SEAMS:   # H-shaped: bar along the seam + a pad at each bolt pair; heat-set insert pockets open to the back
        b = box(s - STRIP_BAR_HX, s + STRIP_BAR_HX, -BOLT_Y, BOLT_Y, T, T + STRIP_T)
        for sy in (-1, 1):
            b = b.union(box(s - STRIP_PAD_HX, s + STRIP_PAD_HX, sy * BOLT_Y - 3.7, sy * BOLT_Y + 3.7, T, T + STRIP_T))
        for sx in (-1, 1):
            for sy in (-1, 1):
                x, y = s + sx * BOLT_DX, sy * BOLT_Y
                b = b.cut(cq.Workplane("XY").workplane(offset=T + STRIP_T - INSERT_DEPTH).center(x, y).circle(INSERT_D / 2).extrude(INSERT_DEPTH + 1))
                b = b.cut(cq.Workplane("XY").workplane(offset=T - 1).center(x, y).circle(BOLT_D / 2).extrude(STRIP_T))
        out.append(b)
    return out

def parts():
    return {**{f"seg{i}": s for i, s in enumerate(segments())}, **{f"strip{i}": s for i, s in enumerate(strips())}}

def export():
    OUT.mkdir(exist_ok=True)
    for k, v in parts().items():
        cq.exporters.export(v, str(OUT / f"panel_{k}.stl"), tolerance=0.02, angularTolerance=0.1)
    cq.exporters.export(full(), str(OUT / "panel_full.step"))

if __name__ == "__main__":
    export()
