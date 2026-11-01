"""Rack main-board footprints -> hw/rack/openpack.pretty/*.kicad_mod (run by hw/rack/layout.py). Library nickname
"openpack", as hw/rack/backplane.py names them. Every dimension below is read off the drawing named; frame: KiCad
footprint mm, y down. For the panel connectors "panel" is the rear-panel inner face, which the board's rear edge
meets (BOARD_EDGE_Y: the edge of the board relative to the footprint origin, used by layout.py).

Neutrik NC3MAH(-0): Neutrik drawing ST-NC3MAH-0 rev C (13.01.10, neutrik.com/media/8309, read 2026-11-01) and its DXF
(neutrik.com/media/11747, scale 3:1, circle centres read numerically). "PCB-Layout (component side)": contacts 2, 3, 1
left to right in one row 17.78 from the panel line, 3.81 pitch; ground contact G 12.70 from the panel; two housing pegs
Ø1.6 at (+3.81, 8.89) and (-3.81, 3.81) from the panel. Ø1.6 holes for 1, 2 and the pegs, Ø1.2 for 3 and G. Body Ø22,
18.6 deep behind the panel, nose 2.7 in front; panel cut-out Ø22 + 2 x Ø3.2 at (+-9.9, +-9.9) diagonal (rear side view).
The axis sits 11.0 above the board top (Ø22 body resting on the board, front view).

TE Connectivity 5415025-1 (coordinator pick, #34; LCSC C5164649): TE customer drawing C-5415025 rev A2 (19JAN2020, read
from the JLC/LCSC record 2026-11-01). "PCB configuration": 4 x Ø2.11 holes on a 6.60 mm square (body pins Ø1.27), centre
contact Ø1.17 hole (pin Ø0.97) in the middle of the square. Side view: front face to centre pin 22.63, front face to the
flange 15.32, flange 0.89 thick, overall 27.64; axis 6.15 above the board; body 11.66 tall. 1/2-28 UNEF thread in front
of the flange; recommended panel cut-out Ø12.83 with a flat 5.64 from the centre (11.91 across). The flange's front face
sits at the board edge (the panel's inner face), so the centre pin is 22.63 - 15.32 = 7.31 into the board.

LTST-S270: Lite-On LTST-S270KGKT/KRKT data sheet DS22-2000-226 rev I (LCSC C125113 / C125114 records): side-looking
chip LED 1.65 long x 0.60, lens 1.15 deep; "Suggest soldering pad dimensions" 1.10 x 1.10 pads with a 0.90 gap (pad
centres 2.00 apart). Pad 1 = cathode (the symbol's K), lens towards -y (the board edge after placement).

Qorvo QPQ1907: "QPQ1907 Data Sheet 040820" p.6 "Recommended land pattern" (top view): 5 pads 0.254 x 0.330, pin 1 at
(-0.495, 0), the others at x 0 / +0.495, y +-0.2855; mask openings 0.354 x 0.430 (0.05 margin). Numbering per JESD 95-1
(counter-clockwise from pin 1, top view): 2 (0, +0.2855), 3 (+0.495, +0.2855), 4 (+0.495, -0.2855), 5 (0, -0.2855) in
KiCad's y-down frame. Pin 1 = INPUT, 4 = OUTPUT, 2/3/5 GND (p.3).

Microstrip_NetTie: the schematic's TL parts (Wilkinson arms, 50 ohm feeds) are copper, not parts. The footprint is a
1.0 mm net tie (two 0.16 mm pads 0.8 apart joined by a 0.16 mm copper bar, net_tie_pad_groups "1, 2") placed where the line starts; the line
itself is a track of the far-end net drawn by layout.py at the width and length hw/rack/layout.py RF computes (#95 open
item "give the TL net-ties real track geometry"). Excluded from BOM and position files.

PinSocket_2x13_P2.54mm_Key14: KiCad's PinSocket_2x13_P2.54mm_Vertical with pad 14 deleted (the Samtec
SSW-113-01-G-D-14 has no contact there) and "KEY" on the silk, as hw/rx/footprints_rx.py does for the header.
"""
import importlib.util
import os
import pathlib

HERE = pathlib.Path(__file__).resolve().parent
LIB = HERE / "openpack.pretty"

_spec = importlib.util.spec_from_file_location("hw_pack_footprints_r", HERE.parent / "pack" / "footprints.py")
pk = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(pk)
_spec = importlib.util.spec_from_file_location("hw_rx_footprints_r", HERE.parent / "rx" / "footprints_rx.py")
rxf = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rxf)

# ---- mechanical facts layout.py / mech/rack.py use (origin = footprint origin, y into the board) ----
NC3MAH = dict(panel_y=-17.78, body_d=22.0, body_depth=18.6, nose=2.7, axis_h=11.0, flange=19.8,
              cutout_d=22.0, screw=(9.9, 3.2))
BNC_TE = dict(panel_y=-7.31, body_w=11.66, body_depth=27.64 - 15.32, axis_h=6.15, front_len=15.32,
              cutout_d=12.83, cutout_flat=5.64, max_panel=15.32 - 10.67)


def _npth(x, y, d):
    return (f'  (pad "" np_thru_hole circle (at {x:.4f} {y:.4f}) (size {d} {d}) (drill {d}) '
            f'(layers "*.Cu" "*.Mask"))\n')


def nc3mah():
    py = NC3MAH["panel_y"]
    b = pk._text("Reference", "REF**", 0, 2.6, "F.SilkS", size=1.0)
    b += pk._text("Value", "NC3MAH", 0, -9.0, "F.Fab")
    # body behind the panel (fab), courtyard on the board side only
    b += pk._rect(-11.0, py, 11.0, py + NC3MAH["body_depth"], "F.Fab")
    b += pk._rect(-11.25, py + 0.3, 11.25, py + NC3MAH["body_depth"] + 0.6, "F.CrtYd", 0.05)
    b += pk._line(-11.12, py + 0.4, -11.12, py + NC3MAH["body_depth"] + 0.12, "F.SilkS", 0.12)
    b += pk._line(11.12, py + 0.4, 11.12, py + NC3MAH["body_depth"] + 0.12, "F.SilkS", 0.12)
    b += pk._line(-11.12, py + NC3MAH["body_depth"] + 0.12, 11.12, py + NC3MAH["body_depth"] + 0.12, "F.SilkS", 0.12)
    b += pk._fp_text("panel", 0, py + 1.2, "F.Fab", 0.8)
    b += pk._tht("2", -3.81, 0, 2.6, 1.6)
    b += pk._tht("3", 0.0, 0, 2.0, 1.2)
    b += pk._tht("1", 3.81, 0, 2.6, 1.6, shape="rect")
    b += pk._tht("G", 0.0, -5.08, 2.0, 1.2)
    b += _npth(3.81, py + 8.89, 1.6)
    b += _npth(-3.81, py + 3.81, 1.6)
    # pin labels on the silk next to the hot / cold pins
    b += pk._fp_text("2", -3.81, 2.2, "F.SilkS", 0.8)
    b += pk._fp_text("3", 0.0, 2.2, "F.SilkS", 0.8)
    return pk._wrap("Neutrik_NC3MAH", "Neutrik NC3MAH(-0) male XLR, horizontal PCB; drawing ST-NC3MAH-0 rev C PCB layout",
                    b, attr="through_hole")


def bnc_te():
    py = BNC_TE["panel_y"]
    b = pk._text("Reference", "REF**", 0, 6.8, "F.SilkS", size=1.0)
    b += pk._text("Value", "5415025-1", 0, -12.0, "F.Fab", size=0.8)
    w = BNC_TE["body_w"] / 2
    b += pk._rect(-w, py, w, py + BNC_TE["body_depth"], "F.Fab")
    b += pk._rect(-6.4, py - BNC_TE["front_len"], 6.4, py, "F.Fab")     # thread + nose, outside the board
    b += pk._rect(-w - 0.5, py + 0.3, w + 0.5, py + BNC_TE["body_depth"] + 0.5, "F.CrtYd", 0.05)
    b += pk._line(-w - 0.12, py + 0.4, -w - 0.12, py + BNC_TE["body_depth"] + 0.12, "F.SilkS", 0.12)
    b += pk._line(w + 0.12, py + 0.4, w + 0.12, py + BNC_TE["body_depth"] + 0.12, "F.SilkS", 0.12)
    b += pk._tht("1", 0.0, 0.0, 1.9, 1.17)
    for x in (-3.30, 3.30):
        for y in (-3.30, 3.30):
            b += pk._tht("2", x, y, 3.1, 2.11)
    return pk._wrap("BNC_TE_5415025-1_RA", "TE 5415025-1 right-angle PCB BNC, 1/2-28 bulkhead thread; drawing C-5415025 "
                    "rev A2 PCB configuration", b, attr="through_hole")


def ltst_s270():
    b = pk._text("Reference", "REF**", 0, 1.4, "F.SilkS", size=0.8)
    b += pk._text("Value", "LTST-S270", 0, 2.4, "F.Fab", size=0.5)
    b += pk._rect(-0.825, -0.6, 0.825, 0.0, "F.Fab")                        # body; lens to -y (0.47 more)
    b += pk._rect(-0.3, -1.07, 0.3, -0.6, "F.Fab")
    b += pk._rect(-1.8, -1.25, 1.8, 0.8, "F.CrtYd", 0.05)
    b += pk._line(-1.75, 0.75, -1.75, -0.75, "F.SilkS", 0.15)               # cathode bar beside pad 1
    b += pk._smd("1", -1.0, 0.0, "rect", 1.1, 1.1)
    b += pk._smd("2", 1.0, 0.0, "rect", 1.1, 1.1)
    return pk._wrap("LED_LiteOn_LTST-S270", "Lite-On LTST-S270 side-looking chip LED; DS22-2000-226 suggested pads", b)


QPQ_PADS = {"1": (-0.495, 0.0), "2": (0.0, 0.2855), "3": (0.495, 0.2855), "4": (0.495, -0.2855), "5": (0.0, -0.2855)}


def qpq1907():
    b = pk._text("Reference", "REF**", 0, -1.4, "F.SilkS", size=0.8)
    b += pk._text("Value", "QPQ1907", 0, 1.6, "F.Fab", size=0.5)
    b += pk._rect(-0.7, -0.6, 0.7, 0.6, "F.Fab")
    b += pk._rect(-1.0, -0.85, 0.95, 0.85, "F.CrtYd", 0.05)
    # pin-1 dot outside the body, on the input side
    b += ('  (fp_circle (center -1.15 -0.75) (end -1.0 -0.75) (stroke (width 0.12) (type solid)) (fill yes) '
          '(layer "F.SilkS"))\n')
    for name, (x, y) in QPQ_PADS.items():
        b += (f'  (pad "{name}" smd rect (at {x:.4f} {y:.4f}) (size 0.254 0.33) (layers "F.Cu" "F.Paste" "F.Mask") '
              f'(solder_mask_margin 0.05))\n')
    return pk._wrap("Qorvo_QPQ1907_LGA5_1.4x1.2mm_datasheet_land_pattern",
                    "Qorvo QPQ1907 BAW filter 1.4 x 1.2 mm LGA-5; Data Sheet 040820 p.6 recommended land pattern", b)


def microstrip_nettie():
    b = pk._text("Reference", "REF**", 0, -0.6, "F.Fab", size=0.4)
    b += pk._text("Value", "TL", 0, 0.6, "F.Fab", size=0.4)
    b += '  (net_tie_pad_groups "1, 2")\n'
    b += '  (pad "1" smd rect (at -0.4 0) (size 0.16 0.16) (layers "F.Cu"))\n'
    b += '  (pad "2" smd rect (at 0.4 0) (size 0.16 0.16) (layers "F.Cu"))\n'
    b += ('  (fp_poly (pts (xy -0.48 -0.08) (xy 0.48 -0.08) (xy 0.48 0.08) (xy -0.48 0.08)) (stroke (width 0) (type solid)) '
          '(fill yes) (layer "F.Cu"))\n')
    return pk._wrap("Microstrip_NetTie", "Microstrip start: 0.2 mm net tie, line drawn as a track (hw/rack/layout.py)",
                    b, attr="smd exclude_from_pos_files exclude_from_bom")


SOCK_SRC = ("Connector_PinSocket_2.54mm.pretty", "PinSocket_2x13_P2.54mm_Vertical")


def socket_key14():
    base = pathlib.Path(os.environ.get("KICAD10_FOOTPRINT_DIR", "/usr/share/kicad/footprints"))
    t = (base / SOCK_SRC[0] / f"{SOCK_SRC[1]}.kicad_mod").read_text()
    t = t.replace(f'(footprint "{SOCK_SRC[1]}"', '(footprint "PinSocket_2x13_P2.54mm_Key14"', 1)
    i = t.index('(pad "14"')
    at = t[i:i + 200].split("(at ")[1].split(")")[0].split()
    t = rxf._drop_sexp(t, i)
    assert '(pad "14"' not in t
    x, y = float(at[0]), float(at[1])
    mark = "".join(f'\t(fp_text user "KEY" (at {x} {y} 90) (layer "{layer}")\n'
                   f'\t\t(effects (font (size 0.8 0.8) (thickness 0.15)){" (justify mirror)" if layer[0] == "B" else ""}))\n'
                   for layer in ("F.SilkS", "B.SilkS"))
    return t.rstrip()[:-1] + mark + ")\n"


FOOTPRINTS = {"Neutrik_NC3MAH": nc3mah, "BNC_TE_5415025-1_RA": bnc_te, "LED_LiteOn_LTST-S270": ltst_s270,
              "Qorvo_QPQ1907_LGA5_1.4x1.2mm_datasheet_land_pattern": qpq1907, "Microstrip_NetTie": microstrip_nettie,
              "PinSocket_2x13_P2.54mm_Key14": socket_key14}


def write_lib():
    LIB.mkdir(exist_ok=True)
    for name, f in FOOTPRINTS.items():
        (LIB / f"{name}.kicad_mod").write_text(f())
    return LIB


if __name__ == "__main__":
    print(write_lib())
