"""Project footprints for the pack board -> hw/pack/openpack.pretty/*.kicad_mod (run by layout.py).

BT40NE: Fanstel "BT40/F/E/N/NE Product Specifications" v1.08, p.13 (BT40NE mechanical drawing) and p.9
(BT40F pad grid; "BT40N/NE has the same soldering pads as BT40F", p.15). Datasheet coordinates used below:
u = mm from the module's outer left edge (15.0 wide), v = mm up from the pad-end edge (29.9 long).
  castellations 1-8 on the left edge of the 14.0-wide pad section (u = 1.0), 9-16 on the right edge (u = 15.0),
  pin 1 / 16 at v = 8.8, 1.10 mm pitch down to pin 8 / 9 at v = 1.1;
  LGA columns Z A B C D E at u = 4.25 + 1.5 k, F at 13.25 (1.75 from the right edge); rows 0..6 at v = 8.0 - 1.2 r;
  LGA pads 0.60 mm round (F6 0.6 x 0.6 square); H0..H3 1.5 x 1.5 at v = 10.0, u = 4.625 + 2.25 k;
  shield ends at v = 19.0, antenna area v = 19.0..29.9 (10.9 mm); u.FL at u = 2.22, v = 29.9 - 13.8 = 16.1.
  p.20: "the antenna area of module shall extend 9.8 mm outside the edge of host PCB" -> board edge at v = 19.0.

SJ1-3543: Same Sky SJ1-354X datasheet (09/12/2024). BT1 is two wire pads for the cradle contacts (hw/REVIEW.md).
"""
import pathlib

HERE = pathlib.Path(__file__).resolve().parent
LIB = HERE / "openpack.pretty"

BT40 = dict(W=15.0, L=29.9, PAD_END=19.0, UFL=(2.22, 16.1))


def _bt40_pads():
    """(name, u, v, shape, sx, sy) in datasheet coordinates"""
    pads = []
    for n in range(1, 9):
        pads.append((str(n), 1.0, 8.8 - (n - 1) * 1.1, "rect", 1.6, 0.7))
    for n in range(9, 17):
        pads.append((str(n), 15.0, 1.1 + (n - 9) * 1.1, "rect", 1.6, 0.7))
    for k, col in enumerate("ZABCDE"):
        for r in range(7):
            pads.append((f"{col}{r}", 4.25 + 1.5 * k, 8.0 - 1.2 * r, "circle", 0.6, 0.6))
    for r in (3, 4, 5):
        pads.append((f"F{r}", 13.25, 8.0 - 1.2 * r, "circle", 0.6, 0.6))
    pads.append(("F6", 13.25, 8.0 - 1.2 * 6, "rect", 0.6, 0.6))
    for k in range(4):
        pads.append((f"H{k}", 4.625 + 2.25 * k, 10.0, "rect", 1.5, 1.5))
    return pads


def bt40_uv_to_fp(u, v):
    """datasheet (u, v) -> footprint (x, y), origin at the module centre, KiCad y down"""
    return u - BT40["W"] / 2, BT40["L"] / 2 - v


def _line(x0, y0, x1, y1, layer, w=0.1):
    return f'  (fp_line (start {x0:.3f} {y0:.3f}) (end {x1:.3f} {y1:.3f}) (stroke (width {w}) (type solid)) (layer "{layer}"))\n'


def _rect(x0, y0, x1, y1, layer, w=0.1):
    return (_line(x0, y0, x1, y0, layer, w) + _line(x1, y0, x1, y1, layer, w) +
            _line(x1, y1, x0, y1, layer, w) + _line(x0, y1, x0, y0, layer, w))


def _text(kind, txt, x, y, layer, hide=False, size=1.0):
    h = " (hide yes)" if hide else ""
    return (f'  (property "{kind}" "{txt}" (at {x:.3f} {y:.3f} 0) (layer "{layer}"){h}\n'
            f'    (effects (font (size {size} {size}) (thickness {size * 0.15:.3f}))))\n')


def _fp_text(txt, x, y, layer, size=0.8):
    return (f'  (fp_text user "{txt}" (at {x:.3f} {y:.3f} 0) (layer "{layer}")\n'
            f'    (effects (font (size {size} {size}) (thickness {size * 0.15:.3f}))))\n')


def _smd(name, x, y, shape, sx, sy):
    return (f'  (pad "{name}" smd {shape} (at {x:.4f} {y:.4f}) (size {sx} {sy}) '
            f'(layers "F.Cu" "F.Paste" "F.Mask"))\n')


def _tht(name, x, y, d, drill, shape="circle"):
    return (f'  (pad "{name}" thru_hole {shape} (at {x:.4f} {y:.4f}) (size {d} {d}) (drill {drill}) '
            f'(layers "*.Cu" "*.Mask"))\n')


def _wrap(name, descr, body, attr="smd"):
    return (f'(footprint "{name}" (version 20240108) (generator "openpack_footprints") (layer "F.Cu")\n'
            f'  (descr "{descr}")\n  (attr {attr})\n{body})\n')


def bt40ne():
    W, L = BT40["W"], BT40["L"]
    b = _text("Reference", "REF**", 0, -L / 2 - 1.2, "F.SilkS")
    b += _text("Value", "BT40NE", 0, 0, "F.Fab")
    x0, x1, y0, y1 = -W / 2, W / 2, -L / 2, L / 2
    ya = BT40["L"] / 2 - BT40["PAD_END"]          # antenna boundary (fp y)
    b += _rect(x0, y0, x1, y1, "F.Fab")
    b += _line(x0, ya, x1, ya, "F.Fab")
    b += _fp_text("ANTENNA: off board", 0, (y0 + ya) / 2, "F.Fab")
    b += _rect(x0 - 0.25, y0 - 0.25, x1 + 0.25, y1 + 0.25, "F.CrtYd", 0.05)
    # silk: pad-section outline only (the antenna overhangs the board edge)
    b += _line(x0 + 1.0 - 0.15, ya, x0 + 1.0 - 0.15, y1 + 0.15, "F.SilkS", 0.12)
    b += _line(x0 + 1.0 - 0.15, y1 + 0.15, x1 + 0.15, y1 + 0.15, "F.SilkS", 0.12)
    ux, uy = bt40_uv_to_fp(*BT40["UFL"])
    b += _fp_text("u.FL", ux + 2.2, uy, "F.Fab", 0.6)
    b += f'  (fp_circle (center {ux:.3f} {uy:.3f}) (end {ux + 0.6:.3f} {uy:.3f}) (stroke (width 0.1) (type solid)) (layer "F.Fab"))\n'
    for name, u, v, shape, sx, sy in _bt40_pads():
        x, y = bt40_uv_to_fp(u, v)
        if name.isdigit():   # castellations: long axis across the module edge
            b += _smd(name, x, y, "rect", sx, sy)
        else:
            b += _smd(name, x, y, shape, sx, sy)
    return _wrap("Fanstel_BT40NE", "Fanstel BT40NE nRF5340+nRF21540 module, 15x29.9 mm; datasheet v1.08 p.9/p.13; antenna area overhangs the board edge (p.20)", b)


# SJ1-3543: Same Sky "SJ1-354X" datasheet, 09/12/2024, p.2 (mechanical drawing + recommended PCB layout, top view).
# Body 12.0 W x 11.6 L x 9.6 H behind an M6x0.5 bushing 3.6 long; jack axis ~5.2 above the PCB (scaled from the
# front view, 9.6 body height, +-0.3). Layout: 8 x d1.50 holes in two columns, 3.00 and 8.00 behind the connector
# edge (= body front face), rows at +5 / +2.5 / 0 / -2.5 / -5. SJ1-3543 fits pins 1 sleeve, 2 tip, 3 ring;
# 4/5 (switches) are not populated on -3543, so those holes are left out. The three unnumbered holes take the
# housing's kinked anchor legs: plated, tied to GND in layout.py.
# Footprint frame: barrel axis along +x, connector edge (body front) at x = 0, body behind it; KiCad y down.
# (datasheet top view rotated 180 deg: its pin 3 at (8, +5) -> here (-8, +5) y-down)
JACK = dict(BODY=(-11.6, 0.0, -6.0, 6.0), BUSHING=3.6, BUSHING_D=6.0, H=9.6, AXIS=5.2, DRILL=1.5, PAD=2.2,
            PINS={"S": (-3.0, 0.0), "T": (-8.0, -2.5), "R": (-8.0, 5.0)},
            ANCHORS=[(-3.0, -5.0), (-3.0, 5.0), (-8.0, -5.0)])


def sj1_3543():
    x0, x1, y0, y1 = JACK["BODY"]
    b = _text("Reference", "REF**", (x0 + x1) / 2, y0 - 1.2, "F.SilkS")
    b += _text("Value", "SJ1-3543", (x0 + x1) / 2, 0, "F.Fab")
    b += _rect(x0, y0, x1, y1, "F.Fab")
    r = JACK["BUSHING_D"] / 2
    b += _rect(x1, -r, x1 + JACK["BUSHING"], r, "F.Fab")
    b += _fp_text("M6 bushing", x1 + 1.8, r + 0.8, "F.Fab", 0.5)
    b += _rect(x0 - 0.25, y0 - 0.25, x1 + JACK["BUSHING"] + 0.25, y1 + 0.25, "F.CrtYd", 0.05)
    b += _rect(x0 - 0.15, y0 - 0.15, x1, y1 + 0.15, "F.SilkS", 0.12)
    for n, (x, y) in JACK["PINS"].items():
        b += _tht(n, x, y, JACK["PAD"], JACK["DRILL"])
    for x, y in JACK["ANCHORS"]:
        b += _tht("MP", x, y, JACK["PAD"], JACK["DRILL"])
    return _wrap("SameSky_SJ1-3543", "Same Sky SJ1-3543 3.5 mm stereo jack, M6 bushing + nut, right angle THT (SJ1-354X datasheet 09/12/2024)", b, "through_hole")


def holder_leads():
    b = _text("Reference", "REF**", 0, -2.4, "F.SilkS")
    b += _text("Value", "18650 leads", 0, 2.4, "F.Fab")
    b += _tht("1", -1.75, 0, 2.2, 1.2, "rect")
    b += _tht("2", 1.75, 0, 2.2, 1.2)
    b += _fp_text("+", -1.75, -2.0, "F.SilkS", 1.0)
    b += _fp_text("-", 1.75, -2.0, "F.SilkS", 1.0)
    b += _rect(-3.2, -1.45, 3.2, 1.45, "F.CrtYd", 0.05)
    return _wrap("Cell_Wire_Pads", "Wire landing for the 18650 cradle contacts (MYOUNG MY-18650-04-J/05-J in mech/pack.py)", b, "through_hole")


FOOTPRINTS = {"Fanstel_BT40NE": bt40ne, "SameSky_SJ1-3543": sj1_3543, "Cell_Wire_Pads": holder_leads}


def write_lib():
    LIB.mkdir(exist_ok=True)
    for name, f in FOOTPRINTS.items():
        (LIB / f"{name}.kicad_mod").write_text(f())
    return LIB


if __name__ == "__main__":
    print(write_lib())
