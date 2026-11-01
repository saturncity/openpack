"""Receiver project footprints -> hw/rx/openpack.pretty/*.kicad_mod (run by hw/rx/layout.py). Library nickname
"openpack", as the netlist names them (openpack:Fanstel_BT40E, openpack:Panasonic_TQ2SA).

BT40E: Fanstel "BLE 5.3, 802.15.4 Modules, BT40/F/E/N/NE" v1.08 p.11 (BT40E mechanical drawing, top view; v1.09 is the
same drawing). Datasheet coordinates: u = mm from the module's left edge (14.0 wide), v = mm up from the pad-end edge
(16.0 long).
  castellations 1-8 on the left edge (u = 0), 9-16 on the right edge (u = 14); pin 1 / 16 at v = 8.8, 1.10 mm pitch
  down to pin 8 / 9 at v = 1.1; 0.70 mm wide;
  LGA columns Z A B C D E at u = 3.25 + 1.5 k, F at 12.25 (1.75 from the right edge); rows 0..6 at v = 8.0 - 1.2 r
  (Z6 at 0.8); LGA pads 0.60 mm round, F6 0.6 x 0.6 square; H0..H3 1.5 x 1.5 at v = 10.0, u = 3.625 + 2.25 k;
  u.FL receptacle top right, centre (12.05, 14.6) (scaled from the top view; side view: 1.4 from the top edge).
  No PCB antenna: the u.FL is the only RF port, so there is no antenna keepout, only u.FL mating room.

TQ2SA: Panasonic "TQ relays" datasheet (c Panasonic 2019, LCSC C2684447 PDF) p.11, "2. Surface-mount terminal", SA type:
body 14 x 9 mm, 5.6 mm tall (seated), terminals 11.5 +-0.5 tip to tip; "Suggested mounting pad (Top view)": 1.0 x 2.94 mm
pads at 2.54 mm pitch, 9.56 mm between the two rows' pad centres (+-0.1). Schematic (top view): 10 9 8 7 6 on one side,
1..5 on the other, 10 opposite 1; coil 1 (+) / 10 (-).
"""
import importlib.util
import pathlib

HERE = pathlib.Path(__file__).resolve().parent
LIB = HERE / "openpack.pretty"

_spec = importlib.util.spec_from_file_location("hw_pack_footprints", HERE.parent / "pack" / "footprints.py")
pk = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(pk)

BT40E = dict(W=14.0, L=16.0, UFL=(12.05, 14.6))
TQ2SA = dict(BODY=(9.0, 14.0), ROW=9.56, PAD=(2.94, 1.0), PITCH=2.54, H=5.6)


def bt40e_pads():
    """(name, u, v, shape, sx, sy) in datasheet coordinates"""
    pads = []
    for n in range(1, 9):
        pads.append((str(n), 0.0, 8.8 - (n - 1) * 1.1, "rect", 1.6, 0.7))
    for n in range(9, 17):
        pads.append((str(n), 14.0, 1.1 + (n - 9) * 1.1, "rect", 1.6, 0.7))
    for k, col in enumerate("ZABCDE"):
        for r in range(7):
            pads.append((f"{col}{r}", 3.25 + 1.5 * k, 8.0 - 1.2 * r, "circle", 0.6, 0.6))
    for r in (3, 4, 5):
        pads.append((f"F{r}", 12.25, 8.0 - 1.2 * r, "circle", 0.6, 0.6))
    pads.append(("F6", 12.25, 8.0 - 1.2 * 6, "rect", 0.6, 0.6))
    for k in range(4):
        pads.append((f"H{k}", 3.625 + 2.25 * k, 10.0, "rect", 1.5, 1.5))
    return pads


def uv_to_fp(u, v):
    return u - BT40E["W"] / 2, BT40E["L"] / 2 - v


def bt40e():
    W, L = BT40E["W"], BT40E["L"]
    x0, x1, y0, y1 = -W / 2, W / 2, -L / 2, L / 2
    b = pk._text("Reference", "REF**", 0, y1 + 1.3, "F.SilkS", size=0.8)
    b += pk._text("Value", "BT40E", 0, 0, "F.Fab")
    b += pk._rect(x0, y0, x1, y1, "F.Fab")
    b += pk._rect(x0 - 1.05, y0 - 0.25, x1 + 1.05, y1 + 0.25, "F.CrtYd", 0.05)
    # silk: top edge and the pin-1 corner only (castellations sit on the outline)
    b += pk._line(x0 - 0.15, y0 - 0.15, x1 + 0.15, y0 - 0.15, "F.SilkS", 0.12)
    p1x, p1y = uv_to_fp(0.0, 8.8)
    b += f'  (fp_circle (center {p1x - 1.3:.3f} {p1y:.3f}) (end {p1x - 1.1:.3f} {p1y:.3f}) (stroke (width 0.12) (type solid)) (fill yes) (layer "F.SilkS"))\n'
    ux, uy = uv_to_fp(*BT40E["UFL"])
    b += f'  (fp_circle (center {ux:.3f} {uy:.3f}) (end {ux + 1.0:.3f} {uy:.3f}) (stroke (width 0.1) (type solid)) (layer "F.Fab"))\n'
    b += pk._fp_text("u.FL", ux - 2.0, uy, "F.Fab", 0.6)
    for name, u, v, shape, sx, sy in bt40e_pads():
        x, y = uv_to_fp(u, v)
        b += pk._smd(name, x, y, shape, sx, sy)
    return pk._wrap("Fanstel_BT40E", "Fanstel BT40E nRF5340 module, u.FL, no FEM, 14x16 mm; datasheet v1.08/v1.09 p.11", b)


def tq2sa():
    bw, bl = TQ2SA["BODY"]
    sx, sy = TQ2SA["PAD"]
    r, p = TQ2SA["ROW"] / 2, TQ2SA["PITCH"]
    b = pk._text("Reference", "REF**", 0, -bl / 2 - 1.0, "F.SilkS", size=0.8)
    b += pk._text("Value", "TQ2SA-12V", 0, 0, "F.Fab")
    b += pk._rect(-bw / 2, -bl / 2, bw / 2, bl / 2, "F.Fab")
    b += pk._rect(-max(r + sx / 2, 5.75) - 0.25, -bl / 2 - 0.25, max(r + sx / 2, 5.75) + 0.25, bl / 2 + 0.25, "F.CrtYd", 0.05)
    # silk: the body's short ends only (the pads reach under the body sides)
    b += pk._line(-bw / 2, -bl / 2 - 0.12, bw / 2, -bl / 2 - 0.12, "F.SilkS", 0.12)
    b += pk._line(-bw / 2, bl / 2 + 0.12, bw / 2, bl / 2 + 0.12, "F.SilkS", 0.12)
    b += pk._fp_text("coil", 0, -bl / 2 + 1.5, "F.Fab", 0.7)
    for k in range(5):
        y = -2 * p + k * p
        b += pk._smd(str(1 + k), -r, y, "rect", sx, sy)          # 1..5 down the left
        b += pk._smd(str(10 - k), r, y, "rect", sx, sy)          # 10..6 down the right (10 opposite 1)
    b += f'  (fp_circle (center {-r:.3f} {-2 * p - 1.1:.3f}) (end {-r + 0.2:.3f} {-2 * p - 1.1:.3f}) (stroke (width 0.12) (type solid)) (fill yes) (layer "F.SilkS"))\n'
    return pk._wrap("Panasonic_TQ2SA", "Panasonic TQ2SA DPDT relay, SA surface-mount terminals; TQ datasheet p.11 suggested mounting pad", b)


FOOTPRINTS = {"Fanstel_BT40E": bt40e, "Panasonic_TQ2SA": tq2sa}


def write_lib():
    LIB.mkdir(exist_ok=True)
    for name, f in FOOTPRINTS.items():
        (LIB / f"{name}.kicad_mod").write_text(f())
    return LIB


if __name__ == "__main__":
    print(write_lib())
