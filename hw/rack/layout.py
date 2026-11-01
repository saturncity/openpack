"""OpenPack rack main board PCB (issue #34): netlist -> hw/rack/rack.kicad_pcb, regenerable.

Run with the python that carries KiCad's pcbnew module (KiCad 10):
    python3 hw/rack/layout.py            # place, RF copper, route, pour, DRC, fab outputs, renders
    python3 hw/rack/layout.py --no-out   # board + DRC only

Inputs: hw/rack/out/backplane.net (SKiDL, `python hw/rack/backplane.py --no-sch`), footprints_rack.py, the receiver's
mechanical record hw/rx/out/fab/mech.json. Templates: hw/pack/layout.py (helpers, stackup), hw/pack/router.py (grid
router, run here through hw/rack/wrouter.py in small windows so a 412 x 323 mm board stays tractable),
hw/rx/layout_rx.py (RF lines, solid RF grounds, keyed J1).
Frame: board mm, origin at the rear-left corner seen from above, x across the rack, y from the rear panel towards
the front; KiCad gets X = 100 + x, Y = 100 - y.

Floor plan (hw/REVIEW.md, rack section, has the reasoning):
  y   0..19   rear-panel connectors: 8 XLR (one behind each slot), BNC B / BNC A / DC jack in the gaps between them
  y  13..37   RF front ends (BNC -> ESD/bias-T -> QPL9057 -> QPQ1907), power entry (fuse, P-FET, TVS, input eFuse)
  y  33..62   Wilkinson tree B (root at the rear), then the 16 u.FL ports in one row just behind the receivers
  y  78..93   Wilkinson tree A (root at the front), under the receivers, in front of their M3 standoffs
  y  70..160  the 8 receivers (48 x 90 mm, 52 mm pitch) on their sockets, 11 mm above the board
  y 160..200  per-slot eFuses and test pads, +12 V / +5 V bus pours on B.Cu, 5 V buck
  y 200..323  host: SC16IS752 x 2, ribbon header, CM4 IO board on 10 mm spacers above; front LEDs at the edge

Stackup (JLCPCB JLC04161H-7628, 1.6 mm): L1 RF + parts + GND pour / L2 solid GND / L3 GND pour + digital /
L4 power pours, audio, chassis strip, GND pour. Every current path is on 35 um outer copper (#104 review M1).
"""
import importlib.util, json, math, pathlib, re, subprocess, sys, time

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


pk = _load("hw_pack_layout_r", ROOT / "hw" / "pack" / "layout.py")
router = pk.router
wr = _load("hw_rack_wrouter", HERE / "wrouter.py")
fpr = _load("hw_rack_footprints", HERE / "footprints_rack.py")

NETLIST = HERE / "out" / "backplane.net"
BOARD = HERE / "rack.kicad_pcb"
PRO = HERE / "rack.kicad_pro"
OUT = HERE / "out"
OX, OY = pk.OX, pk.OY
KICAD_FP = pk.KICAD_FP
STACKUP = pk.STACKUP

# ---------------------------------------------------------------------------------------------------------------
# Mechanics. Case: Hammond RM1U1913SBK (Hammond drawing RM1U1913SBK: inside 415.30 wide x 323.85 deep x 40.09 high,
# 3.18 mm end panels). The board fills the inside: rear edge on the rear panel's inner face (the connector flanges
# sit there), front edge 0.85 mm short of the front panel. mech/rack.py builds the case around these numbers.
# ---------------------------------------------------------------------------------------------------------------
CASE_IN = (415.30, 323.85, 40.09)
BW, BD = 412.0, 323.0
BOARD_X0 = (CASE_IN[0] - BW) / 2           # board x = 0 sits 1.65 mm from the left wall
STANDOFF = 5.0                              # board underside above the case floor (M3 x 5 spacers)
BOARD_T = 1.6
OUTLINE = [(0.0, 0.0), (BW, 0.0), (BW, BD), (0.0, BD)]

RX_MECH = json.loads((ROOT / "hw" / "rx" / "out" / "fab" / "mech.json").read_text())
PITCH = RX_MECH["slot_pitch_min"]           # 52.0
SUB_W, SUB_L = RX_MECH["board"]             # 48 x 90
N_SLOTS = 8
Y0 = 70.0                                   # receiver rear edge (its far end from J1)
assert (N_SLOTS - 1) * PITCH + SUB_W <= BW


def sub_xy(k, u, v):
    """receiver-frame point (u right, v up from its J1 end, as hw/rx/layout_rx.py) -> main board, slot k. The
    receiver sits turned 180 deg: its J1 end towards the front, its u.FL end towards the rear panel."""
    return (PITCH * k + SUB_W - u, Y0 + SUB_L - v)


def j1_pin(k, n):
    c = (n - 1) // 2
    u = RX_MECH["j1_pin1"][0] + RX_MECH["j1_pitch"] * c
    v = RX_MECH["j1_pin1"][1] if n % 2 else RX_MECH["j1_pin1"][1] - RX_MECH["j1_pitch"]
    return sub_xy(k, u, v)


SUB_HOLES = {k: [sub_xy(k, *RX_MECH["mount_m3"][h]) for h in ("H1", "H2")] for k in range(N_SLOTS)}
SUB_UFL = {k: {"A": sub_xy(k, 8.8, 79.0), "B": sub_xy(k, 8.8, 85.5)} for k in range(N_SLOTS)}   # receiver J3 / J4
XLR_X = [PITCH * k + SUB_W / 2 for k in range(N_SLOTS)]           # each XLR right behind its slot
GAP_X = [PITCH * k + SUB_W + (PITCH - SUB_W) / 2 for k in range(N_SLOTS - 1)]   # 50, 102, ... between XLRs
BNC_X = {"A": GAP_X[3], "B": GAP_X[2]}      # 206 / 154
DCJ_X = GAP_X[6]                            # 362
DCJ_AXIS = 6.5                              # PJ-063AH centre above the board (Same Sky drawing; JLC record "6.5mm")
# CM4 IO board (cm4io-datasheet Figure 2: 160 x 90, M2.5 holes at (11, 8) (145, 8) (11, 77) (145, 77)), turned 180 deg
# so its connector edge faces the front panel: frame (u, v) -> (CM4IO_XR - u, CM4IO_YF - v), on 10 mm spacers
CM4IO_XR, CM4IO_YF, CM4IO_SPACER = 402.0, 318.0, 10.0
CM4IO_HOLES = [(CM4IO_XR - u, CM4IO_YF - v) for u, v in ((11, 8), (145, 8), (11, 77), (145, 77))]
CM4IO_RECT = (CM4IO_XR - 160.0, CM4IO_YF - 90.0, CM4IO_XR, CM4IO_YF)
CASE_HOLES = [(4.0, 30.0), (BW - 4.0, 30.0), (4.0, 205.0), (BW - 4.0, 205.0), (4.0, BD - 4.0), (BW - 4.0, BD - 4.0),
              (206.0, 214.0), (150.0, BD - 4.0)]

# ---------------------------------------------------------------------------------------------------------------
# RF: 50 / 70.7 ohm lines on L1 over the solid L2 plane, 0.5 mm gap to the L1 pour (near-microstrip). Widths from the
# 2D field solve (hw/rx/rf_line.py solve(): raw bare copper, 5 um grid, h 0.2104, er 4.4; run 2026-11-01):
#   0.35 / gap 0.5 -> 50.17 ohm, eeff 3.099     0.17 / gap 0.5 -> 70.25 ohm, eeff 2.902
# lambda/4 of the 70.7 ohm arm from that eeff at 2441.75 MHz. hw/rack/rf_routed.py re-checks the tree as drawn.
# ---------------------------------------------------------------------------------------------------------------
RF_SOLVE = {(0.35, 0.5): (50.17, 3.099), (0.34, 0.5): (50.96, 3.09), (0.36, 0.5): (49.41, 3.108),
            (0.17, 0.5): (70.25, 2.902), (0.18, 0.5): (68.66, 2.916), (0.16, 0.5): (71.93, 2.888),
            (0.25, 0.5): (59.46, 3.001)}       # 0.25: the shunt-part stubs only (each <= 1.5 mm, < lambda/45)
W50, W70, RF_GAP = 0.35, 0.17, 0.5
F0 = 2441.75e6
LQ = 299792458.0 / (4 * F0 * math.sqrt(RF_SOLVE[(W70, RF_GAP)][1])) * 1e3       # 18.02 mm
R_HALF = 0.51                                # R_0402 pad centres at +-0.51: the isolation resistor bridges the arms
DIV_A = 7.0                                  # divider half-width: arm = A out, H up, A - 0.51 back in
DIV_H = LQ - 2 * DIV_A + R_HALF              # ~4.53 mm
OUT_RISE = 1.3                               # output escape beyond the resistor
TIE_OFF = 0.6                                # TL net tie centre from the junction (pad 1 0.2 mm, pad 2 1.0 mm away)
FENCE_OFF, FENCE_PITCH = 1.15, 1.5           # via fence: 1.15 mm off the line centre, ~lambda/26 pitch in FR4
PORT = {"A": (38.0, 60.0, 1), "B": (32.0, 62.0, -1)}     # x offset in the slot, y, side of the RF pad (+1 = front)
# tree stage centres (x) and junction y; "up" = input from the rear, outputs to the front
TREE = {
    "B": {"s1": [(214.0, 33.0)], "s2": [(110.0, 40.33), (318.0, 40.33)],
          "s3": [(58.0 + 104 * j, 47.66) for j in range(4)], "up": (True, True, True)},
    "A": {"s1": [(220.0, 87.0)], "s2": [(116.0, 91.3), (324.0, 91.3)],
          "s3": [(64.0 + 104 * j, 83.8) for j in range(4)], "up": (True, False, False)},
}
RF_CHAIN_TOP = 27.6
A_HOP = [(206.0, 29.2), (220.0, 43.0)]       # tree A's feed dives to B.Cu under tree B's root, back up at (220, 43)
# L1 here belongs to the RF lines: no other net routes on F.Cu (the power entry, right of x 336 below y 45.5, is not RF)
RF_ZONE = [(0.0, 31.0, 336.0, 96.0), (336.0, 45.5, BW, 96.0)]

VIA_D, VIA_DRILL = 0.6, 0.3
CLEAR = 0.15
WIDTHS = {"sig": 0.2, "pwr": 0.3, "wide": 0.5, "big": 1.5}
WIDE_W, NECK_W, BIG_W = 0.5, 0.3, 1.5

# ---------------------------------------------------------------------------------------------------------------
# net classes
# ---------------------------------------------------------------------------------------------------------------
BIG_NETS = ("+12V_IN", "+12V_RAW", "+12V_PROT", "BUCK_SW")      # 3-4 A, track-fed (+12V_BUS / +5V are pours)
POWER_NETS = BIG_NETS + ("+12V_BUS", "+5V", "+3V3", "+12V_HOST", "+5V_LNA_A", "+5V_LNA_B", "BIAS_A_DC", "BIAS_B_DC",
                         "BIAS_A_RF", "BIAS_B_RF") + \
    tuple(f"+12V_S{k}" for k in range(N_SLOTS)) + tuple(f"+5V_S{k}" for k in range(N_SLOTS))
AUDIO_NETS = tuple(f"S{k}_AUD_{s}" for k in range(N_SLOTS) for s in ("HOT", "COLD"))
WIDE_NETS = POWER_NETS + AUDIO_NETS
# +12V_BUS on B.Cu: a rear strip behind the XLRs (feeds the bias eFuses and the input eFuse's output), a spine at
# x 358-364 up the gap between slots 6 and 7, and a front strip along the slot eFuses; +5V a front strip and a pocket
# under the buck. The audio legs cross the rear strip on F.Cu (hops of a few mm); nothing else crosses a pour.
ZONES_B = {"+12V_BUS": [(143.0, 21.6), (364.0, 21.6), (364.0, 160.6), (410.5, 160.6), (410.5, 165.0), (1.5, 165.0),
                        (1.5, 160.6), (358.0, 160.6), (358.0, 25.4), (143.0, 25.4)],
           "+5V": [(1.5, 166.0), (410.5, 166.0), (410.5, 170.4), (230.0, 170.4), (230.0, 197.0), (196.0, 197.0),
                   (196.0, 170.4), (1.5, 170.4)],
           "CHASSIS": [(0.4, 0.4), (BW - 0.4, 0.4), (BW - 0.4, 21.0), (0.4, 21.0)]}
BUCK_SW_ZONE = [(213.45, 184.2), (219.0, 184.2), (219.0, 188.2), (216.4, 188.2), (216.4, 186.45), (215.6, 186.45),
                (215.6, 185.42), (213.45, 185.42)]
RF_SOLID_GND = ("J3", "J4") + tuple(f"J{30 + k}" for k in range(N_SLOTS)) + tuple(f"J{40 + k}" for k in range(N_SLOTS)) + \
    ("U6", "U7", "U8", "U9")


def is_rf(net):
    if not net:
        return False
    return net.startswith(("ANT_", "SPL_", "WK_", "RF_A", "RF_B")) or net in (
        "LNA_A_IN", "LNA_B_IN", "LNA_A_RFIN", "LNA_B_RFIN", "LNA_A_RFOUT", "LNA_B_RFOUT", "LNA_A_OUT", "LNA_B_OUT")


# ---------------------------------------------------------------------------------------------------------------
def mm(v):
    return pk.mm(v)


def V(x, y):
    return pk.V(x, y)


def to_xy(p):
    return pk.to_xy(p)


def fp_path(lib_fp):
    lib, name = lib_fp.split(":")
    d = fpr.LIB if lib == "openpack" else KICAD_FP / f"{lib}.pretty"
    return d, name


def read_netlist(path=NETLIST):
    return pk.read_netlist(path)


def pad_xy(fp, num):
    return [to_xy(p.GetPosition()) for p in fp.Pads() if p.GetNumber() == num]


def orient_pins(fp, want):
    """rotate (0/90/180/270) and translate so the first two pads of `want` land where wanted"""
    (n1, p1), (n2, p2) = list(want.items())[:2]
    for rot in (0, 90, 180, 270):
        fp.SetOrientationDegrees(rot)
        fp.SetPosition(V(0, 0))
        a, b = pad_xy(fp, n1)[0], pad_xy(fp, n2)[0]
        d = (b[0] - a[0], b[1] - a[1])
        w = (p2[0] - p1[0], p2[1] - p1[1])
        if abs(d[0] - w[0]) < 1e-3 and abs(d[1] - w[1]) < 1e-3:
            fp.SetPosition(V(p1[0] - a[0], p1[1] - a[1]))
            return rot
    raise SystemExit(f"{fp.GetReference()}: no rotation gives {want}")


def face(fp, pads_from, pads_to, vec):
    """keep the centre; pick the rotation that best points pads_from -> pads_to along vec"""
    c = to_xy(fp.GetPosition())
    best = None
    for rot in (0, 90, 180, 270):
        fp.SetOrientationDegrees(rot)
        fp.SetPosition(V(*c))
        a = [q for p in fp.Pads() if p.GetNumber() in pads_from for q in [to_xy(p.GetPosition())]]
        b = [q for p in fp.Pads() if p.GetNumber() in pads_to for q in [to_xy(p.GetPosition())]]
        ax, ay = sum(q[0] for q in a) / len(a), sum(q[1] for q in a) / len(a)
        bx, by = sum(q[0] for q in b) / len(b), sum(q[1] for q in b) / len(b)
        s = (bx - ax) * vec[0] + (by - ay) * vec[1]
        if best is None or s > best[0] + 1e-6:
            best = (s, rot)
    fp.SetOrientationDegrees(best[1])
    fp.SetPosition(V(*c))
    return best[1]


# ---------------------------------------------------------------------------------------------------------------
# parts by role (the netlist's refdes numbering is SKiDL's)
# ---------------------------------------------------------------------------------------------------------------
class Parts:
    def __init__(self, comps, nets):
        self.comps = comps
        self.pins = {}
        for net, nodes in nets.items():
            for r, p in nodes:
                self.pins.setdefault(r, {})[p] = net

    def on(self, net, prefix=None, value=None):
        out = [r for r, p in self.pins.items() if net in p.values() and (prefix is None or re.fullmatch(prefix + r"\d+", r))
               and (value is None or self.comps[r]["value"] == value)]
        return sorted(out, key=lambda r: int(re.sub(r"\D", "", r) or 0))

    def one(self, net, prefix=None, value=None):
        r = self.on(net, prefix, value)
        assert len(r) == 1, (net, prefix, value, r)
        return r[0]

    def pad_on(self, ref, net):
        return [p for p, n in self.pins[ref].items() if n == net]


def efuse_parts(P, u):
    """an efuse() block of backplane.py: ILM resistor, dV/dt cap, input cap (the C after dV/dt), output cap"""
    ilm = P.one(f"{u}_ILM", "R")
    dv = P.one(f"{u}_DVDT", "C")
    n = int(dv[1:])
    cin, cout = f"C{n + 1}", f"C{n + 2}"
    assert P.pins[cin]["2"] == "GND" and P.pins[cout]["2"] == "GND", (u, cin, cout)
    return ilm, dv, cin, cout


def chain_parts(P, ant):
    """RF front end of one antenna, in signal order, with the bias-T / LNA-supply side parts"""
    d = {}
    d["bnc"] = {"A": "J3", "B": "J4"}[ant]
    d["esd1"] = P.one(f"ANT_{ant}", "D", "ESD103-B1-02EL")
    d["choke"] = P.one(f"BIAS_{ant}_RF", "L")
    d["dcb"] = [c for c in P.on(f"LNA_{ant}_IN", "C") if f"ANT_{ant}" in P.pins[c].values()][0]
    d["esd2"] = P.one(f"LNA_{ant}_IN", "D")
    d["r0"] = P.one(f"LNA_{ant}_RFIN", "R")
    d["lna"] = {"A": "U6", "B": "U7"}[ant]
    d["lch"] = P.one(f"LNA_{ant}_RFOUT", "L")
    d["cout"] = P.one(f"LNA_{ant}_OUT", "C")
    d["bpf"] = {"A": "U8", "B": "U9"}[ant]
    d["cbias"] = P.on(f"BIAS_{ant}_RF", "C")
    d["r2512"] = P.one(f"BIAS_{ant}_RF", "R")
    d["tvs"] = P.one(f"BIAS_{ant}_DC", "D")
    d["efb"] = {"A": "U10", "B": "U11"}[ant]
    d["en"] = P.one(f"HOST_GPIO{22 if ant == 'A' else 23}", "R")
    d["fl"] = P.one(f"HOST_GPIO{26 if ant == 'A' else 27}", "R")
    d["fb"] = P.one(f"+5V_LNA_{ant}", "FB")
    d["rb"] = P.one(f"LNA_{ant}_VBIAS", "R")
    d["cvb"] = P.one(f"LNA_{ant}_VBIAS", "C")
    d["csup"] = P.on(f"+5V_LNA_{ant}", "C")
    d["tps"] = P.on(f"BIAS_{ant}_DC", "TP") + P.on(f"+5V_LNA_{ant}", "TP")
    return d


def placement(P):
    """ref -> (x, y, rot) | ("pins", {pad: xy}) | (x, y, ("face", from_pads, to_pads, vec))"""
    pl = {}
    # ---- rear-panel connectors ----
    for k in range(N_SLOTS):
        xc = XLR_X[k]
        pl[f"J{20 + k}"] = (xc, 17.78, 180)                       # NC3MAH: contacts 17.78 from the panel line
        hot, cold = P.one(f"S{k}_AUD_HOT", "D"), P.one(f"S{k}_AUD_COLD", "D")
        pl[hot] = (xc + 7.4, 24.4, ("face", ("2",), ("1",), (0, 1)))     # SMAJ58CA, chassis pad to the rear
        pl[cold] = (xc + 3.0, 24.4, ("face", ("2",), ("1",), (0, 1)))
    for ant, ref in (("A", "J3"), ("B", "J4")):
        pl[ref] = (BNC_X[ant], -fpr.BNC_TE["panel_y"], 180)       # centre pin 7.31 from the panel
    pl["J1"] = (DCJ_X, 12.0, 0)                                    # PJ-063AH: opening at the panel, centre pin 12 in
    # ---- RF front ends: a straight 50 ohm line up the gap from the BNC centre pin ----
    for ant in "AB":
        x0 = BNC_X[ant]
        s = 1 if ant == "A" else -1                                # bias-T side: A right, B left
        c = chain_parts(P, ant)
        line = ("face", None, None, (s, 0))
        pl[c["esd1"]] = (x0 + s * 0.86, 13.6, ("shunt", f"ANT_{ant}", x0))
        pl[c["choke"]] = (x0 + s * 1.2, 15.4, ("shunt", f"ANT_{ant}", x0))
        pl[c["dcb"]] = (x0, 17.0, ("series", f"ANT_{ant}", f"LNA_{ant}_IN"))
        pl[c["esd2"]] = (x0 - s * 0.86, 18.4, ("shunt", f"LNA_{ant}_IN", x0))
        pl[c["r0"]] = (x0, 19.8, ("series", f"LNA_{ant}_IN", f"LNA_{ant}_RFIN"))
        pl[c["lna"]] = (x0, 22.3, ("face", ("2",), ("7",), (0, 1)))
        pl[c["lch"]] = (x0 - s * 1.4, 24.6, ("shunt", f"LNA_{ant}_RFOUT", x0))
        pl[c["cout"]] = (x0, 25.0, ("series", f"LNA_{ant}_RFOUT", f"LNA_{ant}_OUT"))
        pl[c["bpf"]] = (x0, 27.0, ("face", ("1",), ("4",), (0, 1)))
        pl[c["cbias"][0]] = (x0 + s * 3.4, 15.8, 0)
        pl[c["cbias"][1]] = (x0 + s * 3.4, 17.6, 0)
        pl[c["r2512"]] = (x0 + s * 7.4, 15.8, 90)
        pl[c["tvs"]] = (x0 + s * 10.3, 15.2, ("face", ("2",), ("1",), (0, 1)))
        pl[c["efb"]] = (x0 + s * 8.6, 23.0, 0)
        ilm, dv, cin, co = efuse_parts(P, c["efb"])
        pl[ilm] = (x0 + s * 6.0, 25.6, 90); pl[dv] = (x0 + s * 7.2, 25.6, 90)
        pl[cin] = (x0 + s * 11.0, 25.6, 90); pl[co] = (x0 + s * 11.6, 21.0, 0)
        pl[c["en"]] = (x0 + s * 8.4, 26.2, 90); pl[c["fl"]] = (x0 + s * 9.6, 26.2, 90)
        pl[c["fb"]] = (x0 - s * 8.6, 26.6, 90)
        for i, cc in enumerate(c["csup"]):
            pl[cc] = (x0 - s * (4.2 + 1.3 * i), 26.6, 90)
        # QPL9057 pin 1 (VBIAS) sits 0.5 mm left of the RF input pin 2 for both chains (the footprint does not
        # mirror): its cap goes beside it and rf_frontend() draws the stub; the router cannot leave a pad that close
        # to an RF line. A's resistor shares the stub; B's stays on its supply side and the router joins it on In2.
        pl[c["cvb"]] = (x0 - 1.9, 22.45, 90)
        pl[c["rb"]] = (x0 - 1.9, 19.9, 90) if ant == "A" else (x0 + 2.7, 21.2, 90)
        pl[c["tps"][0]] = (x0 + s * 13.0, 19.6, 0)
        pl[c["tps"][1]] = (x0 - s * 10.6, 29.4, 0)
    # ---- power entry behind the DC jack ----
    x = DCJ_X
    pl["F1"] = (x, 18.4, 90)
    pl["Q1"] = (x, 26.2, 90)
    pl[P.one("Q1_G", "R")] = (x + 4.4, 30.6, 90); pl["D1"] = (x + 5.0, 33.2, 0)
    pl["D2"] = (x - 6.0, 29.0, 90)
    pl["C1"] = (x - 6.2, 36.2, 0)                                   # 100 uF 6.3 x 5.4 on +12V_PROT
    pl["U1"] = (x + 1.0, 35.6, 0)
    ilm, dv, cin, co = efuse_parts(P, "U1")
    pl[ilm] = (x + 2.0, 37.6, 180); pl[dv] = (x - 1.6, 39.0, 0); pl[cin] = (x - 1.8, 32.4, 0); pl[co] = (x + 4.0, 38.0, 90)
    en = P.on("U1_EN", "R")
    pl[en[0]] = (x + 5.4, 36.0, 90); pl[en[1]] = (x + 6.8, 36.0, 90)
    pl["C5"] = (x + 3.0, 42.6, 0); pl["C6"] = (x - 4.0, 44.0, 0)    # +12V_BUS bulk at the eFuse output, by the spine
    pl["NT1"] = (x - 10.6, 22.6, 90)
    pl[P.one("HOST_GPIO6", "R", "10k")] = (x + 8.6, 36.0, 90)
    pl[P.one("+12V_PROT", "TP")] = (x + 9.6, 26.6, 0)
    pl[P.one("HOST_GPIO6", "TP")] = (x + 9.6, 40.0, 0)
    gtp = P.on("GND", "TP")
    pl[gtp[0]] = (x + 9.6, 23.4, 0)
    pl[P.one("+12V_BUS", "TP")] = (x - 8.8, 40.8, 0)
    # ---- slots: sockets, eFuses, test pads, UART resistors (slots 0-3), front LEDs ----
    for k in range(N_SLOTS):
        sx = PITCH * k
        pl[f"J{10 + k}"] = ("pins", {"1": j1_pin(k, 1), "2": j1_pin(k, 2)})
        for u, dx in ((f"U{20 + k}", 12.0), (f"U{30 + k}", 32.0)):
            pl[u] = (sx + dx, 175.0, 0)
            ilm, dv, cin, co = efuse_parts(P, u)
            # ILM is pin 7 (right side, next to GND pin 8): its resistor sits just above-right, pad 1 inboard (#34)
            pl[ilm] = (sx + dx + 1.0, 177.0, 180); pl[dv] = (sx + dx - 1.8, 177.8, 90)
            pl[cin] = (sx + dx - 2.6, 173.0, 0); pl[co] = (sx + dx + 3.0, 177.4, 90)
        en = P.on(f"U{20 + k}_EN", "R")
        pl[en[0]] = (sx + 6.0, 172.6, 0); pl[en[1]] = (sx + 6.0, 174.4, 0)
        tps = [P.one(n, "TP") for n in (f"+12V_S{k}", f"+5V_S{k}", f"S{k}_BP_UART_TX", f"S{k}_BP_UART_RX", f"S{k}_BP_nRESET")]
        for i, t in enumerate(tps):
            pl[t] = (sx + 5.0 + 7.6 * i, 183.0, 0)
        for net in (f"S{k}_BP_UART_RX", f"S{k}_BP_UART_TX"):
            r = P.on(net, "R")
            if r:
                pl[r[0]] = (sx + 41.0, 172.2 if "RX" in net else 174.2, 0)
        for i, sig in enumerate(("LOCK", "PEAK")):
            led = P.one(f"S{k}_BP_LED_{sig}_A", "D")
            r = P.one(f"S{k}_BP_LED_{sig}", "R", "560")
            lx = sx + 18.0 + 12.0 * i
            pl[led] = (lx, BD - 1.25, 0)                             # lens at the board edge, through the front panel
            pl[r] = (lx + 3.0, BD - 2.6, 0)
    # ---- 5 V buck (TPS62933 reference layout, SLUSEA4D 10-1), 3.3 V LDO, CM4IO feed ----
    bx, by = 213.0, 186.0
    # SOT-583 pins (board y up): left 1 NC / 2 EN / 3 VIN / 4 GND top to bottom, right 8 FB / 7 SS / 6 BST / 5 SW.
    # SW is a small F.Cu pour (BUCK_SW_ZONE) from pin 5 to the inductor and the boot cap; BST leaves pin 6 to the
    # right, SS climbs past pin 8 to its cap, FB goes straight up to the divider, EN left to its divider (#34).
    pl["U2"] = (bx, by, 0)
    pl["L1"] = (bx + 6.9, by + 1.05, 0)                        # clear of slot 4's test pads (y 183)
    pl["C8"] = (bx + 2.32, by - 0.25, 0)                            # pad 1 BST beside pin 6, pad 2 on the SW pour
    pl["C11"] = (bx - 2.4, by - 0.7, 180)                           # 100 nF VIN-GND right at pins 3 / 4
    pl["C9"] = (bx - 4.4, by + 3.8, 90); pl["C10"] = (bx - 6.8, by + 3.8, 90)
    pl["C12"] = (bx + 7.0, by + 5.2, 0); pl["C13"] = (bx + 7.0, by + 7.4, 0); pl["C14"] = (bx + 3.8, by + 5.6, 90)
    en = P.on("BUCK_EN", "R"); pl[en[0]] = (bx - 3.6, by + 0.6, 0); pl[en[1]] = (bx - 2.1, by + 1.0, 90)
    pl[P.one("BUCK_SS", "C")] = (bx + 2.32, by + 1.4, 0)
    fb = P.on("BUCK_FB", "R"); pl[fb[0]] = (bx + 1.75, by + 3.0, 270); pl[fb[1]] = (bx + 0.75, by + 2.6, 90)
    pl[P.one("+5V", "TP")] = (bx - 7.0, by - 2.0, 0)
    pl["U3"] = (190.0, 214.0, 0); pl["C15"] = (186.4, 214.0, 90); pl["C16"] = (193.8, 214.0, 90)
    pl[P.one("+3V3", "TP")] = (190.0, 210.6, 0)
    pl["U12"] = (232.0, 300.0, 0)
    ilm, dv, cin, co = efuse_parts(P, "U12")
    pl[ilm] = (229.0, 302.6, 90); pl[dv] = (230.2, 302.6, 90); pl[cin] = (229.4, 297.8, 0); pl[co] = (235.0, 302.0, 90)
    en = P.on("U12_EN", "R"); pl[en[0]] = (227.6, 297.2, 90); pl[en[1]] = (226.2, 297.2, 90)
    pl["J5"] = (232.0, 309.5, 0)
    pl[P.one("+12V_HOST", "TP")] = (236.4, 305.6, 0)
    # ---- host: SC16IS752 x 2 (TSSOP-28), crystals, ribbon header ----
    for u, (ux, uy), y, crst, cx1, cx2, cdd in (("U4", (150.0, 232.0), "Y1", "C20", "C21", "C22", "C23"),
                                                 ("U5", (262.0, 214.0), "Y2", "C24", "C25", "C26", "C27")):
        pl[u] = (ux, uy, 0)
        pl[y] = (ux - 7.6, uy - 2.6, 0)
        pl[cx1] = (ux - 10.6, uy - 1.6, 90); pl[cx2] = (ux - 10.6, uy - 4.2, 90)
        pl[cdd] = (ux - 4.6, uy + 4.0, 90)
        pl[crst] = (ux - 4.6, uy + 0.4, 90)
        rst = P.one(f"{u}_RST", "R"); pl[rst] = (ux - 6.0, uy + 0.4, 90)
        irq = P.one(f"HOST_GPIO{24 if u == 'U4' else 25}", "R", "1k"); pl[irq] = (ux + 4.6, uy + 0.4, 90)
    pl["J2"] = ("pins", {"1": (166.0, 300.0), "3": (168.54, 300.0)})   # 2 x 20 box header, ribbon to the CM4IO J8
    host_r = P.on("+3V3", "R")
    for i, r in enumerate(x for x in host_r if x not in pl):
        pl[r] = (196.0 + 1.4 * i, 240.0, 90)
    for i, r in enumerate(P.on("GND", "R")):
        if r not in pl and any(n.startswith("HOST_GPIO") for n in P.pins[r].values()):
            pl[r] = (196.0 + 1.4 * i, 244.0, 90)
    tph = [P.one(f"HOST_GPIO{g}", "TP") for g in (21, 20, 19, 18, 17, 24, 25)]
    for i, t in enumerate(tph):
        pl[t] = (190.0 + 3.0 * i, 250.5, 0)
    pl[gtp[1]] = (190.0 + 3.0 * len(tph), 250.5, 0)
    pl[gtp[2]] = (206.0, 206.0, 0)
    return pl


# ---------------------------------------------------------------------------------------------------------------
def build():
    import pcbnew as P_
    fpr.write_lib()
    comps, nets = read_netlist()
    P = Parts(comps, nets)
    b = P_.BOARD()
    b.SetCopperLayerCount(4)
    netinfo = {}
    for name in sorted(nets):
        ni = P_.NETINFO_ITEM(b, name)
        b.Add(ni)
        netinfo[name] = ni
    for (x0, y0), (x1, y1) in zip(OUTLINE, OUTLINE[1:] + OUTLINE[:1]):
        s = P_.PCB_SHAPE(b)
        s.SetShape(P_.SHAPE_T_SEGMENT)
        s.SetStart(V(x0, y0)); s.SetEnd(V(x1, y1))
        s.SetLayer(P_.Edge_Cuts); s.SetWidth(mm(0.1))
        b.Add(s)
    pl = placement(P)
    for ref in comps:                     # placed by rf_copper(): parked off the board until then
        if ref not in pl and (ref.startswith("TL") or re.fullmatch(r"J[34]\d", ref) or
                              any(n.startswith("WK_") for n in P.pins[ref].values())):
            pl[ref] = (-100.0, -100.0, 0)
    missing = set(comps) - set(pl)
    assert not missing, sorted(missing)
    fps = {}
    for ref, c in sorted(comps.items()):
        d, name = fp_path(c["footprint"])
        fp = P_.FootprintLoad(str(d), name)
        if fp is None:
            raise SystemExit(f"footprint not found: {c['footprint']}")
        fp.SetReference(ref)
        fp.SetValue(c["value"])
        fp.SetFPID(P_.LIB_ID(c["footprint"].split(":")[0], name))
        b.Add(fp)
        fps[ref] = fp
    # nets before placement: face()/shunt rules look at pad nets
    for name, nodes in nets.items():
        for ref, pin in nodes:
            hit = 0
            for p in fps[ref].Pads():
                if p.GetNumber() == pin:
                    p.SetNet(netinfo[name]); hit += 1
            assert hit, (ref, pin)
    for ref, spec in pl.items():
        fp = fps[ref]
        if spec[0] == "pins":
            orient_pins(fp, spec[1])
            continue
        x, y, rot = spec
        fp.SetPosition(V(x, y))
        if isinstance(rot, tuple):
            kind = rot[0]
            if kind == "face":
                face(fp, rot[1], rot[2], rot[3])
            elif kind == "series":
                a, c_ = P.pad_on(ref, rot[1]), P.pad_on(ref, rot[2])
                face(fp, a, c_, (0, 1))
            elif kind == "shunt":
                on = P.pad_on(ref, rot[1])
                other = [p.GetNumber() for p in fp.Pads() if p.GetNumber() not in on]
                face(fp, on, other, (1 if x > rot[2] else -1, 0))
        else:
            fp.SetOrientationDegrees(rot)
    for ref, fp in fps.items():
        if ref[0] in "RCLDQY" or ref.startswith(("TP", "FB", "TL", "NT")):
            fp.Reference().SetVisible(False)
        else:
            fp.Reference().SetTextSize(P_.VECTOR2I(mm(1.0), mm(1.0)))
            fp.Reference().SetTextThickness(mm(0.15))
        fp.Value().SetVisible(False)
    # RF ground pads join the pours solidly, not through thermal spokes (#116 review S2)
    for ref in RF_SOLID_GND:
        for pad in fps[ref].Pads():
            if pad.GetNetname() == "GND":
                pad.SetLocalZoneConnection(P_.ZONE_CONNECTION_FULL)
    holes = {}
    for k in range(N_SLOTS):
        for j, xy in enumerate(SUB_HOLES[k]):
            holes[f"HS{k}{j}"] = (xy, "MountingHole_3.2mm_M3")
    for j, xy in enumerate(CM4IO_HOLES):
        holes[f"HC{j}"] = (xy, "MountingHole_2.7mm_M2.5")
    for j, xy in enumerate(CASE_HOLES):
        holes[f"H{j + 1}"] = (xy, "MountingHole_3.2mm_M3")
    for ref, (xy, name) in holes.items():
        fp = P_.FootprintLoad(str(KICAD_FP / "MountingHole.pretty"), name)
        fp.SetReference(ref)
        fp.SetFPID(P_.LIB_ID("MountingHole", name))
        fp.Reference().SetVisible(False); fp.Value().SetVisible(False)
        b.Add(fp)
        fp.SetPosition(V(*xy))
        fps[ref] = fp
    silk(b)
    return b, fps, netinfo, nets, P, pl


def silk(b):
    import pcbnew as P_
    texts = {"OpenPack rack main board #34": (60.0, 300.0, 1.5), "REAR PANEL": (30.0, 1.6, 1.0), "FRONT": (6.0, BD - 3.0, 1.0)}
    for k in range(N_SLOTS):
        a, c = j1_pin(k, 13), j1_pin(k, 14)
        texts[f"SLOT {k}"] = (PITCH * k + 24.0, 148.0, 1.2)
        texts[f"14 = KEY{' ' * k}"] = (c[0], c[1] + 2.6, 0.8)          # the key position, by each socket
        texts[f"OUT {k + 1}"] = (XLR_X[k], 28.2, 1.0)
        texts[f"A{k}" + " " * 0] = (PITCH * k + PORT["A"][0] + 2.6, PORT["A"][1] - 2.6, 0.8)
        texts[f"B{k}"] = (PITCH * k + PORT["B"][0] - 2.6, PORT["B"][1] + 2.6, 0.8)
    texts["ANT A"] = (BNC_X["A"], 31.6 - 0.0 + 0.0 - 0.0 + 0.0, 0.8)
    texts["ANT B"] = (BNC_X["B"] - 6.0, 31.8, 0.8)
    texts["12V IN 4A"] = (DCJ_X, 47.0, 1.0)
    texts["CM4 IO board above"] = (CM4IO_RECT[0] + 80.0, CM4IO_RECT[1] + 45.0, 1.5)
    for txt, (x, y, s) in texts.items():
        t = P_.PCB_TEXT(b)
        t.SetText(txt.strip()); t.SetLayer(P_.F_SilkS); t.SetPosition(V(x, y))
        t.SetTextSize(P_.VECTOR2I(mm(s), mm(s))); t.SetTextThickness(mm(0.15 if s < 1.2 else 0.2))
        b.Add(t)


# ---------------------------------------------------------------------------------------------------------------
def courtyard_boxes(fps):
    import pcbnew as P_
    boxes = {}
    for ref, fp in fps.items():
        cy = fp.GetCourtyard(P_.F_CrtYd)
        if cy.OutlineCount() == 0:
            continue
        bb = cy.BBox()
        x0, x1 = P_.ToMM(bb.GetLeft()) - OX, P_.ToMM(bb.GetRight()) - OX
        if x1 < -20:
            continue
        y0, y1 = OY - P_.ToMM(bb.GetBottom()), OY - P_.ToMM(bb.GetTop())
        boxes[ref] = (x0, x1, y0, y1)
    return boxes


def courtyard_overlaps(fps, t=0.03):
    boxes = courtyard_boxes(fps)
    bad = []
    refs = sorted(boxes)
    for i, a in enumerate(refs):
        A = boxes[a]
        for c in refs[i + 1:]:
            B = boxes[c]
            if A[0] + t < B[1] and B[0] + t < A[1] and A[2] + t < B[3] and B[2] + t < A[3]:
                bad.append((a, c))
    return bad


FIXED_PREFIX = ("J", "U", "H", "Q", "F")


def legalize(fps, pl, margin=0.1, passes=400):
    """nudge small parts until no courtyards overlap (connectors, ICs and holes stay put); every pass moves the
    later-placed part of each overlapping pair by the smallest step that clears it; moves snap to 0.05 mm"""
    order = {r: i for i, r in enumerate(pl)}
    for _ in range(passes):
        bad = courtyard_overlaps(fps)
        if not bad:
            break
        boxes = courtyard_boxes(fps)
        done = set()
        for a, c in bad:
            cand = [r for r in (c, a) if not r.startswith(FIXED_PREFIX) and r in pl and r not in done]
            if not cand:
                continue
            mv = max(cand, key=lambda r: order[r])
            other = a if mv == c else c
            A, O = boxes[mv], boxes[other]
            opts = [(O[1] - A[0] + margin, 0), (-(A[1] - O[0] + margin), 0), (0, O[3] - A[2] + margin),
                    (0, -(A[3] - O[2] + margin))]
            opts.sort(key=lambda d: abs(d[0]) + abs(d[1]))
            for dx, dy in opts:
                if A[0] + dx < 0.4 or A[1] + dx > BW - 0.4 or A[2] + dy < 0.4 or A[3] + dy > BD - 0.4:
                    continue
                x, y = to_xy(fps[mv].GetPosition())
                fps[mv].SetPosition(V(round((x + dx) * 20) / 20, round((y + dy) * 20) / 20))
                boxes[mv] = (A[0] + dx, A[1] + dx, A[2] + dy, A[3] + dy)
                done.add(mv)
                break
    return courtyard_overlaps(fps)


# ---------------------------------------------------------------------------------------------------------------
# copper database for the windowed router
# ---------------------------------------------------------------------------------------------------------------
def pad_poly(pad, layer):
    return pk.pad_poly(pad, layer)


def fill_copper(fps):
    import pcbnew as P_
    cu = wr.Copper(router, (0.0, 0.0, BW, BD), edge_clr=0.3, clearance=CLEAR, widths=dict(WIDTHS), via=(VIA_D, VIA_DRILL))
    pads = {}
    for ref, fp in fps.items():
        for p in fp.Pads():
            net = p.GetNetname()
            if p.GetAttribute() == P_.PAD_ATTRIB_NPTH:
                x, y = to_xy(p.GetPosition())
                cu.hole((x, y), P_.ToMM(p.GetDrillSize().x) / 2)
                continue
            pth = p.GetAttribute() == P_.PAD_ATTRIB_PTH
            layers = (0, 1, 2) if pth else ((0,) if p.IsOnLayer(P_.F_Cu) else ((2,) if p.IsOnLayer(P_.B_Cu) else ()))
            if not layers:
                continue
            poly = pad_poly(p, P_.F_Cu if 0 in layers else P_.B_Cu)
            hole = (to_xy(p.GetPosition()), P_.ToMM(max(p.GetDrillSize().x, p.GetDrillSize().y)) / 2) if pth else None
            it = cu.pad(layers, poly, net, extra=0.25 if is_rf(net) else 0.0, smd=not pth, hole=hole)
            it.conn = False
            pads.setdefault((ref, p.GetNumber()), []).append(it)
    # spacer / screw keep-outs round every mounting hole (spacer faces up to 3.3 mm radius, M2.5 2.9)
    for ref, fp in fps.items():
        if ref.startswith("H"):
            x, y = to_xy(fp.GetPosition())
            cu.keepout((0, 1, 2), (x, y, 3.4 if not ref.startswith("HC") else 3.0))
    return cu, pads


# ---------------------------------------------------------------------------------------------------------------
# RF copper: front ends, the two Wilkinson trees, port feeds. Every RF track is drawn here (not by the router) and
# logged in RF_LOG for hw/rack/rf_routed.py: per net the polyline, width and layer.
# ---------------------------------------------------------------------------------------------------------------
RF_LOG = []


def rf_track(b, cu, netinfo, net, pts, w, layer=0):
    import pcbnew as P_
    L = (P_.F_Cu, P_.In2_Cu, P_.B_Cu)[layer]
    for a, c in zip(pts, pts[1:]):
        if math.dist(a, c) < 1e-6:
            continue
        pk.add_track(b, netinfo[net], L, a, c, w)
        cu.seg(layer, a, c, w, net, extra=0.35)
    RF_LOG.append({"net": net, "w": w, "layer": wr.KL[layer], "pts": [[round(p[0], 4), round(p[1], 4)] for p in pts]})


def rf_via(b, cu, netinfo, net, c):
    pk.add_via(b, netinfo[net], c)
    cu.via_at(c, net)
    RF_LOG.append({"net": net, "via": [round(c[0], 4), round(c[1], 4)]})


def pc(fps, ref, num):
    return pad_xy(fps[ref], num)[0]


def rf_frontend(b, cu, fps, netinfo, P, ant):
    c = chain_parts(P, ant)
    x0 = BNC_X[ant]
    pin = pc(fps, c["bnc"], "1")
    dcb_a = pc(fps, c["dcb"], P.pad_on(c["dcb"], f"ANT_{ant}")[0])
    dcb_b = pc(fps, c["dcb"], P.pad_on(c["dcb"], f"LNA_{ant}_IN")[0])
    r0_a = pc(fps, c["r0"], P.pad_on(c["r0"], f"LNA_{ant}_IN")[0])
    r0_b = pc(fps, c["r0"], P.pad_on(c["r0"], f"LNA_{ant}_RFIN")[0])
    lin, lout = pc(fps, c["lna"], "2"), pc(fps, c["lna"], "7")
    co_a = pc(fps, c["cout"], P.pad_on(c["cout"], f"LNA_{ant}_RFOUT")[0])
    co_b = pc(fps, c["cout"], P.pad_on(c["cout"], f"LNA_{ant}_OUT")[0])
    bin_, bout = pc(fps, c["bpf"], "1"), pc(fps, c["bpf"], "4")
    # shunt parts: a stub from the line to the pad on the line's net
    stubs = []
    for ref, net in ((c["esd1"], f"ANT_{ant}"), (c["choke"], f"ANT_{ant}"), (c["esd2"], f"LNA_{ant}_IN"),
                     (c["lch"], f"LNA_{ant}_RFOUT")):
        stubs.append((net, pc(fps, ref, P.pad_on(ref, net)[0])))
    rf_track(b, cu, netinfo, f"ANT_{ant}", [pin, (x0, dcb_a[1] - 0.9), dcb_a], W50)
    rf_track(b, cu, netinfo, f"LNA_{ant}_IN", [dcb_b, r0_a], W50)
    # 50 ohm right up to the QPL9057 / QPQ1907 pins: each line enters its pin straight along the pin axis, 0.2 mm from
    # the GND pins either side (RF clearance 0.15); a diagonal into a 0.5 mm-pitch pin row would graze its neighbour
    rf_track(b, cu, netinfo, f"LNA_{ant}_RFIN", [r0_b, (r0_b[0], lin[1] - 0.75), (lin[0], lin[1] - 0.6), lin], W50)
    rf_track(b, cu, netinfo, f"LNA_{ant}_RFOUT", [lout, (lout[0], lout[1] + 0.6), (co_a[0], co_a[1] - 0.15), co_a], W50)
    rf_track(b, cu, netinfo, f"LNA_{ant}_OUT", [co_b, (co_b[0], bin_[1] - 0.6), (bin_[0], bin_[1] - 0.3), bin_], W50)
    for net, p in stubs:
        rf_track(b, cu, netinfo, net, [(x0, p[1]), p], 0.25)
    # LNA bias stub: pin 1 -> left -> the decoupling cap (and A's bias resistor); not RF, so not in RF_LOG
    vb = f"LNA_{ant}_VBIAS"
    p1 = pc(fps, c["lna"], "1")
    cv = pc(fps, c["cvb"], P.pad_on(c["cvb"], vb)[0])
    pts = [p1, (cv[0], p1[1]), cv]
    HAND.update({(c["lna"], "1"), (c["cvb"], P.pad_on(c["cvb"], vb)[0])})
    if ant == "A":
        rbp = pc(fps, c["rb"], P.pad_on(c["rb"], vb)[0])
        hand_track(b, cu, netinfo, vb, [(cv[0], p1[1]), rbp], 0.25)
        HAND.add((c["rb"], P.pad_on(c["rb"], vb)[0]))
    hand_track(b, cu, netinfo, vb, pts, 0.25)
    return bout


HAND = set()          # (ref, pad) joined by hand-drawn copper: the router treats them as connected


def hand_track(b, cu, netinfo, net, pts, w):
    import pcbnew as P_
    for a, c in zip(pts, pts[1:]):
        if math.dist(a, c) < 1e-6:
            continue
        pk.add_track(b, netinfo[net], P_.F_Cu, a, c, w)
        cu.seg(0, a, c, w, net)


def divider(b, cu, fps, netinfo, P, ant, stage, idx, j, up, head_net):
    """one Wilkinson: junction j, arm TL net ties, two lambda/4 arms, the 100 ohm resistor, two output escapes.
    Returns (out_a, out_b) points and their nets."""
    xj, yj = j
    sg = 1 if up else -1
    arms = [f"WK_{ant}_{stage}{idx}a", f"WK_{ant}_{stage}{idx}b"]
    for side, arm in zip((-1, 1), arms):
        tl = [r for r in P.on(arm, "TL") if head_net in P.pins[r].values()][0]
        fp = fps[tl]
        fp.SetPosition(V(xj + side * TIE_OFF, yj))
        orient_pins(fp, {"1": (xj + side * (TIE_OFF - 0.4), yj), "2": (xj + side * (TIE_OFF + 0.4), yj)})
        rf_track(b, cu, netinfo, head_net, [(xj, yj), (xj + side * (TIE_OFF - 0.4), yj)], W70)
        pts = [(xj + side * (TIE_OFF + 0.4), yj), (xj + side * DIV_A, yj), (xj + side * DIV_A, yj + sg * DIV_H),
               (xj + side * R_HALF, yj + sg * DIV_H)]
        rf_track(b, cu, netinfo, arm, pts, W70)
    r = [x for x in P.on(arms[0], "R") if arms[1] in P.pins[x].values()][0]
    orient_pins(fps[r], {P.pad_on(r, arms[0])[0]: (xj - R_HALF, yj + sg * DIV_H),
                         P.pad_on(r, arms[1])[0]: (xj + R_HALF, yj + sg * DIV_H)})
    outs = []
    for side, arm in zip((-1, 1), arms):
        p0 = (xj + side * R_HALF, yj + sg * DIV_H)
        p1 = (p0[0], p0[1] + sg * 0.6)
        p2 = (xj + side * (R_HALF + 0.7), yj + sg * (DIV_H + OUT_RISE))
        outs.append((arm, [p0, p1, p2]))
    return outs


def tree(b, cu, fps, netinfo, P, ant, feed_end):
    """draw the 1:8 tree; feed_end = where the SPL_x_IN line arrives (already drawn up to the root junction)"""
    T = TREE[ant]
    heads = {0: [(f"SPL_{ant}_IN", T["s1"][0])]}
    st = {1: T["s1"], 2: T["s2"], 3: T["s3"]}
    level_outs = []
    pending = [(f"SPL_{ant}_IN", T["s1"][0], None)]
    for stage in (1, 2, 3):
        up = T["up"][stage - 1]
        nxt = []
        for i, (head, j, path_in) in enumerate(pending):
            outs = divider(b, cu, fps, netinfo, P, ant, stage, i, j, up, head)
            for (arm, pts), tgt in zip(outs, ([st[stage + 1][2 * i], st[stage + 1][2 * i + 1]] if stage < 3 else
                                              [None, None])):
                nxt.append((arm, tgt, pts))
        if stage < 3:
            new = []
            for arm, tgt, pts in nxt:
                p2 = pts[-1]
                route = pts + [(tgt[0], p2[1]), tgt]
                rf_track(b, cu, netinfo, arm, route, W50)
                new.append((arm, tgt, None))
            pending = new
        else:
            level_outs = nxt
    # leaves: stage-3 arm k (slot order) -> port feed net tie -> u.FL
    for k, (arm, _, pts) in enumerate(level_outs):
        px = PITCH * k + PORT[ant][0]
        py, side = PORT[ant][1], PORT[ant][2]
        u = {"A": 30, "B": 40}[ant] + k
        uf = fps[f"J{u}"]
        uf.SetPosition(V(px, py))
        face(uf, ("2",), ("1",), (0, side))
        rfpad = pad_xy(uf, "1")[0]
        tl = [r for r in P.on(f"RF_{ant}{k}", "TL")][0]
        tie_c = (rfpad[0], rfpad[1] + side * 1.15)
        fp = fps[tl]
        fp.SetPosition(V(*tie_c))
        orient_pins(fp, {"1": (tie_c[0], tie_c[1] + side * 0.4), "2": (tie_c[0], tie_c[1] - side * 0.4)})
        start = (tie_c[0], tie_c[1] + side * 0.4)
        p2 = pts[-1]
        rf_track(b, cu, netinfo, arm, pts + [(start[0], p2[1]), start], W50)
        rf_track(b, cu, netinfo, f"RF_{ant}{k}", [(tie_c[0], tie_c[1] - side * 0.4), rfpad], W50)


def rf_copper(b, cu, fps, netinfo, P):
    out = {ant: rf_frontend(b, cu, fps, netinfo, P, ant) for ant in "AB"}
    jb = TREE["B"]["s1"][0]
    # B: BAW out -> up to y 31 -> across to the root -> up into the junction
    rf_track(b, cu, netinfo, "SPL_B_IN", [out["B"], (out["B"][0], 31.0), (jb[0], 31.0), jb], W50)
    # A: BAW out -> via -> B.Cu under tree B's root -> via at (220, 43) -> up the clear corridor to its root
    ja = TREE["A"]["s1"][0]
    h0, h1 = A_HOP
    rf_track(b, cu, netinfo, "SPL_A_IN", [out["A"], h0], W50)
    rf_via(b, cu, netinfo, "SPL_A_IN", h0)
    rf_track(b, cu, netinfo, "SPL_A_IN", [h0, (h0[0], h0[1] + 3.0), (h1[0], h1[1] - 6.0), h1], W50, layer=2)
    rf_via(b, cu, netinfo, "SPL_A_IN", h1)
    rf_track(b, cu, netinfo, "SPL_A_IN", [h1, ja], W50)
    for ant in "AB":
        tree(b, cu, fps, netinfo, P, ant, None)
    for it in cu.items:
        if it.kind != "pad" and is_rf(it.net):
            it.conn = True


def rf_fence(b, cu, gnd_vias):
    """GND via fence both sides of every RF segment, then the usual spacing check against all copper"""
    pts = []
    for it in cu.items:
        if it.kind != "seg" or not is_rf(it.net) or it.layers[0] != 0:
            continue
        (a, c), w = it.geom, it.w
        L = math.dist(a, c)
        if L < 0.3:
            continue
        ux, uy = (c[0] - a[0]) / L, (c[1] - a[1]) / L
        n = max(1, int(L / FENCE_PITCH))
        for s in range(n + 1):
            t = s / n
            px, py = a[0] + (c[0] - a[0]) * t, a[1] + (c[1] - a[1]) * t
            for sd in (1, -1):
                pts.append((px - sd * uy * FENCE_OFF, py + sd * ux * FENCE_OFF))
    return place_gnd_vias(b, cu, pts, gnd_vias, spacing=0.95, tol=0.3)


def place_gnd_vias(b, cu, pts, placed, spacing=0.9, tol=0.4, win=1.2):
    """drop GND vias at (or within tol of) the given points where the windowed grid says a GND via fits"""
    n = 0
    pts = sorted(pts, key=lambda p: (round(p[1] / 20), p[0]))
    cache = None
    for c in pts:
        if any(abs(c[0] - p[0]) < spacing and abs(c[1] - p[1]) < spacing and math.dist(c, p) < spacing for p in placed[-400:]):
            continue
        if cache is None or not (cache[1][0] + 2 < c[0] < cache[1][2] - 2 and cache[1][1] + 2 < c[1] < cache[1][3] - 2):
            w = (c[0] - 12, c[1] - 12, c[0] + 12, c[1] + 12)
            g, _ = cu.grid(w, "GND")
            cache = (g, w)
        g = cache[0]
        best = None
        for dx, dy in ((0, 0), (0.1, 0), (-0.1, 0), (0, 0.1), (0, -0.1), (0.2, 0), (-0.2, 0), (0, 0.2), (0, -0.2),
                       (0.3, 0), (-0.3, 0), (0, 0.3), (0, -0.3)):
            if abs(dx) > tol or abs(dy) > tol:
                continue
            i = g.cell(c[0] + dx, c[1] + dy)
            if i is None or not g.via_ok(i, 1, {}):
                continue
            v = g.xy(i)
            if any(math.dist(v, p) < spacing for p in placed[-400:]):
                continue
            best = v
            break
        if best:
            import pcbnew as P_
            pk.add_via(b, NETS["GND"], best)
            cu.via_at(best, "GND")
            g.commit([], [best], VIA_D, 1)
            g.mark_circle(range(3), best, VIA_D / 2, 2)
            placed.append(best)
            n += 1
    return n


NETS = {}


def gnd_hand(b, cu, fps, gnd_vias):
    """GND pins that the generic fan-out would wall in or cannot reach, wired by hand (#34):
    - TPS2595 pin 8 -> its exposed pad (a fan-out via to the right blocked the ILM pin 7 beside it);
    - QPL9057 GND pins 3/4/6/8 -> its exposed pad (the 0.5 mm RF pour gap keeps the L1 pour off them);
    - QPQ1907 pads 2+3 -> one via outboard, pad 5 -> one via on the other side;
    - TPS62933 pin 4 -> a via just below it."""
    import pcbnew as P_

    def stub(a, c, w=0.2):
        pk.add_track(b, NETS["GND"], P_.F_Cu, a, c, w)
        cu.seg(0, a, c, w, "GND")

    def via(c):
        pk.add_via(b, NETS["GND"], c)
        cu.via_at(c, "GND")
        gnd_vias.append(c)

    def to_ep(ref, nums, ep="9"):
        e = [q for p_ in fps[ref].Pads() if p_.GetNumber() == ep for q in [pk.pad_poly(p_, P_.F_Cu)]][0]
        xs = [q[0] for q in e]; ys = [q[1] for q in e]
        for n in nums:
            a = pc(fps, ref, n)
            t = (min(max(a[0], min(xs) + 0.15), max(xs) - 0.15), min(max(a[1], min(ys) + 0.15), max(ys) - 0.15))
            stub(a, t)
            HAND.add((ref, n))
    for ref, fp in fps.items():
        if str(fp.GetFPID().GetLibItemName()).startswith("Texas_DSG0008A"):
            to_ep(ref, ["8"])
    for ref in ("U6", "U7"):
        to_ep(ref, ["3", "4", "6", "8"])
    for ref in ("U8", "U9"):
        p2, p3, p5 = pc(fps, ref, "2"), pc(fps, ref, "3"), pc(fps, ref, "5")
        side = 1 if p2[0] > p5[0] else -1
        v = (p2[0] + side * 0.76, (p2[1] + p3[1]) / 2)
        stub(p2, p3); stub(p2, (v[0], p2[1])); stub((v[0], p2[1]), v); via(v)
        v5 = (p5[0] - side * 0.76, p5[1])
        stub(p5, v5); via(v5)
        HAND.update({(ref, "2"), (ref, "3"), (ref, "5")})
    a = pc(fps, "U2", "4")
    v = (a[0], a[1] - 0.95)
    stub(a, v, 0.3); via(v)
    HAND.add(("U2", "4"))


def gnd_fanout(b, cu, pads, gnd_vias, log):
    """one via per SMD GND pad, as close as clearance allows (big pads: via in pad); the L1 pour joins them too"""
    import pcbnew as P_
    n = 0
    for (ref, num), lst in sorted(pads.items()):
        for it in lst:
            if it.net != "GND" or it.layers != (0,) or (ref, num) in HAND:
                continue
            poly = it.geom[0]
            xs = [q[0] for q in poly]; ys = [q[1] for q in poly]
            cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
            hx, hy = (max(xs) - min(xs)) / 2, (max(ys) - min(ys)) / 2
            if any(abs(v[0] - cx) <= hx + 0.2 and abs(v[1] - cy) <= hy + 0.2 for v in gnd_vias[-600:]):
                continue
            g, _ = cu.grid((cx - 4, cy - 4, cx + 4, cy + 4), "GND")
            best = None
            for r in (0.0, 0.55, 0.75, 0.95, 1.2, 1.5, 1.9, 2.4):
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
                    if r and not g.via_ok(i, 1, {}):
                        continue
                    if r == 0.0 and not all(g.own["via"][l][i] in (0, 1) for l in range(3)):
                        continue
                    if not g.seg_free(0, (cx, cy), (vx, vy), "pwr", 1, ()):
                        continue
                    if any(math.dist((vx, vy), p) < 0.9 for p in gnd_vias[-600:]):
                        continue
                    best = (vx, vy)
                    break
                if best:
                    break
            if not best:
                log.append(f"GND fanout failed {ref}.{num}")
                continue
            if math.dist(best, (cx, cy)) > 1e-6:
                pk.add_track(b, NETS["GND"], P_.F_Cu, (cx, cy), best, 0.3)
                cu.seg(0, (cx, cy), best, 0.3, "GND")
            pk.add_via(b, NETS["GND"], best)
            cu.via_at(best, "GND")
            gnd_vias.append(best)
            n += 1
    return n


def zone_fanout(b, cu, pads, net, rect, log, placed):
    """SMD pads of a pour net (CHASSIS: TVS anodes, NT1) get a via into the B.Cu pour inside rect"""
    import pcbnew as P_
    n = 0
    for (ref, num), lst in sorted(pads.items()):
        for it in lst:
            if it.net != net or it.layers != (0,):
                continue
            poly = it.geom[0]
            xs = [q[0] for q in poly]; ys = [q[1] for q in poly]
            cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
            g, _ = cu.grid((cx - 6, cy - 6, cx + 6, cy + 6), net)
            best = None
            for r in (0.0, 0.6, 0.9, 1.2, 1.6, 2.0, 2.5, 3.0, 3.6):
                for ang in (270, 240, 300, 180, 0, 210, 330, 90, 120, 60, 150, 30):
                    a = math.radians(ang)
                    vx, vy = cx + r * math.cos(a), cy + r * math.sin(a)
                    if not (rect[0] + 0.8 < vx < rect[2] - 0.8 and rect[1] + 0.8 < vy < rect[3] - 0.8):
                        continue
                    i = g.cell(vx, vy)
                    if i is None or not g.via_ok(i, 1, {}):
                        continue
                    vx, vy = g.xy(i)
                    if not g.seg_free(0, (cx, cy), (vx, vy), "pwr", 1, ()):
                        continue
                    best = (vx, vy)
                    break
                if best:
                    break
            if not best:
                log.append(f"{net} fanout failed {ref}.{num}")
                continue
            if math.dist(best, (cx, cy)) > 1e-6:
                pk.add_track(b, NETS[net], P_.F_Cu, (cx, cy), best, 0.5)
                cu.seg(0, (cx, cy), best, 0.5, net)
            pk.add_via(b, NETS[net], best)
            cu.via_at(best, net)
            placed.append(best)
            n += 1
    return n


def route_all(b, cu, nets, log):
    """everything that is not RF, GND or a pour: audio legs first (B.Cu only), then power (outer copper, wide),
    then signals (any routing layer, inner preferred for long runs)"""
    import pcbnew as P_
    LAY = (P_.F_Cu, P_.In2_Cu, P_.B_Cu)

    def on_seg(net, l, a, c, w):
        pk.add_track(b, NETS[net], LAY[l], a, c, w)

    def on_via(net, v):
        pk.add_via(b, NETS[net], v)
    failed = {}
    skip = {"GND", "CHASSIS", "BUCK_SW"}      # BUCK_SW: the F.Cu pour BUCK_SW_ZONE
    rf_or_skip = lambda n: is_rf(n) or n in skip or n.startswith("__")
    order = [n for n in AUDIO_NETS] + [n for n in BIG_NETS] + \
        [n for n in POWER_NETS if n not in BIG_NETS] + \
        sorted((n for n in nets if n not in WIDE_NETS and not rf_or_skip(n)),
               key=lambda n: (n.startswith(("HOST_", "S")), n))
    forbid_rf = {0: (3,)}
    for net in order:
        if net not in nets or len(nets[net]) < 2 and net not in ZONES_B:
            continue
        if net in AUDIO_NETS:
            kw = dict(cls="wide", layers=[0, 2], layer_cost=(1.6, 9.0, 1.0), via_cost=8.0)
        elif net in BIG_NETS:
            kw = dict(cls="big", layers=[0, 2], layer_cost=(1.0, 9.0, 1.3), via_cost=6.0)
        elif net in POWER_NETS:
            kw = dict(cls="wide", layers=[0, 2], layer_cost=(1.0, 9.0, 1.2), via_cost=6.0)
        else:
            kw = dict(cls="sig", layers=[0, 1, 2], layer_cost=(1.5, 1.0, 1.3), via_cost=8.0)
        t0 = time.time()
        bad = cu.route_net(net, forbid=forbid_rf, on_seg=on_seg, on_via=on_via, **kw)
        print(f"  route {net}: {time.time() - t0:.1f} s{' FAILED ' + str(len(bad)) if bad else ''}", flush=True)
        if bad:
            failed[net] = [f"{(p.bbox[0] + p.bbox[2]) / 2:.1f},{(p.bbox[1] + p.bbox[3]) / 2:.1f}" for p in bad]
            log.append(f"FAILED {net}: {failed[net]}")
    return failed


def stitch_grid(b, cu, gnd_vias):
    """GND stitching: a 6 mm grid over the board plus a 3 mm row along every edge (L1/L2/L3/L4 pours tied)"""
    pts = []
    x = 1.5
    while x < BW - 1.0:
        pts += [(x, 1.2), (x, BD - 1.2)]
        x += 3.0
    y = 3.0
    while y < BD - 1.0:
        pts += [(1.2, y), (BW - 1.2, y)]
        y += 3.0
    for gx in range(6, int(BW) - 2, 6):
        for gy in range(6, int(BD) - 2, 6):
            pts.append((float(gx), float(gy)))
    return place_gnd_vias(b, cu, pts, gnd_vias, spacing=1.2, tol=0.6)


# ---------------------------------------------------------------------------------------------------------------
def zones(b):
    import pcbnew as P_
    def add(layer, net, poly, prio, solid=False):
        z = P_.ZONE(b)
        z.SetLayer(layer); z.SetNet(NETS[net])
        z.SetLocalClearance(mm(0.2))
        z.SetMinThickness(mm(0.25))
        z.SetThermalReliefGap(mm(0.25)); z.SetThermalReliefSpokeWidth(mm(0.4 if net != "GND" else 0.3))
        z.SetPadConnection(P_.ZONE_CONNECTION_FULL if solid else P_.ZONE_CONNECTION_THERMAL)
        z.SetIslandRemovalMode(P_.ISLAND_REMOVAL_MODE_ALWAYS)
        z.SetAssignedPriority(prio)
        ol = z.Outline(); ol.NewOutline()
        for x, y in poly:
            ol.Append(mm(OX + x), mm(OY - y))
        b.Add(z)
    for layer in (P_.F_Cu, P_.In1_Cu, P_.In2_Cu, P_.B_Cu):
        add(layer, "GND", OUTLINE, 0)
    add(P_.F_Cu, "BUCK_SW", BUCK_SW_ZONE, 3, solid=True)
    for net, poly in ZONES_B.items():
        # the bus pours join their pads solidly: 0.4 mm spokes would neck a 0.5 A slot feed for nothing
        add(P_.B_Cu, net, poly, 2 if net != "CHASSIS" else 1, solid=net != "CHASSIS")
    P_.ZONE_FILLER(b).Fill(b.Zones())


def netclass_of(net):
    if is_rf(net):
        return "RF"
    if net in BIG_NETS:
        return "Big"
    if net in AUDIO_NETS:
        return "Audio_I"
    if net in POWER_NETS:
        return "Power"
    return None


def write_project(nets):
    def cls(name, clearance, width, prio):
        return {"name": name, "clearance": clearance, "track_width": width, "via_diameter": VIA_D, "via_drill": VIA_DRILL,
                "microvia_diameter": 0.3, "microvia_drill": 0.1, "diff_pair_width": 0.2, "diff_pair_gap": 0.2,
                "diff_pair_via_gap": 0.25, "wire_width": 6, "bus_width": 12, "line_style": 0,
                "schematic_color": "rgba(0, 0, 0, 0.000)", "pcb_color": "rgba(0, 0, 0, 0.000)", "priority": prio}
    pats = []
    for n in sorted(nets):
        c = netclass_of(n)
        if c:
            pats.append({"netclass": c, "pattern": n})
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
                                "track_dangling": "warning", "starved_thermal": "warning", "courtyards_overlap": "error"},
            "track_widths": [0.0, 0.2, 0.3, W70, W50, 0.5, BIG_W],
            "via_dimensions": [{"diameter": 0.0, "drill": 0.0}, {"diameter": VIA_D, "drill": VIA_DRILL}],
        }},
        "net_settings": {
            "classes": [cls("Default", 0.127, 0.2, 2147483647), cls("Power", 0.15, WIDE_W, 1), cls("Big", 0.2, BIG_W, 0),
                        cls("Audio_I", 0.15, WIDE_W, 2), cls("RF", 0.15, W50, 3)],
            "meta": {"version": 4},
            "netclass_patterns": pats,
        },
        "meta": {"filename": "rack.kicad_pro", "version": 3},
    }
    PRO.write_text(json.dumps(pro, indent=2) + "\n")


def save(b):
    import pcbnew as P_
    P_.SaveBoard(str(BOARD), b)
    txt = BOARD.read_text()
    txt = re.sub(r"(\t\(setup\n)", lambda m: m.group(1) + pk.stackup_sexp() + "\n", txt, count=1)
    BOARD.write_text(txt)


def segments(path=BOARD):
    return pk.segments(path)


def drc(out=None):
    out = out or (OUT / "drc.json")
    out.parent.mkdir(exist_ok=True)
    # --save-board keeps kicad-cli's refill (the one that applies the .kicad_dru RF pour gap); the gerbers export it
    subprocess.run(["kicad-cli", "pcb", "drc", "--format", "json", "--severity-all", "--refill-zones", "--save-board",
                    "-o", str(out), str(BOARD)], capture_output=True, text=True)
    rep = json.loads(out.read_text())
    errs = [v for v in rep.get("violations", []) if v.get("severity") == "error"]
    warns = [v for v in rep.get("violations", []) if v.get("severity") == "warning"]
    return rep, errs, warns, rep.get("unconnected_items", [])


# ---------------------------------------------------------------------------------------------------------------
# mechanical record for mech/rack.py (and the tests): outline, holes, panel connectors with their axis heights
# ---------------------------------------------------------------------------------------------------------------
def mech_record(fps):
    panel = []
    for k in range(N_SLOTS):
        panel.append({"name": f"xlr{k}", "kind": "NC3MAH", "x": XLR_X[k], "z": STANDOFF + BOARD_T + fpr.NC3MAH["axis_h"],
                      "cut_d": fpr.NC3MAH["cutout_d"], "screws": fpr.NC3MAH["screw"], "depth": fpr.NC3MAH["body_depth"],
                      "body": [fpr.NC3MAH["flange"], fpr.NC3MAH["body_d"]]})
    for ant in "AB":
        panel.append({"name": f"bnc_{ant.lower()}", "kind": "5415025-1", "x": BNC_X[ant],
                      "z": STANDOFF + BOARD_T + fpr.BNC_TE["axis_h"], "cut_d": fpr.BNC_TE["cutout_d"],
                      "flat": fpr.BNC_TE["cutout_flat"], "depth": fpr.BNC_TE["body_depth"], "body": [fpr.BNC_TE["body_w"], 11.66]})
    panel.append({"name": "dc", "kind": "PJ-063AH", "x": DCJ_X, "z": STANDOFF + BOARD_T + DCJ_AXIS, "cut_d": 9.5,
                  "depth": 13.0, "body": [10.0, 11.0]})
    return {
        "board": [BW, BD], "thickness": BOARD_T, "standoff": STANDOFF, "case_inside": list(CASE_IN), "board_x0": BOARD_X0,
        "slot_pitch": PITCH, "sub_board": [SUB_W, SUB_L], "sub_y0": Y0, "sub_above_main": RX_MECH["above_main_board"],
        "sub_header_stack": RX_MECH["header_stack"],
        "sub_holes": {str(k): SUB_HOLES[k] for k in range(N_SLOTS)},
        "cm4io": {"rect": list(CM4IO_RECT), "holes": CM4IO_HOLES, "spacer": CM4IO_SPACER, "height_above": 16.0},
        "case_holes": CASE_HOLES, "panel": panel,
        "ports": {ant: [[PITCH * k + PORT[ant][0], PORT[ant][1]] for k in range(N_SLOTS)] for ant in "AB"},
        "receiver_ufl": {ant: [list(SUB_UFL[k][ant]) for k in range(N_SLOTS)] for ant in "AB"},
        "leds": [[to_xy(fps[r].GetPosition())[0], BD] for r in sorted(fps) if fps[r].GetFPID().GetLibItemName() == "LED_LiteOn_LTST-S270"],
        "led_axis_z": STANDOFF + BOARD_T + 0.3,
    }


def main(argv):
    import pcbnew as P_
    RF_LOG.clear()
    HAND.clear()
    b, fps, netinfo, nets, P, pl = build()
    NETS.clear(); NETS.update(netinfo)
    bad = legalize(fps, pl)
    if bad:
        print("courtyard overlaps:", bad)
    cu, pads = fill_copper(fps)
    rf_copper(b, cu, fps, netinfo, P)
    # refresh the pad copper of the parts rf_copper re-oriented (TL net ties, u.FL ports, resistors)
    cu, pads = refill_pads(cu, fps)
    log = []
    gnd_vias = []
    cu.zone(0, BUCK_SW_ZONE, "BUCK_SW")
    gnd_hand(b, cu, fps, gnd_vias)
    print("placed, RF drawn", flush=True)
    nf = gnd_fanout(b, cu, pads, gnd_vias, log)
    print(f"GND fan-out {nf}", flush=True)
    for net, poly in ZONES_B.items():
        if net != "CHASSIS":
            cu.zone(2, poly, net)
    for r in RF_ZONE:
        cu.tag((0,), r, 3)
    nc = zone_fanout(b, cu, pads, "CHASSIS", (ZONES_B["CHASSIS"][0][0], ZONES_B["CHASSIS"][0][1],
                                                ZONES_B["CHASSIS"][2][0], ZONES_B["CHASSIS"][2][1]), log, [])
    failed = route_all(b, cu, nets, log)
    nfence = rf_fence(b, cu, gnd_vias)
    nst = stitch_grid(b, cu, gnd_vias)
    for line in log:
        print(line)
    print(f"GND fanout {nf}, chassis vias {nc}, RF fence vias {nfence}, stitching {nst}; failed nets: {sorted(failed)}")
    zones(b)
    write_project(nets)
    save(b)
    (OUT / "rf_geometry.json").write_text(json.dumps({"w50": W50, "w70": W70, "gap": RF_GAP, "lq_mm": LQ, "div_a": DIV_A,
                                                       "div_h": DIV_H, "solve": {f"{k[0]}/{k[1]}": v for k, v in RF_SOLVE.items()},
                                                       "tracks": RF_LOG}, indent=0) + "\n")
    (OUT / "mech.json").write_text(json.dumps(mech_record(fps), indent=1) + "\n")
    rep, errs, warns, unconn = drc()
    print(pk.summarize(errs, warns, unconn))
    if "--no-out" not in argv:
        outputs = _load("hw_rack_outputs", HERE / "outputs_rack.py")
        outputs.run_all()
    return 1 if (errs or unconn or failed) else 0


def refill_pads(cu, fps):
    """rebuild the pad items (positions changed for parts rf_copper oriented) and keep every other item"""
    keep = [it for it in cu.items if it.kind != "pad" and it.kind != "hole"]
    cu2, pads = fill_copper(fps)
    cu2.items.extend(keep)
    for it in cu2.items:
        if it.kind == "pad" and is_rf(it.net):
            it.conn = True
    for key in HAND:
        for it in pads.get(key, []):
            it.conn = True
    return cu2, pads


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
