"""OpenPack receiver sub-board PCB (issue #34): netlist -> hw/rx/rx.kicad_pcb, regenerable.

Run with the python that carries KiCad's pcbnew module (KiCad 10):
    python3 hw/rx/layout_rx.py            # place, route, pour, DRC, fab outputs, renders
    python3 hw/rx/layout_rx.py --no-out   # board + DRC only

Inputs: hw/rx/out/rx.net (SKiDL, `python hw/rx/rx.py`), footprints_rx.py. The pack board (hw/pack/layout.py) is the
template: the same grid router (hw/pack/router.py), stackup, JLC rules and fab flow.
Frame: board mm, origin at the bottom-left corner, x right / y up; KiCad gets X = 100 + x, Y = 100 - y.

Stackup (JLCPCB JLC04161H-7628, 1.6 mm): L1 sig + GND pour / L2 solid GND / L3 GND pour + digital / L4 sig + GND pour.
Every current-carrying net (rails, relay coil, the audio output legs) stays on the 35 um outer layers (#104 review M1).
Design choices and the review: hw/REVIEW.md (receiver section).
"""
import importlib.util, json, math, pathlib, re, subprocess, sys

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


pk = _load("hw_pack_layout", ROOT / "hw" / "pack" / "layout.py")   # helpers: netlist, pads, tracks, stackup, microstrip
router = pk.router
footprints_rx = _load("hw_rx_footprints", HERE / "footprints_rx.py")

NETLIST = HERE / "out" / "rx.net"
BOARD = HERE / "rx.kicad_pcb"
PRO = HERE / "rx.kicad_pro"
OX, OY = pk.OX, pk.OY
KICAD_FP = pk.KICAD_FP

# ---------------------------------------------------------------------------------------------------------------
# Outline. No rack mechanics exist yet (#33), so this defines them: a 48 x 90 mm mezzanine, J1 (2x13 THT header on
# the underside) along the bottom edge, two M3 standoff holes at the far end. Eight slots at >= 52 mm pitch = 416 mm,
# inside a 19" 1U case (~425 mm inside). Stack: main-board socket 8.5 + header body 2.5 -> sub-board underside 11.0
# mm above the main board; tallest top part C47/C48 (10 x 12.5 radial) -> 25.1 mm above the main board top.
# ---------------------------------------------------------------------------------------------------------------
BW, BH = 48.0, 90.0
OUTLINE = [(0.0, 0.0), (BW, 0.0), (BW, BH), (0.0, BH)]
J1_PIN1 = (8.76, 5.54)           # pin 1; odd pins on y = 5.54, even on 3.0 (underside header: mirrored), pairs every 2.54 mm in +x
MOUNT = {"H1": (3.4, 86.6), "H2": (44.6, 40.0)}
MECH = dict(board=(BW, BH), thickness=1.6, j1_pin1=J1_PIN1, j1_pitch=2.54, mount_m3=MOUNT, slot_pitch_min=52.0,
            header_stack=11.0, top_max_height=12.5)

STACKUP = pk.STACKUP
H_L1L2, ER = 0.2104, 4.4


# ---------------------------------------------------------------------------------------------------------------
# 50 ohm grounded coplanar waveguide on L1 (0.25 mm gap to the L1 GND pour) over the L2 plane. Sized with a 2D field
# solve of this stackup (hw/rx/rf_line.py: the closed-form CPW formula is off for gap > h), calibrated on the pack's
# Hammerstad-Jensen microstrip: w = 0.31 mm -> 50.1 ohm.
# ---------------------------------------------------------------------------------------------------------------
rf_line = _load("hw_rx_rf_line", HERE / "rf_line.py")
RF_W, RF_GAP = rf_line.RF_W, rf_line.RF_GAP
RF_NETS = ("RF_A", "RF_B", "SW_RF1", "SW_RF2", "SW_RFC", "RF_OUT")
FENCE_OFF, FENCE_PITCH = 1.0, 1.2              # via fence: centre 1.0 mm off the line, 1.2 mm pitch (lambda/28 in FR4)

# ---------------------------------------------------------------------------------------------------------------
# net classes
# ---------------------------------------------------------------------------------------------------------------
# rails + relay coil: 0.5 mm on L1/L4 (35 um), necking to 0.3 only within 1.2 mm of a pad too small for 0.5
POWER_NETS = ("+12V", "+12V_R", "+12VA", "+5V", "+3V3", "+3V3A", "RLY_COIL")
# audio output legs: DC-blocked, but a charged phantom cable shorted at the XLR puts ~0.9 A peak through them
# (ADR-0014, hw/spice/rx_driver_load.cir): same 0.5 mm outer-layer class
AUDIO_I_NETS = ("DRV_OUTA", "DRV_OUTB", "DRV_COLD_P", "DRV_HOT_P", "DRV_COLD_X", "DRV_HOT_X", "DRV_COLD_O", "DRV_HOT_O",
                "AUD_COLD", "AUD_HOT")
WIDE_NETS = POWER_NETS + AUDIO_I_NETS
WIDE_W, NECK_W, NECK_ZONE = 0.5, 0.3, 1.2
# rail pins that carry no current (logic straps): routed last as 0.2 mm signal tracks on any layer.
# PCM5102A FLT (pin 11, tied high for the low-latency filter) sits beyond the I2S pins; the PE4259 VDD (9 uA, Table 2)
# and its 100 nF sit inside the RF block.
LOGIC_TIES = {("U3", "11"), ("U2", "6"), ("C23", "1")}
ANALOG_NETS = {"DAC_OUTL", "DAC_OUTF", "DRV_CIN", "DRV_INA", "DRV_INB", "VCM", "VCM1", "DAC_LDOO", "DAC_CAPP", "DAC_CAPM",
               "DAC_VNEG"} | set(AUDIO_I_NETS)
# digital / switching nets: never inside the analog region, on any layer (their return current stays out of the
# ground under the audio path)
NOISY_NETS = {"+12V", "+12V_R", "+5V", "+3V3", "RLY_COIL", "RLY_G", "SUP_SENSE", "UART_TX", "UART_RX", "BP_UART_TX",
              "BP_UART_RX", "nRESET", "BP_nRESET", "BOOT", "BP_BOOT", "SWDIO", "SWDCLK", "LED_LOCK", "LED_PEAK",
              "BP_LED_LOCK", "BP_LED_PEAK", "SLOT0", "SLOT1", "SLOT2", "BP_SLOT0", "BP_SLOT1", "BP_SLOT2", "ANT_SEL",
              "OUT_EN", "XSMT_EN", "I2S_BCK", "I2S_LRCK", "I2S_SDOUT", "BP_I2S_BCK", "BP_I2S_LRCK", "BP_I2S_SDOUT"}
# analog region (tag 2): DAC analog side, driver, clamps, coupling caps, relay contacts, J1 audio pins
ANALOG_RECTS = [(0.3, 7.0, 13.2, 24.4), (0.3, 24.4, 15.8, 66.0), (0.3, 66.0, 7.2, 77.0)]
TAG_MODULE, TAG_ANALOG = 1, 2
VIA_D, VIA_DRILL = 0.6, 0.3
CLEAR = 0.15

# ---------------------------------------------------------------------------------------------------------------
# placement: ref -> (x, y, rotation deg CCW), all on top except J1 (underside)
# ---------------------------------------------------------------------------------------------------------------
U1_POS = (38.5, 81.5, 0)      # BT40E: x 31.5..45.5, y 73.5..89.5; u.FL at (43.55, 88.1) by the top edge
PLACE = {
    "U1": U1_POS,
    # --- RF (top left): J3/J4 from the rack splitters -> 10 pF -> PE4259 -> 10 pF -> J5 -> jumper -> module u.FL ---
    "J4": (8.8, 85.5, 180), "C21": (12.6, 85.5, 0), "J3": (8.8, 79.0, 180), "C20": (12.6, 79.0, 0),
    "U2": (17.4, 82.25, 0), "C22": (21.4, 82.25, 0), "J5": (26.0, 82.25, 0), "C23": (20.0, 84.8, 90), "R36": (20.0, 79.6, 90),
    "TP12": (23.0, 78.6, 0),
    # --- DAC (analog pins 1-10 face left, I2S pins 11-20 face right) ---
    "U3": (10.4, 72.5, 0),
    "C32": (2.6, 76.6, 90), "C33": (5.0, 76.4, 180), "C37": (5.0, 74.6, 270), "C38": (3.2, 71.8, 180),
    "C30": (2.6, 69.0, 90), "C31": (5.0, 70.4, 180),
    "C34": (17.4, 77.2, 0), "C35": (15.6, 76.0, 0), "C36": (15.6, 74.6, 0), "R38": (17.4, 74.3, 90), "R37": (15.6, 73.45, 0),
    "D10": (17.2, 66.4, 90), "TP8": (21.4, 76.4, 0), "TP9": (23.6, 76.4, 0), "TP10": (25.8, 76.4, 0),
    "R40": (5.0, 68.6, 270), "C39": (2.6, 66.2, 90), "C40": (9.8, 65.4, 180),
    # --- balanced driver (U6) + VCM ---
    "U6": (8.2, 59.6, 0), "R41": (2.0, 62.0, 90), "R42": (3.4, 61.0, 90), "C41": (3.4, 58.2, 90),
    "R43": (13.4, 58.6, 90), "R44": (14.8, 58.6, 90), "C42": (16.2, 58.6, 90),
    "C45": (12.5, 61.5, 90), "C46": (15.0, 62.4, 90),
    "C43": (21.6, 62.0, 0), "C49": (21.6, 55.6, 0), "R45": (26.8, 64.0, 90), "R46": (26.8, 61.0, 90), "R53": (26.8, 58.0, 90),
    "C44": (16.8, 55.6, 90), "D8": (21.4, 50.6, 0), "TP11": (26.8, 52.4, 0),
    # --- output legs: 22 R -> S1J clamps -> 47 uF BP -> relay ---
    "R50": (4.0, 54.9, 0), "R47": (11.6, 54.9, 0),
    "D6": (2.1, 49.8, 90), "D4": (5.9, 49.8, 90), "D3": (9.7, 49.8, 90), "D5": (13.5, 49.8, 90),
    "C47": (3.2, 40.0, 0), "C48": (3.2, 29.0, 0), "R54": (12.4, 36.0, 90), "R55": (12.4, 25.4, 90),
    "K1": (8.8, 16.8, 270), "R49": (2.0, 8.1, 90), "R52": (10.3, 8.0, 0), "R48": (4.2, 8.1, 90), "R51": (7.6, 8.0, 0),
    # --- +12 V entry, hold-up, coil drive, supervisor (middle column) ---
    "D1": (17.4, 9.6, 90), "D7": (18.2, 17.0, 270), "Q1": (18.8, 23.8, 0), "R62": (21.6, 22.0, 90), "R63": (23.0, 22.0, 90),
    "TP13": (21.8, 26.0, 0),
    "R1": (16.0, 30.0, 90), "D9": (19.6, 30.6, 0), "C7": (18.6, 38.6, 90), "C8": (16.2, 45.0, 90), "TP1": (17.4, 27.4, 0),
    "TP2": (22.0, 45.2, 0), "TP7": (17.2, 48.6, 0),
    "U7": (25.0, 28.6, 0), "C61": (27.6, 29.6, 90), "R60": (23.0, 32.8, 90), "R61": (24.4, 32.8, 90), "C60": (26.0, 32.8, 90),
    # --- +5 V entry, LDOs ---
    "D2": (21.6, 9.6, 90), "C9": (22.6, 15.6, 90), "C1": (26.2, 12.8, 90), "C2": (27.6, 12.8, 90), "TP3": (26.4, 19.8, 0),
    "U5": (20.6, 68.6, 270), "C5": (23.2, 69.8, 90), "C6": (19.0, 72.8, 90), "TP5": (24.4, 66.6, 0),
    "U4": (34.0, 50.0, 0), "C3": (37.8, 50.4, 90), "C4": (30.2, 50.0, 90), "TP4": (40.6, 50.0, 0),
    "TP6": (29.0, 21.0, 0),
    # --- module decoupling + SWD ---
    "C10": (43.0, 71.6, 90), "C11": (44.6, 72.0, 90), "C12": (40.6, 70.6, 90),
    "J2": (40.0, 60.0, 0),
    # --- backplane series resistors above J1 pins 13..26 ---
    "R33": (25.6, 8.4, 90), "R34": (27.6, 8.4, 90), "R20": (30.2, 8.4, 90), "R22": (32.6, 8.4, 90), "R31": (35.2, 8.4, 90),
    "R25": (37.6, 8.4, 90), "R27": (40.2, 8.4, 90),
    "R35": (28.8, 11.0, 90), "R21": (31.4, 11.0, 90), "R23": (34.0, 11.0, 90), "R32": (36.6, 11.0, 90), "R26": (39.0, 11.0, 90),
    "R24": (33.0, 14.0, 90), "R28": (36.6, 14.0, 90), "R29": (38.4, 14.0, 90), "R30": (40.2, 14.0, 90),
}
FIXED = {"C37", "C38", "U1", "J1", "J3", "J4", "J5", "U2", "C20", "C21", "C22", "K1", "C47", "C48", "U3", "U6", "H1", "H2", "J2"}

# silkscreen: refdes inside the body outline where pads leave room; tiny parts keep theirs on F.Fab; the antenna
# inputs get a plain label (the jumpers are plugged by hand)
REF_AT = {"K1": (8.8, 16.8), "U6": (8.2, 59.6), "U3": (10.4, 72.5)}
HIDE_REF = {"J3", "J4", "U2", "U5"}
SILK_TEXT = {"ANT A": (13.0, 76.6), "ANT B": (12.6, 88.6), "OpenPack RX #34": (38.5, 46.0), "J1 underside, pin 1": (13.0, 0.9)}

# PCM5102A charge pump: pin -> cap pad as an L-shaped L1 stub (out along the pin, then onto the pad), drawn before
# the GND fan-out so the CPGND/AGND vias cannot take the room (ref, pad, ref, pad). These two-pin nets are not routed.
STUBS = [("U3", "2", "C37", "1"), ("U3", "4", "C37", "2"), ("U3", "5", "C38", "1")]


def mm(v):
    return pk.mm(v)


def V(x, y):
    return pk.V(x, y)


def to_xy(p):
    return pk.to_xy(p)


def fp_path(lib_fp):
    lib, name = lib_fp.split(":")
    d = footprints_rx.LIB if lib == "openpack" else KICAD_FP / f"{lib}.pretty"
    return d, name


def read_netlist(path=NETLIST):
    return pk.read_netlist(path)


# ---------------------------------------------------------------------------------------------------------------
def place_j1(fp):
    """underside header: flip, then pick the rotation that puts pin 1 at J1_PIN1, pin 2 below it, pin 3 to its right"""
    import pcbnew as P
    fp.Flip(fp.GetPosition(), P.FLIP_DIRECTION_LEFT_RIGHT)
    for rot in (0, 90, 180, 270):
        fp.SetOrientationDegrees(rot)
        fp.SetPosition(V(0, 0))
        pads = {p.GetNumber(): to_xy(p.GetPosition()) for p in fp.Pads()}
        dx, dy = J1_PIN1[0] - pads["1"][0], J1_PIN1[1] - pads["1"][1]
        p2 = (pads["2"][0] + dx, pads["2"][1] + dy)
        p3 = (pads["3"][0] + dx, pads["3"][1] + dy)
        if abs(p2[0] - J1_PIN1[0]) < 1e-3 and abs(J1_PIN1[1] - p2[1] - 2.54) < 1e-3 and abs(p3[0] - J1_PIN1[0] - 2.54) < 1e-3:
            fp.SetPosition(V(dx, dy))
            return rot
    raise SystemExit("J1: no rotation gives the ADR-0014 pin order")


def build():
    import pcbnew as P
    footprints_rx.write_lib()
    comps, nets = read_netlist()
    b = P.BOARD()
    b.SetCopperLayerCount(4)
    netinfo = {}
    for name in sorted(nets):
        ni = P.NETINFO_ITEM(b, name)
        b.Add(ni)
        netinfo[name] = ni
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
        if ref == "J1":
            place_j1(fp)
        else:
            x, y, rot = PLACE[ref]
            fp.SetPosition(V(x, y))
            fp.SetOrientationDegrees(rot)
        fps[ref] = fp
        if ref[0] in "RCLDQ" or ref.startswith("TP") or ref in HIDE_REF:
            fp.Reference().SetVisible(False)
        else:
            fp.Reference().SetTextSize(P.VECTOR2I(mm(0.8), mm(0.8)))
            fp.Reference().SetTextThickness(mm(0.15))
        fp.Value().SetVisible(False)
        if c.get("mpn") == "DNP":
            fp.SetDNP(True)
            fp.SetExcludedFromPosFiles(True)
            fp.SetExcludedFromBOM(True)
    for ref, (x, y) in MOUNT.items():
        fp = P.FootprintLoad(str(KICAD_FP / "MountingHole.pretty"), "MountingHole_3.2mm_M3")
        fp.SetReference(ref)
        fp.SetFPID(P.LIB_ID("MountingHole", "MountingHole_3.2mm_M3"))
        fp.Reference().SetVisible(False)
        fp.Value().SetVisible(False)
        b.Add(fp)
        fp.SetPosition(V(x, y))
        fps[ref] = fp
    missing = set(PLACE) - set(comps)
    assert not missing, missing
    unplaced = set(comps) - set(PLACE) - {"J1"}
    assert not unplaced, unplaced
    for name, nodes in nets.items():
        for ref, pin in nodes:
            hit = 0
            for p in fps[ref].Pads():
                if p.GetNumber() == pin:
                    p.SetNet(netinfo[name]); hit += 1
            assert hit, (ref, pin)
    for ref, (x, y) in REF_AT.items():
        fps[ref].Reference().SetPosition(V(x, y))
        fps[ref].Reference().SetTextAngleDegrees(0)
    for txt, (x, y) in SILK_TEXT.items():
        t = P.PCB_TEXT(b)
        t.SetText(txt); t.SetLayer(P.F_SilkS); t.SetPosition(V(x, y))
        t.SetTextSize(P.VECTOR2I(mm(0.8), mm(0.8))); t.SetTextThickness(mm(0.15))
        b.Add(t)
    return b, fps, netinfo, nets


def courtyard_boxes(fps):
    """F.CrtYd boxes of the top-side parts; J1 (underside) contributes its pad rows as a keep-out for top parts"""
    import pcbnew as P
    boxes = {}
    for ref, fp in fps.items():
        if ref == "J1":
            pts = [to_xy(p.GetPosition()) for p in fp.Pads()]
            xs = [q[0] for q in pts]; ys = [q[1] for q in pts]
            boxes[ref] = (min(xs) - 1.05, max(xs) + 1.05, min(ys) - 1.05, max(ys) + 1.05)
            continue
        bb = fp.GetCourtyard(P.F_CrtYd).BBox()
        x0, x1 = P.ToMM(bb.GetLeft()) - OX, P.ToMM(bb.GetRight()) - OX
        y0, y1 = OY - P.ToMM(bb.GetBottom()), OY - P.ToMM(bb.GetTop())
        boxes[ref] = (x0, x1, y0, y1)
    return boxes


def courtyard_overlaps(fps):
    boxes = courtyard_boxes(fps)
    bad = []
    refs = sorted(boxes)
    t = 0.03
    for i, a in enumerate(refs):
        for c in refs[i + 1:]:
            A, B = boxes[a], boxes[c]
            if A[0] + t < B[1] and B[0] + t < A[1] and A[2] + t < B[3] and B[2] + t < A[3]:
                bad.append((a, c))
    return bad


def legalize(fps, margin=0.1, iters=400):
    """nudge movable parts until no courtyards overlap (FIXED parts stay put); moves snap to 0.05 mm"""
    order = list(PLACE) + list(MOUNT) + ["J1"]
    for _ in range(iters):
        moved = False
        boxes = courtyard_boxes(fps)
        for a, c in courtyard_overlaps(fps):
            mv = c if c not in FIXED and (a in FIXED or order.index(c) > order.index(a)) else a
            if mv in FIXED or mv == "J1":
                continue
            other = a if mv == c else c
            A, O = boxes[mv], boxes[other]
            cands = [(O[1] - A[0] + margin, 0), (-(A[1] - O[0] + margin), 0), (0, O[3] - A[2] + margin), (0, -(A[3] - O[2] + margin))]
            cands.sort(key=lambda d: abs(d[0]) + abs(d[1]))
            for dx, dy in cands:
                if A[0] + dx < 0.2 or A[1] + dx > BW - 0.2 or A[2] + dy < 0.2 or A[3] + dy > BH - 0.2:
                    continue
                x, y, rot = PLACE[mv]
                PLACE[mv] = (round((x + dx) * 20) / 20, round((y + dy) * 20) / 20, rot)
                fps[mv].SetPosition(V(*PLACE[mv][:2]))
                moved = True
                break
            if moved:
                break
        if not moved:
            break
    return courtyard_overlaps(fps)


# ---------------------------------------------------------------------------------------------------------------
add_track, add_via, pad_poly, term_cells = pk.add_track, pk.add_via, pk.pad_poly, pk.term_cells
LAYERS = None


def rf_preroute(b, g, pads, nid, netinfo, fence):
    """50 ohm GCPW on L1: J3 -> C20 -> U2.RF2, J4 -> C21 -> U2.RF1, U2.RFC -> C22 -> J5. Straight runs with one 45 deg
    bend where the PE4259 pins (0.65 mm pitch) sit off the connector axis. Returns the via-fence candidates."""
    import pcbnew as P

    def c(ref, pin):
        return pads[(ref, pin)][0]["c"]

    runs = []
    for jref, cref, upin in (("J3", "C20", "3"), ("J4", "C21", "1")):
        j, c1, c2, u = c(jref, "1"), c(cref, "1"), c(cref, "2"), c("U2", upin)
        # cap pad nearest the connector takes the connector net
        if math.dist(c2, j) < math.dist(c1, j):
            c1, c2 = c2, c1
        # horizontal out of the cap, then one 45 deg run straight into the pin: RF1/RF2 arrive from above/below, which
        # leaves room left of the GND pin (2) between them for its stub and via
        bend = (u[0] - abs(u[1] - c2[1]), c2[1])
        assert bend[0] >= c2[0], (jref, bend, c2)
        runs.append((pads[(jref, "1")][0]["net"], [j, c1]))
        runs.append((pads[("U2", upin)][0]["net"], [c2, bend, u]))
    u, c1, c2, j = c("U2", "5"), c("C22", "1"), c("C22", "2"), c("J5", "1")
    if math.dist(c2, u) < math.dist(c1, u):
        c1, c2 = c2, c1
    runs.append((pads[("U2", "5")][0]["net"], [u, c1]))
    runs.append((pads[("J5", "1")][0]["net"], [c2, j]))
    length = {}
    for net, pts in runs:
        for a, e in zip(pts, pts[1:]):
            if math.dist(a, e) < 1e-6:
                continue
            add_track(b, netinfo[net], P.F_Cu, a, e, RF_W)
            g.mark_seg([0], a, e, RF_W + 2 * (RF_GAP - CLEAR), nid[net])
            length[net] = length.get(net, 0.0) + math.dist(a, e)
            # fence candidates both sides
            L = math.dist(a, e)
            ux, uy = (e[0] - a[0]) / L, (e[1] - a[1]) / L
            n = max(1, int(L / FENCE_PITCH))
            for k in range(n + 1):
                t = k / n
                px, py = a[0] + (e[0] - a[0]) * t, a[1] + (e[1] - a[1]) * t
                for s in (1, -1):
                    fence.append((px - s * uy * FENCE_OFF, py + s * ux * FENCE_OFF))
    return length


def module_fanout(b, g, u1, nid, netinfo, log):
    """LGA signal pads: short L1 stub to a via between pad rows, routed on from the via on L3/L4"""
    import pcbnew as P
    terms = {}
    for p in u1.Pads():
        num, net = p.GetNumber(), p.GetNetname()
        if not net or num.isdigit() or net == "GND":
            continue
        cx, cy = to_xy(p.GetPosition())
        k = nid[net]
        cand = [(cx + dx, cy + dy) for dx, dy in ((0.75, 0.6), (-0.75, 0.6), (0.75, -0.6), (-0.75, -0.6), (0.75, 0), (-0.75, 0),
                                                 (0, 0.6), (0, -0.6))]
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


def gnd_fanout(b, g, pads, gid, gnd, placed, log):
    """one via per SMD GND pad, as close as clearance allows (big pads: via in pad)"""
    import pcbnew as P
    n = 0
    for (ref, num), lst in sorted(pads.items()):
        for pd in lst:
            if pd["net"] != "GND" or pd["layers"] != [0]:
                continue
            cx, cy = pd["c"]
            xs = [q[0] for q in pd["poly"]]; ys = [q[1] for q in pd["poly"]]
            hx, hy = (max(xs) - min(xs)) / 2, (max(ys) - min(ys)) / 2
            if [v for v in placed if abs(v[0] - cx) <= hx + 0.15 and abs(v[1] - cy) <= hy + 0.15]:
                continue
            best = None
            for r in (0.0, 0.55, 0.75, 0.95, 1.2, 1.5, 1.8):
                for ang in (270, 90, 0, 180, 240, 300, 120, 60, 210, 330, 150, 30):
                    a = math.radians(ang)
                    vx = cx + (hx + r) * math.cos(a) if r else cx
                    vy = cy + (hy + r) * math.sin(a) if r else cy
                    if r == 0.0 and (hx < 0.6 or hy < 0.6):
                        continue
                    i = g.cell(vx, vy)
                    if i is None:
                        continue
                    vx, vy = g.xy(i)
                    if r and not g.via_ok(i, gid, {}):
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
                add_track(b, gnd, P.F_Cu, (cx, cy), best, 0.3)
                g.mark_seg([0], (cx, cy), best, 0.3, gid)
            add_via(b, gnd, best)
            g.commit([], [best], VIA_D, gid)
            placed.append(best)
            n += 1
    return n


def stitch(b, g, gid, gnd, placed, pts):
    n = 0
    for c in pts:
        best = None
        for dx, dy in ((0, 0), (0.2, 0), (-0.2, 0), (0, 0.2), (0, -0.2), (0.4, 0), (-0.4, 0), (0, 0.4), (0, -0.4)):
            i = g.cell(c[0] + dx, c[1] + dy)
            if i is None or not g.via_ok(i, gid, {}):
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
            n += 1
    return n


def perimeter_and_grid():
    per, inner = [], []
    x = 1.0
    while x < BW - 0.5:
        per += [(x, 0.8), (x, BH - 0.8)]; x += 3.0
    y = 2.0
    while y < BH - 1.0:
        per += [(0.8, y), (BW - 0.8, y)]; y += 3.0
    for gx in range(3, int(BW) - 1, 4):
        for gy in range(3, int(BH) - 1, 4):
            inner.append((gx + 0.0, gy + 0.0))
    return per, inner


def route_order(nets):
    first = ["ANT_SEL", "+12V", "RLY_COIL", "+5V", "+12V_R", "+12VA", "+3V3A", "+3V3",
             "DRV_HOT_X", "DRV_COLD_X", "DRV_HOT_O", "DRV_COLD_O", "AUD_HOT", "AUD_COLD", "DRV_HOT_P", "DRV_COLD_P",
             "DRV_OUTA", "DRV_OUTB", "DRV_INA", "DRV_INB", "DRV_CIN", "DAC_OUTF", "DAC_OUTL", "VCM", "VCM1",
             "DAC_CAPP", "DAC_CAPM", "DAC_VNEG", "DAC_LDOO", "I2S_BCK", "I2S_LRCK", "I2S_SDOUT"]
    first = [n for n in dict.fromkeys(first) if n in nets]
    return first + sorted(n for n in nets if n not in first)


def route(b, fps, netinfo, nets, log):
    import pcbnew as P
    global LAYERS
    LAYERS = [P.F_Cu, P.In2_Cu, P.B_Cu]
    g = router.Grid(0.0, 0.0, BW, BH, g=0.1, clearance=CLEAR, slack=0.05,
                    widths={"sig": 0.2, "pwr": NECK_W, "wide": WIDE_W}, via=(VIA_D, VIA_DRILL))
    nid = {n: i + 1 for i, n in enumerate(sorted(nets))}
    assert len(nid) < 250
    NCID = 253
    g.mark_outline(OUTLINE, 0.3)
    ux, uy, _ = U1_POS
    g.tag_rect([0], (ux - 7.3, uy - 8.2, ux + 7.3, uy + 8.2), TAG_MODULE)      # no L1 routing under the module
    for r in ANALOG_RECTS:
        g.tag_rect([0, 1, 2], r, TAG_ANALOG)
    for fp in fps.values():                                                     # footprint rule areas (TC2030 legs)
        for z in fp.Zones():
            if z.GetIsRuleArea():
                o = z.Outline().Outline(0)
                poly = [to_xy(o.CPoint(i)) for i in range(o.PointCount())]
                xs = [q[0] for q in poly]; ys = [q[1] for q in poly]
                for i, x, y in g._bbox_cells(min(xs) - 0.5, min(ys) - 0.5, max(xs) + 0.5, max(ys) + 0.5):
                    if router.poly_dist(x, y, poly) <= 0.45:
                        g.novia[i] = 1
                        if z.GetDoNotAllowTracks():
                            for cl in g.cls:
                                for l in range(3):
                                    g.own[cl][l][i] = router.HARD
    pads = {}
    for ref, fp in fps.items():
        for p in fp.Pads():
            net = p.GetNetname()
            k = nid.get(net, NCID)
            if p.GetAttribute() == P.PAD_ATTRIB_NPTH:
                x, y = to_xy(p.GetPosition())
                g.mark_hole((x, y), P.ToMM(p.GetDrillSize().x) / 2)
                continue
            pth = p.GetAttribute() == P.PAD_ATTRIB_PTH
            layers = [0, 1, 2] if pth else ([0] if p.IsOnLayer(P.F_Cu) else ([2] if p.IsOnLayer(P.B_Cu) else []))
            if not layers:
                continue
            poly = pad_poly(p, P.F_Cu if 0 in layers else P.B_Cu)
            # RF pads keep the coplanar gap to everything
            g.mark_poly(layers, poly, k, extra=(RF_GAP - CLEAR) if net in RF_NETS else 0.0)
            if pth:
                x, y = to_xy(p.GetPosition())
                g.mark_via_hole((x, y), hole_r=P.ToMM(p.GetDrillSize().x) / 2)
            else:
                xs = [q[0] for q in poly]; ys = [q[1] for q in poly]
                for i, x, y in g._bbox_cells(min(xs), min(ys), max(xs), max(ys)):
                    if router.in_poly(x, y, poly):
                        g.novia[i] = 1
            pads.setdefault((ref, p.GetNumber()), []).append(dict(poly=poly, layers=layers, net=net, c=to_xy(p.GetPosition())))
    # neck zones round the wide nets' small L1 pads
    for (ref, num), lst in pads.items():
        for pd in lst:
            if pd["net"] in WIDE_NETS and 0 in pd["layers"]:
                xs = [q[0] for q in pd["poly"]]; ys = [q[1] for q in pd["poly"]]
                if min(max(xs) - min(xs), max(ys) - min(ys)) >= WIDE_W + 0.1:
                    continue
                for i, x, y in g._bbox_cells(min(xs) - NECK_ZONE, min(ys) - NECK_ZONE, max(xs) + NECK_ZONE, max(ys) + NECK_ZONE):
                    g.neck[i] = nid[pd["net"]]
    gnd = netinfo["GND"]
    gid = nid["GND"]
    stub_nets = set()
    for ra, pa, rb, pb in STUBS:
        a, e = pads[(ra, pa)][0], pads[(rb, pb)][0]
        net = a["net"]
        assert net == e["net"] and len(nets[net]) == 2, (ra, pa, rb, pb)
        pts = [a["c"], (e["c"][0], a["c"][1]), e["c"]]
        for p0, p1 in zip(pts, pts[1:]):
            if math.dist(p0, p1) > 1e-6:
                add_track(b, netinfo[net], P.F_Cu, p0, p1, 0.25)
                g.mark_seg([0], p0, p1, 0.25, nid[net])
        stub_nets.add(net)
    fence = []
    rf_len = rf_preroute(b, g, pads, nid, netinfo, fence)
    placed = []
    nf = stitch(b, g, gid, gnd, placed, fence)
    fan = gnd_fanout(b, g, pads, gid, gnd, placed, log)
    per, inner = perimeter_and_grid()
    stitch(b, g, gid, gnd, placed, per)
    terms_extra = {("U1", k): v for k, v in module_fanout(b, g, fps["U1"], nid, netinfo, log).items()}

    failed = []
    for name in route_order(nets):
        if name == "GND" or name in RF_NETS or name in stub_nets:
            continue
        k = nid[name]
        cls = "wide" if name in WIDE_NETS else "sig"
        w = g.widths[cls]
        groups, labels = [], []
        for ref, pin in nets[name]:
            if (ref, pin) in terms_extra:
                groups.append(terms_extra[(ref, pin)]); labels.append(f"{ref}.{pin}(via)")
                continue
            cells = set()
            for pd in pads.get((ref, pin), []):
                cells |= term_cells(g, pd)
            if not cells:
                log.append(f"no terminal cells {name} {ref}.{pin}")
                continue
            groups.append(cells); labels.append(f"{ref}.{pin}")
        if len(groups) < 2:
            continue
        if name in WIDE_NETS:
            layers = [0, 2]                         # 35 um outer copper only
        elif name in ANALOG_NETS:
            layers = [0]
        else:
            layers = [0, 1, 2]
        forbid = {}
        if name in NOISY_NETS:
            forbid = {0: (TAG_ANALOG,), 1: (TAG_ANALOG,), 2: (TAG_ANALOG,)}
        forbid[0] = tuple(set(forbid.get(0, ())) | {TAG_MODULE})
        via_cost = 30.0 if name in ANALOG_NETS else 10.0
        lcost = (1.0, 1.6, 1.3) if name in ANALOG_NETS or name in WIDE_NETS else (1.6, 1.0, 1.3)
        ties = [gr for gr, lb in zip(groups, labels) if tuple(lb.split(".")) in LOGIC_TIES]
        main = [gr for gr in groups if not any(gr is t for t in ties)]
        tree = set(main[0])
        rest = main[1:] + ties
        ok = True
        while rest:
            tie = not [r for r in rest if not any(r is t for t in ties)]
            ccls, clay = ("sig", [0, 1, 2]) if tie else (cls, layers)
            targets = set().union(*rest)
            path = g.astar(tree, targets, k, ccls, clay, forbid, via_cost=via_cost, layer_cost=lcost)
            if path is None and name in ANALOG_NETS and name not in WIDE_NETS:
                path = g.astar(tree, targets, k, ccls, [0, 1, 2], forbid, via_cost=via_cost, layer_cost=lcost)
            if path is None:
                ok = False
                break
            segs, vias = g.to_segments(path, ccls, k, forbid)
            g.commit(segs, vias, g.widths[ccls], k)
            for l, a, c, sw in segs:
                add_track(b, netinfo[name], LAYERS[l], a, c, sw)
            for v in vias:
                add_via(b, netinfo[name], v)
            end = path[-1]
            # the tree grows by the copper actually laid (the string-pulled segments), not by the raw A* cells: a later
            # branch must not start from a cell the pulled track no longer passes through (dangling-track bug)
            tree.add(path[-1])
            for l, a, c, _sw in segs:
                n = max(1, int(math.dist(a, c) / (g.g / 2)))
                for s_ in range(n + 1):
                    i = g.cell(a[0] + (c[0] - a[0]) * s_ / n, a[1] + (c[1] - a[1]) * s_ / n)
                    if i is not None:
                        tree.add((l, i))
            for v in vias:
                i = g.cell(*v)
                for l in range(3):
                    tree.add((l, i))
            for r in [r for r in rest if end in r]:
                tree |= r
                rest.remove(r)
        if not ok:
            failed.append(name)
            log.append(f"FAILED {name}: unreached {[labels[groups.index(r)] for r in rest]} (tree from {labels[0]})")
    stitch(b, g, gid, gnd, placed, inner)
    return failed, fan, nf, rf_len


# ---------------------------------------------------------------------------------------------------------------
def zones(b, netinfo):
    import pcbnew as P
    gnd = netinfo["GND"]
    for layer in (P.F_Cu, P.In1_Cu, P.In2_Cu, P.B_Cu):
        z = P.ZONE(b)
        z.SetLayer(layer); z.SetNet(gnd)
        z.SetLocalClearance(mm(0.2))
        z.SetMinThickness(mm(0.2))
        z.SetThermalReliefGap(mm(0.25)); z.SetThermalReliefSpokeWidth(mm(0.3))
        z.SetPadConnection(P.ZONE_CONNECTION_THERMAL)
        z.SetIslandRemovalMode(P.ISLAND_REMOVAL_MODE_ALWAYS)
        ol = z.Outline(); ol.NewOutline()
        for x, y in OUTLINE:
            ol.Append(mm(OX + x), mm(OY - y))
        b.Add(z)
    P.ZONE_FILLER(b).Fill(b.Zones())


def write_project():
    def cls(name, clearance, width, prio):
        return {"name": name, "clearance": clearance, "track_width": width, "via_diameter": VIA_D, "via_drill": VIA_DRILL,
                "microvia_diameter": 0.3, "microvia_drill": 0.1, "diff_pair_width": 0.2, "diff_pair_gap": 0.2,
                "diff_pair_via_gap": 0.25, "wire_width": 6, "bus_width": 12, "line_style": 0,
                "schematic_color": "rgba(0, 0, 0, 0.000)", "pcb_color": "rgba(0, 0, 0, 0.000)", "priority": prio}
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
                                "track_dangling": "warning", "starved_thermal": "warning"},
            "track_widths": [0.0, 0.2, 0.3, RF_W, 0.5], "via_dimensions": [{"diameter": 0.0, "drill": 0.0}, {"diameter": VIA_D, "drill": VIA_DRILL}],
        }},
        "net_settings": {
            "classes": [cls("Default", 0.127, 0.2, 2147483647), cls("Power", 0.15, WIDE_W, 1), cls("Audio_I", 0.15, WIDE_W, 2),
                        cls("RF_50R", RF_GAP, RF_W, 0)],
            "meta": {"version": 4},
            "netclass_patterns": [{"netclass": "Power", "pattern": n} for n in POWER_NETS] +
                                 [{"netclass": "Audio_I", "pattern": n} for n in AUDIO_I_NETS] +
                                 [{"netclass": "RF_50R", "pattern": n} for n in RF_NETS],
        },
        "meta": {"filename": "rx.kicad_pro", "version": 3},
    }
    PRO.write_text(json.dumps(pro, indent=2) + "\n")


def save(b):
    import pcbnew as P
    P.SaveBoard(str(BOARD), b)
    txt = BOARD.read_text()
    txt = re.sub(r"(\t\(setup\n)", lambda m: m.group(1) + pk.stackup_sexp() + "\n", txt, count=1)
    BOARD.write_text(txt)


# ---------------------------------------------------------------------------------------------------------------
# board facts without pcbnew (tests)
# ---------------------------------------------------------------------------------------------------------------
def segments(path=BOARD):
    return pk.segments(path)


def drc(out=None):
    out = out or (HERE / "out" / "drc.json")
    out.parent.mkdir(exist_ok=True)
    # --save-board keeps the refilled zones: only kicad-cli's fill sees rx.kicad_pro's netclass clearances (the RF_50R
    # 0.25 mm coplanar gap); the pcbnew Python fill used the zone's 0.2 mm, and the fab outputs export the saved fill
    subprocess.run(["kicad-cli", "pcb", "drc", "--format", "json", "--severity-all", "--refill-zones", "--save-board",
                    "-o", str(out), str(BOARD)], capture_output=True, text=True)
    rep = json.loads(out.read_text())
    errs = [v for v in rep.get("violations", []) if v.get("severity") == "error"]
    warns = [v for v in rep.get("violations", []) if v.get("severity") == "warning"]
    return rep, errs, warns, rep.get("unconnected_items", [])


def main(argv):
    b, fps, netinfo, nets = build()
    bad = legalize(fps)
    if bad:
        print("courtyard overlaps:", bad)
    log = []
    failed, fan, nf, rf_len = route(b, fps, netinfo, nets, log)
    for line in log:
        print(line)
    print(f"GND fanout vias: {fan}; RF fence vias: {nf}; RF line lengths: { {k: round(v, 2) for k, v in rf_len.items()} }")
    print(f"failed nets: {failed}")
    zones(b, netinfo)
    write_project()
    save(b)
    rep, errs, warns, unconn = drc()
    print(pk.summarize(errs, warns, unconn))
    print(f"50 ohm GCPW L1/L2 (h {H_L1L2}, er {ER}): w {RF_W} mm, gap {RF_GAP} mm -> {rf_line.z_cal(RF_W, RF_GAP):.1f} ohm "
          f"(rf_line.py); microstrip would be {pk.width_for(50.0):.3f} mm")
    print("placement after legalize:", {k: v for k, v in PLACE.items()})
    if "--no-out" not in argv:
        outputs_rx = _load("hw_rx_outputs", HERE / "outputs_rx.py")
        outputs_rx.run_all()
    return 1 if (errs or unconn or failed) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
