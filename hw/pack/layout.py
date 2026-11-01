"""OpenPack body-pack PCB (issue #34): netlist -> hw/pack/pack.kicad_pcb, regenerable.

Run with the python that carries KiCad's pcbnew module (KiCad 10):
    python3 hw/pack/layout.py            # place, route, pour, DRC, fab outputs, renders
    python3 hw/pack/layout.py --no-out   # board + DRC only

Inputs: hw/pack/out/pack.net (SKiDL, `python hw/pack/pack.py`), mech/pack.py (outline and fit), footprints.py.
Frame: board mm, x right / y up, the same origin as mech/pack.py (enclosure plan centre). KiCad gets
X = 100 + x, Y = 100 - y.

Stackup (JLCPCB JLC04161H-7628, 1.6 mm): L1 sig + GND pour / L2 solid GND / L3 GND pour + power / L4 sig + GND pour.
Design choices and the review live in hw/REVIEW.md (pack section).
"""
import json, math, os, pathlib, re, shutil, subprocess, sys

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
import footprints, router  # noqa: E402

NETLIST = HERE / "out" / "pack.net"
BOARD = HERE / "pack.kicad_pcb"
PRO = HERE / "pack.kicad_pro"
FAB = HERE / "out" / "fab"
RENDER = HERE / "out" / "render"
KICAD_FP = pathlib.Path(os.environ.get("KICAD10_FOOTPRINT_DIR", "/usr/share/kicad/footprints"))
OX, OY = 100.0, 100.0

# ---------------------------------------------------------------------------------------------------------------
# Outline from mech/pack.py (enclosure interior x +-46.4, y +-29.4). The board sits beside the 18650 holder
# (holder y <= -8.2), clear of the M2 lid post at (-30, 26.9) (notch) and under-reaching the clip bosses
# (x = -32, top z 6.0) only with the module antenna, which rides above them (board top z 6.6).
# ---------------------------------------------------------------------------------------------------------------
BX0, BX1, BY0, BY1 = -28.0, 45.4, -6.5, 28.5
NOTCH = (-26.5, 24.0)          # x < -26.5 and y > 24.0 removed (lid post (-30, 26.9) d5 + 0.5)
OUTLINE = [(BX0, BY0), (BX1, BY0), (BX1, BY1), (NOTCH[0], BY1), (NOTCH[0], NOTCH[1]), (BX0, NOTCH[1])]

# JLC04161H-7628 (JLCPCB 4-layer impedance stackup)
STACKUP = [("F.Cu", "copper", 0.035, None), ("prepreg", "7628", 0.2104, 4.4), ("In1.Cu", "copper", 0.0152, None),
           ("core", "core", 1.065, 4.6), ("In2.Cu", "copper", 0.0152, None), ("prepreg", "7628", 0.2104, 4.4),
           ("B.Cu", "copper", 0.035, None)]

# ---------------------------------------------------------------------------------------------------------------
# 50 ohm microstrip on L1 over the L2 plane (Hammerstad-Jensen with Wheeler's thickness correction)
# ---------------------------------------------------------------------------------------------------------------
def microstrip_z0(w, h=0.2104, t=0.035, er=4.4):
    if t > 0:
        we = w + t / math.pi * (1 + math.log(4 * math.e / math.sqrt((t / h) ** 2 + (1 / math.pi / (w / t + 1.1)) ** 2)))
    else:
        we = w
    u = we / h
    a = 1 + math.log((u ** 4 + (u / 52) ** 2) / (u ** 4 + 0.432)) / 49 + math.log(1 + (u / 18.1) ** 3) / 18.7
    b = 0.564 * ((er - 0.9) / (er + 3)) ** 0.053
    eeff = (er + 1) / 2 + (er - 1) / 2 * (1 + 10 / u) ** (-a * b)
    f = 6 + (2 * math.pi - 6) * math.exp(-(30.666 / u) ** 0.7528)
    z = 60 / math.sqrt(eeff) * math.log(f / u + math.sqrt(1 + (2 / u) ** 2))
    return z, eeff


def width_for(z_target=50.0, **kw):
    lo, hi = 0.05, 2.0
    for _ in range(60):
        mid = (lo + hi) / 2
        if microstrip_z0(mid, **kw)[0] > z_target:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


# ---------------------------------------------------------------------------------------------------------------
# netlist
# ---------------------------------------------------------------------------------------------------------------
def sexp(text):
    tok = re.findall(r'\(|\)|"(?:[^"\\]|\\.)*"|[^\s()]+', text)
    stack, cur = [], []
    for t in tok:
        if t == "(":
            stack.append(cur)
            cur = []
        elif t == ")":
            done, cur = cur, stack.pop()
            cur.append(done)
        else:
            cur.append(t[1:-1] if t.startswith('"') else t)
    return cur[0]


def _find(node, key):
    return [c for c in node if isinstance(c, list) and c and c[0] == key]


def read_netlist(path=NETLIST):
    root = sexp(path.read_text())
    comps = {}
    for c in _find(_find(root, "components")[0], "comp"):
        ref = _find(c, "ref")[0][1]
        comps[ref] = dict(value=_find(c, "value")[0][1], footprint=_find(c, "footprint")[0][1])
        for f in _find(c, "fields"):
            for ff in _find(f, "field"):
                if _find(ff, "name") and _find(ff, "name")[0][1] == "MPN":
                    comps[ref]["mpn"] = ff[-1]
    nets = {}
    for n in _find(_find(root, "nets")[0], "net"):
        name = _find(n, "name")[0][1]
        nets[name] = [(_find(nd, "ref")[0][1], _find(nd, "pin")[0][1]) for nd in _find(n, "node")]
    return comps, nets


# ---------------------------------------------------------------------------------------------------------------
# placement: ref -> (x, y, rotation deg CCW). All parts on top (single-sided assembly).
# ---------------------------------------------------------------------------------------------------------------
B = (-1.0, 3.0)        # boost cell origin (TPS61023, TI SLVSF14B fig. 10-1 arrangement)
U1_POS = (-23.95, 15.2, 90)   # BT40NE: pad end at x = -9.0, antenna (v > 19) past the x = -28 edge, u.FL at (-25.1, 9.9)


def _b(dx, dy, rot):
    return (round(B[0] + dx, 4), round(B[1] + dy, 4), rot)


PLACE = {
    "U1": U1_POS,
    # --- power entry (bottom left) ---
    "BT1": (-21.5, -4.2, 0), "F1": (-21.5, -0.4, 0), "Q1": (-17.6, -0.4, 180), "R1": (-14.8, -1.6, 0),
    "R12": (-14.6, 5.4, 90), "R13": (-13.4, 5.4, 270), "C30": (-12.2, 5.4, 270),
    "SW1": (-3.5, 19.0, 0),
    # --- 3V3 LDO + module decoupling (top strip) ---
    "U5": (-3.0, 26.4, 0), "C4": (-6.0, 26.4, 270), "C5": (-0.2, 26.4, 270),
    "C29": (-10.6, 24.6, 180), "C32": (-12.9, 24.6, 180), "C28": (-11.0, 26.9, 180),
    "J3": (-18.5, 26.3, 0), "TP1": (-25.2, 26.6, 0), "TP2": (-23.1, 26.6, 0),
    # --- boost cell ---
    "U4": _b(0, 0, 0), "L1": _b(-0.2, -2.45, 0), "C1": _b(-3.0, -0.3, 180),
    "C2": _b(2.8, -0.2, 270), "C3": _b(5.0, -0.2, 270), "R2": _b(0.45, 1.75, 180), "R3": _b(-1.5, 1.75, 180),
    # --- ADC (U2 centre on the 0.05 offset so its 0.5 mm pads sit on the 0.1 mm routing grid) ---
    # analog supply/reference caps in two columns right of U2: AVDD (C20 100n, C19 1u), AREG (C22, C21), VREF (C23)
    "U2": (13.05, 2.05, 180),
    "C20": (16.2, 0.2, 270), "C22": (17.2, 0.2, 270), "C21": (18.45, 0.2, 270), "C23": (19.7, 0.2, 270), "C19": (14.6, -4.6, 90),
    "C25": (14.8, -1.55, 270), "C24": (16.2, -2.25, 270), "C27": (11.8, -1.55, 270), "C26": (9.95, -2.1, 270),
    "R11": (9.4, 2.8, 180),
    "C18": (11.6, 6.6, 90), "C16": (15.3, 7.4, 90), "C17": (14.0, 10.6, 180), "C15": (19.3, 5.0, 180),
    "U6": (18.9, -4.25, 90), "C6": (21.3, -4.8, 90), "C7": (16.5, -4.7, 90),
    # --- op-amp front end (U3) ---
    "U3": (27.0, 3.0, 0), "R9": (22.4, 4.5, 270), "R10": (22.4, 2.55, 270), "C12": (22.0, -0.8, 270),
    "C13": (31.7, 4.9, 0), "C14": (29.2, 6.5, 180),
    "R20": (27.0, -0.9, 0), "D6": (25.3, -3.4, 0), "C10": (30.6, -1.8, 180),
    "R6": (28.3, -4.5, 0), "R8": (29.85, -4.5, 270), "R7": (30.9, -4.5, 90), "C11": (32.2, -4.5, 270),
    "C9": (34.9, 5.2, 90), "D5": (35.9, 5.2, 90), "R5": (33.5, 5.2, 270),
    "R4": (33.0, 8.5, 0), "C8": (36.5, 8.5, 0),
    "J1": (45.4, 0.0, 0),
    # --- LEDs under the lid holes (8, 20) and (16, 20) ---
    "D1": (7.2, 20.0, 90), "D2": (8.8, 20.0, 90), "D3": (15.2, 20.0, 90), "D4": (16.8, 20.0, 90),
    "R14": (7.2, 23.0, 90), "R15": (8.8, 23.0, 90), "R16": (15.2, 23.0, 90), "R17": (16.8, 23.0, 90),
    # --- USB-C (mouth in the +x wall at y = 18, mech USB_Y) ---
    "J2": (43.0, 18.0, 90), "U7": (35.0, 18.0, 0), "R18": (38.0, 14.2, 0), "R19": (38.0, 22.0, 0), "C31": (35.0, 21.6, 0),
}

# preroutes: boost cell, TI fig. 10-1 (net, width, points relative to B)
BOOST_TRACKS = [
    ("BOOST_SW", 0.3, [(0.7125, 0), (0, 0), (0, -0.9), (0.875, -1.775), (0.875, -2.45)]),
    ("VSYS", 0.25, [(-0.7125, 0), (-0.7125, -0.5)]),
    ("VSYS", 0.4, [(-0.7125, -0.5), (-1.275, -1.1), (-1.275, -2.45)]),
    ("VSYS", 0.4, [(-2.225, -0.3), (-1.2, -0.3), (-0.7125, -0.5)]),
    ("+5V", 0.3, [(0.7125, 0.5), (1.3, 0.5), (1.55, 0.75), (2.8, 0.75)]),
    ("+5V", 0.4, [(2.8, 0.75), (5.0, 0.75)]),
    ("GND", 0.3, [(0.7125, -0.5), (1.3, -0.5), (1.65, -1.15), (2.8, -1.15)]),
    ("GND", 0.4, [(2.8, -1.15), (5.0, -1.15)]),
    ("BOOST_FB", 0.2, [(-1.02, 1.75), (-0.08, 1.75)]),
    ("BOOST_FB", 0.2, [(-1.02, 1.75), (-0.7125, 1.4), (-0.7125, 0.5)]),
    ("+5V", 0.25, [(0.93, 1.75), (2.2, 1.75), (2.8, 1.2)]),
]
BOOST_VIAS = [("GND", (2.8, -2.4)), ("GND", (5.0, -2.4)), ("GND", (-3.775, -1.6)), ("GND", (-1.98, 2.75))]
BOOST_TRACKS += [("GND", 0.3, [(2.8, -1.15), (2.8, -2.4)]), ("GND", 0.3, [(5.0, -1.15), (5.0, -2.4)]),
                 ("GND", 0.3, [(-3.775, -0.3), (-3.775, -1.6)]), ("GND", 0.25, [(-1.98, 1.75), (-1.98, 2.75)])]
# pads joined by the preroutes (so the router treats each cluster as one terminal)
BOOST_CLUSTERS = {"VSYS": [("U4", "2"), ("U4", "3"), ("L1", "1"), ("C1", "1")],
                  "+5V": [("U4", "6"), ("C2", "1"), ("C3", "1"), ("R2", "1")],
                  "BOOST_SW": [("U4", "5"), ("L1", "2")], "BOOST_FB": [("U4", "1"), ("R2", "2"), ("R3", "1")]}

# short pad-to-pad doglegs placed before routing: (ref, pad, ref, pad, axis, out). From pad A go `out` mm
# along `axis`, then straight to pad B. The ADC's supply/reference pins to their 100 nF/1 uF caps, J2 GND pads
# to the shield (no via between the USB pins).
DOGLEGS = [("U2", "24", "C25", "1", "y", -0.5), ("U2", "19", "C27", "1", "y", -0.5),
           ("J2", "B1", "J2", "SH", "y", 0.0), ("J2", "A1", "J2", "SH", "y", 0.0)]

# combs: an IC pin runs straight out (x) at its own height and drops onto each cap's pin 1 (caps in a row,
# pin 1 up, ordered so no two combs cross): PCM1840 AVDD, AREG (100 nF + 10 uF), VREF
# (pin, caps, bus y or None = the pin's own height). VCM divider: R6 -> bus above R8/R7/C11.
COMBS = [("U2", "1", [("C20", "1")], None), ("U2", "2", [("C22", "1"), ("C21", "1")], None), ("U2", "3", [("C23", "1")], None),
         ("R6", "2", [("R8", "1"), ("R7", "2"), ("C11", "1")], -3.55)]

# explicit fan-out vias for adjacent fine-pitch pins (staggered so the middle one passes between)
PIN_VIAS = [("U2", "21", (12.7, -1.3)), ("U2", "22", (13.3, -2.4)), ("U2", "23", (13.95, -1.3))]

POWER_NETS = {"BAT+", "BAT_F", "VBAT_RP", "VSYS", "+5V", "+3V3", "USB_VBUS"}
ANALOG_NETS = {"MIC", "PRE_NP", "PRE_INP", "PRE_INM", "PRE_CG", "PRE_OUTA", "PRE_OUTB", "VCM", "ADC_IN1P", "ADC_IN1M",
               "ADC_IN2P", "ADC_IN2M", "ADC_VREF", "ADC_AREG", "+5V_BIAS"}
NOISY_NETS = {"BOOST_SW", "VSYS", "BAT+", "BAT_F", "VBAT_RP", "USB_D+", "USB_D-", "USB_VBUS", "USB_CC1", "USB_CC2",
              "LED_BAT_OK", "LED_BAT_LOW", "LED_PEAK", "LED_CLIP", "UART_TX", "UART_RX", "SWDIO", "SWDCLK", "nRESET"}
ANALOG_RECT = (8.0, -6.5, 45.4, 11.5)          # tag 2: front end + ADC, noisy nets kept out on every layer
TAG_MODULE, TAG_ANALOG = 1, 2
VIA_D, VIA_DRILL = 0.6, 0.3
CLEAR = 0.15


def mm(v):
    import pcbnew
    return pcbnew.FromMM(v)


def V(x, y):
    import pcbnew
    return pcbnew.VECTOR2I(mm(OX + x), mm(OY - y))


def to_xy(p):
    import pcbnew
    return pcbnew.ToMM(p.x) - OX, OY - pcbnew.ToMM(p.y)


def fp_path(lib_fp):
    lib, name = lib_fp.split(":")
    d = footprints.LIB if lib == "openpack" else KICAD_FP / f"{lib}.pretty"
    return d, name


# ---------------------------------------------------------------------------------------------------------------
def build():
    import pcbnew as P
    footprints.write_lib()
    comps, nets = read_netlist()
    b = P.BOARD()
    b.SetCopperLayerCount(4)
    ds = b.GetDesignSettings()
    netinfo = {}
    for name in sorted(nets):
        ni = P.NETINFO_ITEM(b, name)
        b.Add(ni)
        netinfo[name] = ni
    # outline
    for (x0, y0), (x1, y1) in zip(OUTLINE, OUTLINE[1:] + OUTLINE[:1]):
        s = P.PCB_SHAPE(b)
        s.SetShape(P.SHAPE_T_SEGMENT)
        s.SetStart(V(x0, y0)); s.SetEnd(V(x1, y1))
        s.SetLayer(P.Edge_Cuts); s.SetWidth(mm(0.1))
        b.Add(s)
    fps = {}
    for ref, c in sorted(comps.items()):
        d, name = fp_path(c["footprint"])
        fp = P.FootprintLoad(str(d), name)
        if fp is None:
            raise SystemExit(f"footprint not found: {c['footprint']}")
        fp.SetReference(ref)
        fp.SetValue(c["value"])
        fp.SetFPID(P.LIB_ID(c["footprint"].split(":")[0], name))
        b.Add(fp)
        x, y, rot = PLACE[ref]
        fp.SetPosition(V(x, y))
        fp.SetOrientationDegrees(rot)
        fps[ref] = fp
        # silkscreen reference only on ICs and connectors; passives keep it on F.Fab
        if ref[0] in "RCLD" or ref.startswith("TP") or ref in ("F1", "Q1"):
            fp.Reference().SetVisible(False)
        else:
            fp.Reference().SetTextSize(P.VECTOR2I(mm(0.8), mm(0.8)))
            fp.Reference().SetTextThickness(mm(0.12))
        fp.Value().SetVisible(False)
    missing = set(PLACE) - set(comps)
    assert not missing, missing
    # nets onto pads (netlist pin -> footprint pad; USB4105 pairs and shield named differently)
    alias = {("J2", "S1"): ["SH"]}
    pair = {("J2", "A1"): ["B12"], ("J2", "B1"): ["A12"], ("J2", "A4"): ["B9"], ("J2", "B4"): ["A9"]}
    for name, nodes in nets.items():
        for ref, pin in nodes:
            names = alias.get((ref, pin), [pin]) + pair.get((ref, pin), [])
            hit = 0
            for p in fps[ref].Pads():
                if p.GetNumber() in names:
                    p.SetNet(netinfo[name]); hit += 1
            assert hit, (ref, pin)
    # QFN exposed pad: the footprint's paste-only sub-pads are unnumbered; EP is "25"
    return b, fps, netinfo, nets


FIXED = {"U1", "J1", "J2", "J3", "SW1", "D1", "D2", "D3", "D4", "U4", "L1", "C1", "C2", "C3", "R2", "R3", "U2", "U3", "BT1", "C12", "C15", "R9", "R10"}


def legalize(fps, margin=0.1, iters=400):
    """nudge movable parts until no courtyards overlap (anchors in FIXED stay put); moves snap to 0.05 mm"""
    import pcbnew as P
    order = list(PLACE)
    for _ in range(iters):
        moved = False
        for a, bref in courtyard_overlaps(fps):
            mv = bref if bref not in FIXED and (a in FIXED or order.index(bref) > order.index(a)) else a
            if mv in FIXED:
                continue
            other = a if mv == bref else bref
            A = fps[mv].GetCourtyard(P.F_CrtYd).BBox(); O = fps[other].GetCourtyard(P.F_CrtYd).BBox()
            ax0, ax1, ay0, ay1 = [P.ToMM(v) for v in (A.GetLeft(), A.GetRight(), A.GetTop(), A.GetBottom())]
            ox0, ox1, oy0, oy1 = [P.ToMM(v) for v in (O.GetLeft(), O.GetRight(), O.GetTop(), O.GetBottom())]
            cands = [(ox1 - ax0 + margin, 0), (-(ax1 - ox0 + margin), 0), (0, oy1 - ay0 + margin), (0, -(ay1 - oy0 + margin))]
            cands.sort(key=lambda d: abs(d[0]) + abs(d[1]))
            for dX, dY in cands:   # KiCad frame deltas
                nx0, nx1, ny0, ny1 = ax0 + dX - OX, ax1 + dX - OX, OY - (ay1 + dY), OY - (ay0 + dY)
                if nx0 < BX0 + 0.2 or nx1 > BX1 - 0.2 or ny0 < BY0 + 0.2 or ny1 > BY1 - 0.2:
                    continue
                x, y, rot = PLACE[mv]
                PLACE[mv] = (round((x + dX) * 20) / 20, round((y - dY) * 20) / 20, rot)
                fps[mv].SetPosition(V(*PLACE[mv][:2]))
                moved = True
                break
        if not moved:
            break
    return courtyard_overlaps(fps)


def courtyard_overlaps(fps):
    import pcbnew as P
    boxes = {}
    for ref, fp in fps.items():
        bb = fp.GetCourtyard(P.F_CrtYd).BBox()
        boxes[ref] = (P.ToMM(bb.GetLeft()), P.ToMM(bb.GetTop()), P.ToMM(bb.GetRight()), P.ToMM(bb.GetBottom()))
    bad = []
    refs = sorted(boxes)
    for i, a in enumerate(refs):
        for bref in refs[i + 1:]:
            A, Bb = boxes[a], boxes[bref]
            t = 0.03   # courtyard bbox includes the 0.05 line width
            if A[0] + t < Bb[2] and Bb[0] + t < A[2] and A[1] + t < Bb[3] and Bb[1] + t < A[3]:
                bad.append((a, bref))
    return bad


# ---------------------------------------------------------------------------------------------------------------
def pad_poly(pad, layer):
    import pcbnew as P
    ps = P.SHAPE_POLY_SET()
    pad.TransformShapeToPolygon(ps, layer, 0, mm(0.005), P.ERROR_INSIDE)
    o = ps.Outline(0)
    return [to_xy(o.CPoint(i)) for i in range(o.PointCount())]


def add_track(b, net, layer, a, c, w):
    import pcbnew as P
    t = P.PCB_TRACK(b)
    t.SetStart(V(*a)); t.SetEnd(V(*c)); t.SetWidth(mm(w)); t.SetLayer(layer); t.SetNet(net)
    b.Add(t)


def add_via(b, net, c):
    import pcbnew as P
    v = P.PCB_VIA(b)
    v.SetPosition(V(*c)); v.SetWidth(mm(VIA_D)); v.SetDrill(mm(VIA_DRILL)); v.SetNet(net)
    b.Add(v)


LAYERS = None


def route(b, fps, netinfo, nets, log):
    import pcbnew as P
    global LAYERS
    LAYERS = [P.F_Cu, P.In2_Cu, P.B_Cu]
    g = router.Grid(BX0, BY0, BX1, BY1, g=0.1, clearance=CLEAR, slack=0.05, widths={"sig": 0.2, "pwr": 0.4},
                    via=(VIA_D, VIA_DRILL))
    nid = {n: i + 1 for i, n in enumerate(sorted(nets))}
    NCID = 253
    g.mark_outline(OUTLINE, 0.3)
    # region tags
    ux, uy, _ = U1_POS
    g.tag_rect([0], (BX0, uy - 6.4, -9.0, uy + 7.4), TAG_MODULE)   # no L1 routing under the module (castellation ends free)
    g.tag_rect([0, 1, 2], ANALOG_RECT, TAG_ANALOG)
    dog_clusters, dog_gnd = {}, set()
    # footprint keepout areas (TC2030 legs etc.): nothing of ours inside
    for fp in fps.values():
        for z in fp.Zones():
            if z.GetIsRuleArea():
                o = z.Outline().Outline(0)
                poly = [to_xy(o.CPoint(i)) for i in range(o.PointCount())]
                xs = [q[0] for q in poly]; ys = [q[1] for q in poly]
                for i, x, y in g._bbox_cells(min(xs) - 0.5, min(ys) - 0.5, max(xs) + 0.5, max(ys) + 0.5):
                    if router.poly_dist(x, y, poly) <= 0.45:
                        g.novia[i] = 1
                        if z.GetDoNotAllowTracks():
                            for c in g.cls:
                                for l in range(3):
                                    g.own[c][l][i] = router.HARD
    # pads
    pads = {}   # (ref, num) -> list of dict(poly, layers, net, centre)
    for ref, fp in fps.items():
        for p in fp.Pads():
            net = p.GetNetname()
            k = nid.get(net, NCID)
            layers = [0, 1, 2] if p.GetAttribute() in (P.PAD_ATTRIB_PTH,) else ([0] if p.IsOnLayer(P.F_Cu) else [])
            if p.GetAttribute() == P.PAD_ATTRIB_NPTH:
                x, y = to_xy(p.GetPosition())
                g.mark_hole((x, y), P.ToMM(p.GetDrillSize().x) / 2)
                continue
            if not layers:
                continue
            poly = pad_poly(p, P.F_Cu)
            g.mark_poly(layers, poly, k)
            if p.GetAttribute() == P.PAD_ATTRIB_PTH:
                x, y = to_xy(p.GetPosition())
                g.mark_via_hole((x, y))
            else:
                xs = [q[0] for q in poly]; ys = [q[1] for q in poly]
                for i, x, y in g._bbox_cells(min(xs), min(ys), max(xs), max(ys)):
                    if router.in_poly(x, y, poly):
                        g.novia[i] = 1
            pads.setdefault((ref, p.GetNumber()), []).append(dict(poly=poly, layers=layers, net=net, c=to_xy(p.GetPosition())))
    # boost preroutes
    gnd = netinfo["GND"]
    for net, w, pts in BOOST_TRACKS:
        P_ = [(B[0] + x, B[1] + y) for x, y in pts]
        for a, c in zip(P_, P_[1:]):
            add_track(b, netinfo[net], P.F_Cu, a, c, w)
            g.mark_seg([0], a, c, w, nid[net])
    for ra, pa, rb, pb, axis, out in DOGLEGS:
        A = pads[(ra, pa)][0]
        Bp = min(pads[(rb, pb)], key=lambda q: math.hypot(q["c"][0] - A["c"][0], q["c"][1] - A["c"][1]))
        a, c = A["c"], Bp["c"]
        if out:
            m = (a[0] + out, a[1]) if axis == "x" else (a[0], a[1] + out)
            pts = [a, m, c]
        else:
            pts = [a, (a[0], c[1])]
        net = A["net"]
        w = 0.3 if net == "GND" else 0.25
        for p0, p1 in zip(pts, pts[1:]):
            if p0 != p1:
                add_track(b, netinfo[net], P.F_Cu, p0, p1, w)
                g.mark_seg([0], p0, p1, w, nid[net])
        if net == "GND":
            dog_gnd.add((ra, pa))
        else:
            dog_clusters.setdefault(net, []).append([(ra, pa), (rb, pb)])
    for ra, pa, caps, bus in COMBS:
        A = pads[(ra, pa)][0]
        net = A["net"]
        cs = [pads[c][0]["c"] for c in caps]
        a = A["c"]
        y = a[1] if bus is None else bus
        start = a if bus is None else (a[0], y)
        far = (max(c[0] for c in cs), y)
        segs = ([] if bus is None else [(a, start)]) + [(start, far)] + [((c[0], y), c) for c in cs]
        for p0, p1 in segs:
            add_track(b, netinfo[net], P.F_Cu, p0, p1, 0.25)
            g.mark_seg([0], p0, p1, 0.25, nid[net])
        dog_clusters.setdefault(net, []).append([(ra, pa)] + list(caps))
    terms_extra = {}
    for ref, pin, v in PIN_VIAS:
        pd = pads[(ref, pin)][0]
        net = pd["net"]
        add_track(b, netinfo[net], P.F_Cu, pd["c"], v, 0.2)
        g.mark_seg([0], pd["c"], v, 0.2, nid[net])
        add_via(b, netinfo[net], v)
        g.commit([], [v], VIA_D, nid[net])
        i = g.cell(*v)
        terms_extra[(ref, pin)] = {(1, i), (2, i)}
    gnd_vias = []
    for net, (x, y) in BOOST_VIAS:
        c = (B[0] + x, B[1] + y)
        add_via(b, netinfo[net], c)
        g.commit([], [c], VIA_D, nid[net])
        gnd_vias.append(c)
    # GND fan-out: every SMD GND pad gets a via to the L2 plane
    fan = gnd_fanout(b, g, pads, nid["GND"], gnd, gnd_vias, log, skip=dog_gnd | {("J2", "A12"), ("J2", "B12")})
    # RF via fence + perimeter fence now; the interior stitching grid after routing (it would take escape room)
    stitch(b, g, nid["GND"], gnd, gnd_vias, grid=False)
    # module LGA fan-out for the used signal pads (stub + via, inside the module footprint)
    terms_extra.update({("U1", k): v for k, v in module_fanout(b, g, fps["U1"], nid, netinfo, log).items()})

    # ---- nets to route ----
    order = route_order(nets)
    clusters = {n: ([list(BOOST_CLUSTERS[n])] if n in BOOST_CLUSTERS else []) for n in nets}
    for n, pairs in dog_clusters.items():   # merge dogleg pairs into existing clusters
        for pair in pairs:
            hit = [c for c in clusters[n] if set(c) & set(pair)]
            if hit:
                hit[0].extend(q for q in pair if q not in hit[0])
            else:
                clusters[n].append(list(pair))
    failed = []
    for name in order:
        if name == "GND":
            continue
        k = nid[name]
        cls = "pwr" if name in POWER_NETS else "sig"
        w = g.widths[cls]
        # terminals: groups of (layer, cell) sets
        groups, labels = [], []
        used = set()
        for cl in clusters.get(name, []):
            cells = set()
            for key in cl:
                for pd in pads[key]:
                    cells |= term_cells(g, pd)
                used.add(key)
            groups.append(cells); labels.append("+".join(f"{r}.{p}" for r, p in cl))
        for ref, pin in nets[name]:
            keys = [(ref, pin)] + [(ref, a) for a in {("J2", "A1"): ["B12"], ("J2", "B1"): ["A12"], ("J2", "A4"): ["B9"], ("J2", "B4"): ["A9"]}.get((ref, pin), [])]
            if (ref, pin) in used:
                continue
            if (ref, pin) in terms_extra:
                groups.append(terms_extra[(ref, pin)]); labels.append(f"{ref}.{pin}(via)")
                continue
            cells = set()
            for key in keys:
                for pd in pads.get(key, []):
                    cells |= term_cells(g, pd)
            if not cells:
                log.append(f"no terminal cells {name} {ref}.{pin}")
                continue
            groups.append(cells); labels.append(f"{ref}.{pin}")
        if len(groups) < 2:
            continue
        layers = [0] if name in ANALOG_NETS else [0, 1, 2]
        forbid = {}
        if name in NOISY_NETS:
            forbid = {0: (TAG_ANALOG,), 1: (TAG_ANALOG,), 2: (TAG_ANALOG,)}
        if name not in ("USB_D+", "USB_D-") and not name.startswith("LED") and name not in ("UART_TX", "UART_RX", "I2S_BCLK", "I2S_FSYNC", "I2S_SDOUT", "ADC_SHDNZ", "+3V3", "USB_VBUS"):
            forbid.setdefault(0, ())
        forbid[0] = tuple(set(forbid.get(0, ())) | {TAG_MODULE})
        via_cost = 30.0 if name in ANALOG_NETS else 10.0
        # L1 is kept for short local hops and analog; long digital runs go to L4, power to L3
        lcost = (1.0, 1.6, 1.3) if name in ANALOG_NETS else ((1.5, 1.0, 1.25) if name in POWER_NETS | {"+3V3A"} else (1.6, 1.3, 1.0))
        tree = set(groups[0])
        rest = groups[1:]
        ok = True
        while rest:
            targets = set().union(*rest)
            path = g.astar(tree, targets, k, cls, layers, forbid, via_cost=via_cost, layer_cost=lcost)
            if path is None and name in ANALOG_NETS:
                path = g.astar(tree, targets, k, cls, [0, 1, 2], forbid, via_cost=via_cost, layer_cost=lcost)
            if path is None:
                ok = False
                break
            segs, vias = g.to_segments(path, cls, k, forbid)
            g.commit(segs, vias, w, k)
            for l, a, c in segs:
                add_track(b, netinfo[name], LAYERS[l], a, c, w)
            for v in vias:
                add_via(b, netinfo[name], v)
            end = path[-1]
            for l, i in path:
                tree.add((l, i))
            # via cells join every layer of the tree
            for v in vias:
                i = g.cell(*v)
                for l in range(3):
                    tree.add((l, i))
            hit = [r for r in rest if end in r]
            for r in hit:
                tree |= r
                rest.remove(r)
        if not ok:
            failed.append(name)
            left = [labels[groups.index(r)] for r in rest]
            log.append(f"FAILED {name}: unreached {left} (tree from {labels[0]})")
    stitch(b, g, nid["GND"], gnd, gnd_vias, fence=False)
    return failed, fan


def term_cells(g, pd):
    out = set()
    poly = pd["poly"]
    xs = [q[0] for q in poly]; ys = [q[1] for q in poly]
    for i, x, y in g._bbox_cells(min(xs), min(ys), max(xs), max(ys)):
        if router.in_poly(x, y, poly):
            for l in pd["layers"]:
                out.add((l, i))
    return out


def route_order(nets):
    first = ["ADC_AREG", "ADC_VREF", "ADC_DREG", "ADC_IN1M", "ADC_IN2M", "+3V3A", "I2S_BCLK", "I2S_FSYNC", "I2S_SDOUT",
             "ADC_SHDNZ", "USB_VBUS", "BOOST_FB", "VSYS", "+5V", "PRE_INM", "PRE_CG", "PRE_OUTA", "PRE_OUTB", "PRE_INP", "PRE_NP", "MIC", "VCM",
             "ADC_IN1P", "ADC_IN2P", "ADC_IN1M", "ADC_IN2M", "ADC_VREF", "ADC_AREG", "ADC_DREG", "+3V3A", "+5V_BIAS",
             "USB_D+", "USB_D-", "USB_CC1", "USB_CC2", "USB_VBUS"]
    first = list(dict.fromkeys(first))
    rest = sorted(n for n in nets if n not in first)
    return [n for n in first if n in nets] + rest


def gnd_fanout(b, g, pads, gid, gnd, placed, log, skip=()):
    """one via per SMD GND pad (or pad group), as close as clearance allows"""
    import pcbnew as P
    n = 0
    for (ref, num), lst in sorted(pads.items()):
        for pd in lst:
            if pd["net"] != "GND" or pd["layers"] != [0] or (ref, num) in skip:
                continue
            if ref == "U2" and num != "25":   # QFN GND pins (AVSS, MSZ): stub straight into the exposed pad
                ep = pads[("U2", "25")][0]["c"]
                a = pd["c"]
                # straight in, perpendicular to the pad row, until inside the EP; then to its centre
                m = (ep[0] + math.copysign(0.9, a[0] - ep[0]), a[1]) if abs(a[0] - ep[0]) > abs(a[1] - ep[1]) \
                    else (a[0], ep[1] + math.copysign(0.9, a[1] - ep[1]))
                for p0, p1 in ((a, m), (m, ep)):
                    add_track(b, gnd, P.F_Cu, p0, p1, 0.25)
                    g.mark_seg([0], p0, p1, 0.25, gid)
                continue
            cx, cy = pd["c"]
            xs = [q[0] for q in pd["poly"]]; ys = [q[1] for q in pd["poly"]]
            hx, hy = (max(xs) - min(xs)) / 2, (max(ys) - min(ys)) / 2
            # already within 1.2 mm of a GND via we placed? (e.g. boost cell, H pads) -> just connect to it
            near = [v for v in placed if abs(v[0] - cx) <= hx + 0.15 and abs(v[1] - cy) <= hy + 0.15]
            if near:
                continue
            best = None
            for r in (0.0, 0.55, 0.75, 0.95, 1.2, 1.5):
                for ang in (270, 90, 0, 180, 240, 300, 120, 60, 210, 330, 150, 30):
                    a = math.radians(ang)
                    vx = cx + (hx + r) * math.cos(a) if r else cx
                    vy = cy + (hy + r) * math.sin(a) if r else cy
                    if r == 0.0 and (hx < 0.6 or hy < 0.6):
                        continue   # via in pad only on the big pads (module H pads, EP): none here
                    i = g.cell(vx, vy)
                    if i is None:
                        continue
                    vx, vy = g.xy(i)
                    if not g.via_ok(i, gid, {}) and not (r == 0.0):
                        continue
                    if r == 0.0 and not all(g.own["via"][l][i] in (0, gid) for l in range(3)):
                        continue
                    if not g.seg_free(0, (cx, cy), (vx, vy), "sig", gid, ()):
                        continue
                    if any(math.hypot(vx - p[0], vy - p[1]) < 0.9 for p in placed):
                        continue
                    best = (vx, vy)
                    break
                if best:
                    break
            if not best:
                log.append(f"GND fanout failed {ref}.{num}")
                continue
            if best != (cx, cy):
                add_track(b, gnd, P.F_Cu, (cx, cy), best, 0.25)
                g.mark_seg([0], (cx, cy), best, 0.25, gid)
            add_via(b, gnd, best)
            g.commit([], [best], VIA_D, gid)
            placed.append(best)
            n += 1
    return n


def stitch(b, g, gid, gnd, placed, fence=True, grid=True):
    """RF via fence along the antenna-side edge (x = -28, 1.5 mm pitch) and the module edges,
    then a 3 mm perimeter fence and a 5 mm interior stitching grid wherever a via fits."""
    pts = []
    y = BY0 + 0.9
    while y < NOTCH[1] - 0.6:
        pts.append((BX0 + 0.75, y)); y += 1.5
    x = BX0 + 0.75
    while x < NOTCH[0]:
        pts.append((x, NOTCH[1] - 0.75)); x += 1.5
    for x0 in (BX0 + 0.75,):
        pass
    per = []
    x = NOTCH[0] + 0.75
    while x < BX1 - 0.5:
        per.append((x, BY1 - 0.75)); per.append((x, BY0 + 0.75)); x += 3.0
    y = BY0 + 0.75
    while y < BY1 - 0.5:
        per.append((BX1 - 0.75, y)); y += 3.0
    inner = []
    for gx in range(int(BX0) + 2, int(BX1) - 1, 5):
        for gy in range(int(BY0) + 2, int(BY1) - 1, 5):
            inner.append((gx + 0.0, gy + 0.0))
    for c in (pts + per if fence else []) + (inner if grid else []):
        best = None
        for dx, dy in ((0, 0), (0.3, 0), (-0.3, 0), (0, 0.3), (0, -0.3), (0.6, 0), (-0.6, 0), (0, 0.6), (0, -0.6)):
            i = g.cell(c[0] + dx, c[1] + dy)
            if i is None:
                continue
            if not g.via_ok(i, gid, {}):
                continue
            v = g.xy(i)
            if any(math.hypot(v[0] - p[0], v[1] - p[1]) < 0.9 for p in placed):
                continue
            best = v
            break
        if best:
            add_via(b, gnd, best)
            g.commit([], [best], VIA_D, gid)
            placed.append(best)


def module_fanout(b, g, u1, nid, netinfo, log):
    """LGA signal pads under the module: short L1 stub to a via between pad rows; route from the via
    on the inner/bottom layers. Castellated pads are routed normally. GND LGA/H pads via-in-place nearby."""
    import pcbnew as P
    terms = {}
    for p in u1.Pads():
        num, net = p.GetNumber(), p.GetNetname()
        if not net or num.isdigit():
            continue
        cx, cy = to_xy(p.GetPosition())
        k = nid[net]
        if net == "GND":
            continue  # handled by gnd_fanout
        cand = [(cx + dx, cy + dy) for dx, dy in ((0.6, 0.75), (-0.6, 0.75), (0.6, -0.75), (-0.6, -0.75),
                                                 (0, 0.75), (0, -0.75), (0.6, 0), (-0.6, 0))]
        best = None
        for vx, vy in cand:
            i = g.cell(vx, vy)
            if i is None or not g.via_ok(i, k, {}):
                continue
            v = g.xy(i)
            if not g.seg_free(0, (cx, cy), v, "sig", k, ()):
                continue
            best = v
            break
        if not best:
            log.append(f"module fanout failed {num} {net}")
            continue
        add_track(b, netinfo[net], P.F_Cu, (cx, cy), best, 0.2)
        g.mark_seg([0], (cx, cy), best, 0.2, k)
        add_via(b, netinfo[net], best)
        g.commit([], [best], VIA_D, k)
        i = g.cell(*best)
        terms[num] = {(1, i), (2, i)}
    return terms


# ---------------------------------------------------------------------------------------------------------------
def zones(b, netinfo):
    import pcbnew as P
    gnd = netinfo["GND"]
    for layer, prio in ((P.F_Cu, 0), (P.In1_Cu, 0), (P.In2_Cu, 0), (P.B_Cu, 0)):
        z = P.ZONE(b)
        z.SetLayer(layer); z.SetNet(gnd)
        z.SetLocalClearance(mm(0.2))
        z.SetMinThickness(mm(0.2))
        z.SetThermalReliefGap(mm(0.25)); z.SetThermalReliefSpokeWidth(mm(0.3))
        z.SetPadConnection(P.ZONE_CONNECTION_THERMAL)
        z.SetIslandRemovalMode(P.ISLAND_REMOVAL_MODE_ALWAYS)
        z.SetAssignedPriority(prio)
        ol = z.Outline(); ol.NewOutline()
        for x, y in OUTLINE:
            ol.Append(mm(OX + x), mm(OY - y))
        b.Add(z)
    P.ZONE_FILLER(b).Fill(b.Zones())


def stackup_sexp():
    out = ["\t\t(stackup",
           '\t\t\t(layer "F.SilkS" (type "Top Silk Screen"))',
           '\t\t\t(layer "F.Paste" (type "Top Solder Paste"))',
           '\t\t\t(layer "F.Mask" (type "Top Solder Mask") (thickness 0.01))']
    d = 1
    for name, kind, t, er in STACKUP:
        if kind == "copper":
            out.append(f'\t\t\t(layer "{name}" (type "copper") (thickness {t}))')
        else:
            out.append(f'\t\t\t(layer "dielectric {d}" (type "{name}") (thickness {t}) (material "FR4 {kind}") '
                       f'(epsilon_r {er}) (loss_tangent 0.02))')
            d += 1
    out += ['\t\t\t(layer "B.Mask" (type "Bottom Solder Mask") (thickness 0.01))',
            '\t\t\t(layer "B.Paste" (type "Bottom Solder Paste"))',
            '\t\t\t(layer "B.SilkS" (type "Bottom Silk Screen"))',
            '\t\t\t(copper_finish "ENIG")', '\t\t\t(dielectric_constraints no)', "\t\t)"]
    return "\n".join(out)


def write_project():
    """design rules live in pack.kicad_dru; the project file carries netclasses and rule severities"""
    pro = {
        "board": {"design_settings": {
            "defaults": {"board_outline_line_width": 0.1, "copper_line_width": 0.2},
            "rules": {"min_clearance": 0.1, "min_track_width": 0.1, "min_via_diameter": 0.45, "min_via_annular_width": 0.1,
                      "min_through_hole_diameter": 0.2, "min_hole_to_hole": 0.25, "min_copper_edge_clearance": 0.3,
                      "min_hole_clearance": 0.15, "min_silk_clearance": 0.0, "min_text_height": 0.6,
                      "min_text_thickness": 0.1, "solder_mask_to_copper_clearance": 0.0},
            "rule_severities": {"lib_footprint_issues": "ignore", "lib_footprint_mismatch": "ignore",
                                "silk_overlap": "warning", "silk_over_copper": "warning", "silk_edge_clearance": "warning",
                                "text_height": "warning", "text_thickness": "warning", "footprint_type_mismatch": "ignore",
                                "missing_courtyard": "warning", "isolated_copper": "warning",
                                "solder_mask_bridge": "warning", "padstack": "warning", "via_dangling": "warning",
                                "track_dangling": "warning",
                                # every SMD GND pad has its own via to L2; the L1 pour is a second path
                                "starved_thermal": "warning"},
            "track_widths": [0.0, 0.2, 0.25, 0.3, 0.4], "via_dimensions": [{"diameter": 0.0, "drill": 0.0}, {"diameter": VIA_D, "drill": VIA_DRILL}],
        }},
        "net_settings": {
            "classes": [
                {"name": "Default", "clearance": 0.127, "track_width": 0.2, "via_diameter": VIA_D, "via_drill": VIA_DRILL,
                 "microvia_diameter": 0.3, "microvia_drill": 0.1, "diff_pair_width": 0.2, "diff_pair_gap": 0.2,
                 "diff_pair_via_gap": 0.25, "wire_width": 6, "bus_width": 12, "line_style": 0, "schematic_color": "rgba(0, 0, 0, 0.000)",
                 "pcb_color": "rgba(0, 0, 0, 0.000)", "priority": 2147483647},
                {"name": "Power", "clearance": 0.127, "track_width": 0.4, "via_diameter": VIA_D, "via_drill": VIA_DRILL,
                 "microvia_diameter": 0.3, "microvia_drill": 0.1, "diff_pair_width": 0.2, "diff_pair_gap": 0.2,
                 "diff_pair_via_gap": 0.25, "wire_width": 6, "bus_width": 12, "line_style": 0, "schematic_color": "rgba(0, 0, 0, 0.000)",
                 "pcb_color": "rgba(0, 0, 0, 0.000)", "priority": 0},
            ],
            "meta": {"version": 4},
            "netclass_patterns": [{"netclass": "Power", "pattern": n} for n in sorted(POWER_NETS)],
        },
        "meta": {"filename": "pack.kicad_pro", "version": 3},
    }
    PRO.write_text(json.dumps(pro, indent=2) + "\n")


def save(b):
    import pcbnew as P
    P.SaveBoard(str(BOARD), b)
    txt = BOARD.read_text()
    txt = re.sub(r"(\t\(setup\n)", lambda m: m.group(1) + stackup_sexp() + "\n", txt, count=1)
    BOARD.write_text(txt)


# ---------------------------------------------------------------------------------------------------------------
def drc(out=None):
    out = out or (HERE / "out" / "drc.json")
    out.parent.mkdir(exist_ok=True)
    subprocess.run(["kicad-cli", "pcb", "drc", "--format", "json", "--severity-all", "--refill-zones",
                    "--exit-code-violations", "-o", str(out), str(BOARD)], capture_output=True, text=True)
    rep = json.loads(out.read_text())
    errs = [v for v in rep.get("violations", []) if v.get("severity") == "error"]
    warns = [v for v in rep.get("violations", []) if v.get("severity") == "warning"]
    unconn = rep.get("unconnected_items", [])
    return rep, errs, warns, unconn


def summarize(errs, warns, unconn):
    from collections import Counter
    c = Counter(v["type"] for v in errs)
    w = Counter(v["type"] for v in warns)
    return f"DRC: {len(errs)} errors {dict(c)}, {len(warns)} warnings {dict(w)}, {len(unconn)} unconnected"


def main(argv):
    import pcbnew as P
    b, fps, netinfo, nets = build()
    bad = legalize(fps)
    if bad:
        print("courtyard overlaps:", bad)
    log = []
    failed, fan = route(b, fps, netinfo, nets, log)
    for line in log:
        print(line)
    print(f"GND fanout vias: {fan}; failed nets: {failed}")
    zones(b, netinfo)
    write_project()
    save(b)
    rep, errs, warns, unconn = drc()
    print(summarize(errs, warns, unconn))
    w = width_for(50.0)
    print(f"50 ohm microstrip L1/L2 (h 0.2104, er 4.4, t 35 um): w = {w:.3f} mm, Z0 at w=0.36: {microstrip_z0(0.36)[0]:.1f}")
    if "--no-out" not in argv:
        import outputs
        outputs.run_all()
    return 1 if (errs or unconn or failed) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
