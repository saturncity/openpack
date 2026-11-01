#!/usr/bin/env python3
"""R1 with the two rack antennas in the wings (#101, docs/analysis/r1-wing-antennas.md, ADR-0021).

A 3-D free-space model of UK theatres: two receive antennas, one per wing, aimed across the stage. Packs on
the stage, actors in the wings, audience phones in the house and crew Wi-Fi in the wings. For every pack
position it gives the wanted level at each antenna, the worst Wi-Fi at each antenna, and the margin of the
gap carrier on the antenna RX-5 picks. It also writes per-device attenuations for
tests/bsim/scenarios/run.py --geometry.

Frame: x across the stage (antenna L at -x, antenna R at +x), y upstage from the stage front edge (the setting
line, y = 0), z up from the stage floor. Units m, dB, dBm. Free space at 2442 MHz, no body loss, no fading, no
wall credit unless a venue sets one (as ADR-0016's Q3 C/I).

Antenna patterns are rotationally symmetric about boresight, from the H (azimuth) and V (elevation) cuts.
The wanted pack uses the *lower* of the two cuts at that off-axis angle (pessimistic). Every interferer
(Wi-Fi, a hot neighbouring pack) uses the *higher* (envelope, pessimistic). The 3-D pattern is not published,
so both choices are on the safe side.

usage: wing_geometry.py [--write DIR]   prints the options table; --write emits the run.py geometry files
"""
import argparse
import json
import math
import sys
from dataclasses import dataclass, field, replace
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import bsim_modem as bm  # noqa: E402

F_MHZ = 2442.0
WIFI = (2412, 2437, 2462)
EIRP_UK, EIRP_US, WIFI_DBM = 9.0, 20.0, 20.0   # ADR-0015 pack; Q3 Wi-Fi 20 dBm per channel (ADR-0003)
TD_BITS = (81 + 11) * 8                        # TD-length copy, as audit.py Audit 4
MARGIN_DB = 3.0                                # ADR-0016 design margin over the twin threshold
PACK_Z = 1.2                                   # pack on the belt or the small of the back
PLAN = {1: (2414, 2482), 2: (2423, 2463), 3: (2426, 2468), 4: (2403, 2448), 5: (2408, 2451), 6: (2429, 2473),
        7: (2434, 2476), 8: (2439, 2479)}     # host/channel_plan.yaml (UK, ADR-0016)


def fspl_db(d, f=F_MHZ):
    return 20 * math.log10(max(d, 0.05)) + 20 * math.log10(f) - 27.55


def _interp(tab, a):
    a = min(abs(a), 180.0)
    for (a0, g0), (a1, g1) in zip(tab, tab[1:]):
        if a0 <= a <= a1:
            return g0 + (g1 - g0) * (a - a0) / (a1 - a0)
    return tab[-1][1]


# L-com HG2409P-NF (ds_HG2409P-NF.pdf; ADR-0016 read-off): 8 dBi, HPBW 75 H / 65 V, 180 deg -30 H / -18 V,
# rear lobes -10 dB H (~135 deg) and -9 dB V (~120 deg). The 60/90 deg points are interpolations between the
# read-off points for a patch of that beamwidth (est.); Phase 5 measures the real pattern (#92).
PATCH_H = [(0, 0), (37.5, -3), (60, -7), (90, -12), (135, -10), (160, -20), (180, -30)]
PATCH_V = [(0, 0), (32.5, -3), (60, -8), (90, -13), (120, -9), (150, -15), (180, -18)]
# Generic 3 dBi vertical dipole omni (the "omni in the wings" lever): flat in azimuth, so the off-boresight angle
# for it is the elevation; 78 deg elevation HPBW. A vertical antenna "boresight" is horizontal.
OMNI_V = [(0, 0), (39, -3), (60, -8), (90, -30), (120, -8), (141, -3), (180, 0)]
# Generic 6 dBi wide patch (~100 deg H/V, the "wider beam" lever; catalogue class, est.), rear -12.
WIDE = [(0, 0), (50, -3), (90, -9), (135, -12), (180, -15)]


@dataclass(frozen=True)
class Ant:
    kind: str = "patch"     # patch | omni | wide
    gain: float = 8.0

    def rel(self, az, el, pess):
        """Gain vs boresight (dB), az/el off boresight in degrees; pess = wanted signal (lower cut)."""
        if self.kind == "omni":
            return _interp(OMNI_V, el)
        psi = math.degrees(math.acos(max(-1, min(1, math.cos(math.radians(az)) * math.cos(math.radians(el))))))
        if self.kind == "wide":
            return _interp(WIDE, psi)
        h, v = _interp(PATCH_H, psi), _interp(PATCH_V, psi)
        return min(h, v) if pess else max(h, v)


PATCH = Ant()
OMNI3 = Ant("omni", 3.0)
WIDE6 = Ant("wide", 6.0)


@dataclass(frozen=True)
class Venue:
    name: str
    width: float            # acting area / proscenium opening (m)
    depth: float            # acting area depth (m)
    wing: float             # wing width offstage of the acting area (m)
    front_row: float        # front row distance downstage of the setting line (m)
    rows: int
    pitch: float            # row pitch (m)
    rake: float             # rise per row (m)
    house_w: float          # seating width (m)
    floor_z: float          # stalls floor height vs the stage floor (m, negative = below)
    extra: tuple = ()       # other audience points (boxes, circle): (x, y, z)
    wall: bool = False      # proscenium wall at y = 0 outside |x| <= width/2
    wall_db: float = 0.0    # credit for that wall (default none: worst case)


STUDIO = Venue("studio 6 m", 6.0, 5.0, 1.5, 1.0, 8, 0.9, 0.4, 9.0, 0.0)
PROSC = Venue("proscenium 10 m", 10.0, 8.0, 3.0, 2.5, 18, 0.85, 0.12, 16.0, -1.0,
              extra=((-8.0, -1.5, 3.0), (8.0, -1.5, 3.0), (0.0, -14.0, 5.0)), wall=True)
LARGE = Venue("proscenium 12 m", 12.0, 10.0, 4.0, 3.0, 22, 0.85, 0.12, 20.0, -1.0,
              extra=((-9.5, -1.5, 3.0), (9.5, -1.5, 3.0), (0.0, -17.0, 5.0)), wall=True)
VENUES = (STUDIO, PROSC, LARGE)


@dataclass(frozen=True)
class Install:
    """Where the two antennas go. offstage: distance offstage of the acting-area edge; y_frac: position along the
    wing as a fraction of the depth; z: height; toe: yaw of boresight upstage (deg) from straight across."""
    ant: Ant = PATCH
    offstage: float = 1.0
    y_frac: float = 0.5
    z: float = 2.0
    toe: float = 0.0
    tilt: float = 0.0        # boresight down-tilt (deg)
    crew_ap_m: float = 3.0   # no crew Wi-Fi within this distance of either antenna (rule)

    def label(self):
        return (f"{self.ant.kind} {self.ant.gain:g} dBi, {self.offstage:g} m offstage, at {self.y_frac:.0%} of the depth,"
                f" {self.z:g} m up" + (f", toe {self.toe:g} deg" if self.toe else "") +
                (f", tilt {self.tilt:g} deg" if self.tilt else "") +
                (f", crew Wi-Fi allowed {self.crew_ap_m:g} m away" if self.crew_ap_m < 50 else ""))


def antennas(v: Venue, ins: Install):
    """[(name, position, boresight unit vector, Ant)] for the L and R wings."""
    out = []
    for name, s in (("L", -1), ("R", 1)):
        p = (s * (v.width / 2 + ins.offstage), ins.y_frac * v.depth, ins.z)
        yaw = math.radians(ins.toe)
        t = math.radians(ins.tilt)
        b = (-s * math.cos(yaw) * math.cos(t), math.sin(yaw) * math.cos(t), -math.sin(t))
        out.append((name, p, b, ins.ant))
    return out


def gain(a, q, pess):
    """Antenna gain (dBi) of antenna a toward point q."""
    _, p, b, ant = a
    d = [q[i] - p[i] for i in range(3)]
    r = math.sqrt(sum(x * x for x in d)) or 1e-9
    if ant.kind == "omni":
        el = math.degrees(math.asin(d[2] / r))   # vertical omni: elevation from the horizontal
        return ant.gain + ant.rel(0, el, pess)
    cosang = sum(d[i] * b[i] for i in range(3)) / r
    psi = math.degrees(math.acos(max(-1, min(1, cosang))))
    return ant.gain + ant.rel(psi, 0, pess)


def dist(p, q):
    return math.sqrt(sum((p[i] - q[i]) ** 2 for i in range(3)))


def wall_loss(v: Venue, p, q):
    """Proscenium wall credit if the ray p -> q crosses y = 0 outside the opening (or above 7 m)."""
    if not v.wall or (p[1] > 0) == (q[1] > 0):
        return 0.0
    t = p[1] / (p[1] - q[1])
    x, z = p[0] + t * (q[0] - p[0]), p[2] + t * (q[2] - p[2])
    return v.wall_db if abs(x) > v.width / 2 or z > 7.0 else 0.0


def audience(v: Venue):
    pts = []
    for k in range(v.rows):
        y = -(v.front_row + k * v.pitch)
        z = v.floor_z + 1.0 + k * v.rake          # phone in the hand, seated
        n = int(v.house_w / 1.0) + 1
        pts += [(-v.house_w / 2 + i * v.house_w / (n - 1), y, z) for i in range(n)]
    return pts + list(v.extra)


def crew_aps(v: Venue, ins: Install, ants):
    """Crew Wi-Fi anywhere in either wing, 1.2 m up, outside the rule radius around each antenna."""
    pts = []
    for s in (-1, 1):
        for i in range(9):
            x = s * (v.width / 2 + v.wing * i / 8)
            for j in range(11):
                q = (x, v.depth * j / 10, 1.2)
                if all(dist(q, a[1]) >= ins.crew_ap_m for a in ants):
                    pts.append(q)
    return pts


def stage(v: Venue, step=0.5):
    nx, ny = int(v.width / step) + 1, int(v.depth / step) + 1
    return [(-v.width / 2 + i * step, j * step, PACK_Z) for i in range(nx) for j in range(ny)]


def wanted_dbm(a, q, eirp=EIRP_UK):
    return eirp - fspl_db(dist(a[1], q)) + gain(a, q, True)


def wifi_dbm(v, a, q, dbm=WIFI_DBM):
    return dbm - fspl_db(dist(a[1], q)) + gain(a, q, False) - wall_loss(v, a[1], q)


def ci_threshold_db(f_mhz, wanted=-40.0):
    """Lowest wanted-minus-Wi-Fi (dB, per Wi-Fi channel, all three on air) for PER <= 0.1 % of a TD-length copy in
    the twin (BabbleSim BLE_simple, sim/loss/bsim_modem.py). 11 MHz carriers: -12.3 dB, as Audit 4."""
    for x in range(-600, 400):
        ci = x / 10
        if bm.per(bm.sinr_db(f_mhz, WIFI, wanted, wanted - ci), TD_BITS) <= 1e-3:
            return ci
    return 40.0


def neighbour_tolerance_db(off_mhz):
    """How much hotter (dB) a pack off_mhz away may be before a copy's PER exceeds 0.1 % (twin)."""
    sinr = next(x / 10 for x in range(400) if bm.per(x / 10, TD_BITS) <= 1e-3)
    return -bm.through_filter_db(off_mhz, "2M", bm.TX2M) - sinr


def gap_carrier(k):
    return next(f for f in PLAN[k] if min(abs(f - w) for w in WIFI) >= 11)


@dataclass
class Eval:
    venue: Venue
    ins: Install
    ants: list = field(default_factory=list)
    thr: float = 0.0
    iw: dict = field(default_factory=dict)       # worst Wi-Fi level per antenna (dBm) and where
    rows: list = field(default_factory=list)     # per stage point: (q, S_L, S_R, sel, margin_sel, margin_best)


def evaluate(v: Venue, ins: Install, thr=None):
    """Worst-case 11 MHz gap carrier (thr dB) at every stage point. margin = C/I - thr - MARGIN_DB on the antenna
    RX-5 picks (the stronger wanted RSSI) and on the better one. >= 0 means the gap copy holds with margin."""
    thr = ci_threshold_db(2423) if thr is None else thr
    e = Eval(v, ins, antennas(v, ins), thr)
    srcs = audience(v) + crew_aps(v, ins, e.ants)
    for a in e.ants:
        lv = [(wifi_dbm(v, a, q), q) for q in srcs]
        e.iw[a[0]] = max(lv)
    for q in stage(v):
        s = [wanted_dbm(a, q) for a in e.ants]
        m = [s[i] - e.iw[a[0]][0] - thr - MARGIN_DB for i, a in enumerate(e.ants)]
        sel = 0 if s[0] >= s[1] else 1
        e.rows.append((q, s[0], s[1], sel, m[sel], max(m)))
    return e


def summary(e: Eval):
    ms = [r[4] for r in e.rows]
    mb = [r[5] for r in e.rows]
    worst = min(e.rows, key=lambda r: r[4])
    return {"points": len(ms), "pass_sel": sum(x >= 0 for x in ms) / len(ms), "pass_best": sum(x >= 0 for x in mb) / len(mb),
            "worst_margin": worst[4], "worst_at": worst[0], "worst_best": min(mb),
            "wifi_L": e.iw["L"][0], "wifi_L_at": e.iw["L"][1], "s_min": min(max(r[1], r[2]) for r in e.rows)}


# ---------------------------------------------------------------- near-far and the rack chain

def near(v: Venue, ins: Install, approach=0.5, eirp=EIRP_UK, on_axis=False):
    """An actor walks past antenna L, `approach` m from its foot horizontally, in any direction (the worst one is
    kept), pack at PACK_Z. Envelope pattern. on_axis: instead, the pack 'approach' m straight in front of the face
    at its height (off-rule worst case, e.g. a low mount). Returns (position, level at L, level at R) in dBm."""
    L, R = antennas(v, ins)
    if on_axis:
        q = tuple(L[1][i] + approach * L[2][i] for i in range(3))
        return q, eirp - fspl_db(approach) + L[3].gain, eirp - fspl_db(dist(R[1], q)) + gain(R, q, False)
    best = None
    for k in range(0, 360, 5):
        t = math.radians(k)
        q = (L[1][0] + approach * math.cos(t), L[1][1] + approach * math.sin(t), PACK_Z)
        lv = eirp - fspl_db(dist(L[1], q)) + gain(L, q, False)
        if best is None or lv > best[1]:
            best = (q, lv)
    q = best[0]
    return q, best[1], eirp - fspl_db(dist(R[1], q)) + gain(R, q, False)


def victim_headroom(e: Eval, nx, plan_x, plan_y_gap):
    """For pack Y (gap carrier plan_y_gap) at every stage point, with near pack X (carriers plan_x, levels nx at
    L/R): headroom (dB, >= 0 holds with MARGIN_DB) of Y's gap copy on L, on R. The copy must beat the Wi-Fi there
    and X by the offset's tolerance."""
    offs = [abs(plan_y_gap - f) for f in plan_x]
    tol = min(neighbour_tolerance_db(o) if o < 10 else 99.0 for o in offs)
    out = []
    for q, sL, sR, sel, _, _ in e.rows:
        hL = min(sL - e.iw["L"][0] - e.thr - MARGIN_DB, sL - (nx[0] - tol))
        hR = min(sR - e.iw["R"][0] - e.thr - MARGIN_DB, sR - (nx[1] - tol))
        out.append((q, hL, hR, sel))
    return out


def near_far(v: Venue, ins: Install, approach=0.5, eirp=EIRP_UK, plan=PLAN, on_axis=False):
    """Near pack X at antenna L (near()); every other pack Y anywhere on the stage grid. Y keeps its frames if its gap
    copy holds on either antenna: RX-5 is per carrier and ages a blocked antenna out (ADR-0011). 'strict' counts
    only the antenna with the stronger RSSI. worst = lowest headroom over all (X, Y) pairs and stage points."""
    e = evaluate(v, ins)
    q, nL, nR = near(v, ins, approach, eirp, on_axis)
    worst, fails, strict = {}, {}, {}
    for x in plan:
        for y in plan:
            if x != y:
                h = victim_headroom(e, (nL, nR), plan[x], gap_carrier(y))
                worst[(x, y)] = min(max(a, b) for _, a, b, _ in h)
                fails[(x, y)] = sum(max(a, b) < 0 for _, a, b, _ in h) / len(h)
                strict[(x, y)] = sum((a if s == 0 else b) < 0 for _, a, b, s in h) / len(h)
    base = sum(r[5] < 0 for r in e.rows) / len(e.rows)    # stage points short of margin with no near pack at all
    k = min(worst, key=worst.get)
    return {"pos": q, "p_near": (nL, nR), "approach_m": dist(e.ants[0][1], q), "worst": worst[k], "worst_pair": k,
            "extra_fail": max(fails.values()) - base, "strict_extra_fail": max(strict.values()) - base}


def near_far_any(v: Venue, ins: Install, approach=0.5, eirp=EIRP_UK, plan=PLAN, both=False, k_hot=None):
    """General near-far: the hot pack X may stand anywhere, at the boom (near()) or on any stage point (envelope
    gain toward it), and the victim Z anywhere on stage. Z's gap copy must beat the Wi-Fi and X on the antenna it uses,
    on either antenna (RX-5). both: a second hot pack Y at the mirror-image position of X (both wings / both sides
    occupied). Returns the worst headroom over all pairs (triples) and positions."""
    e = evaluate(v, ins)
    L, R = e.ants
    bq, bl, br = near(v, ins, approach, eirp)
    hot = [(bq, bl, br)] + [(q, eirp - fspl_db(dist(L[1], q)) + gain(L, q, False),
                             eirp - fspl_db(dist(R[1], q)) + gain(R, q, False)) for q, *_ in e.rows]
    if k_hot:  # the k hottest aggressor positions (by their stronger antenna) plus the boom
        hot = hot[:1] + sorted(hot[1:], key=lambda h: -max(h[1], h[2]))[:k_hot]
    tol = lambda g, fs: min(neighbour_tolerance_db(abs(g - f)) if abs(g - f) < 10 else 99.0 for f in fs)
    rows = [(sL, sR, sL - e.iw["L"][0] - e.thr - MARGIN_DB, sR - e.iw["R"][0] - e.thr - MARGIN_DB, q)
            for q, sL, sR, _, _, _ in e.rows]
    worst, arg = 99.0, None
    for x in plan:
        for z in plan:
            if z == x:
                continue
            g = gap_carrier(z)
            tx = tol(g, plan[x])
            ys = [y for y in plan if y not in (x, z)] if both else [None]
            for y in ys:
                ty = tol(g, plan[y]) if y else 99.0
                if tx > 50 and ty > 50:
                    continue
                for hq, hl, hr in hot:
                    for sL, sR, mL, mR, q in rows:
                        if dist(q, hq) < 0.5:
                            continue
                        hL = min(mL, sL - (hl - tx), sL - (hr - ty))   # Y mirrored: its L level is X's R level
                        hR = min(mR, sR - (hr - tx), sR - (hl - ty))
                        h = max(hL, hR)
                        if h < worst:
                            worst, arg = h, (x, y, z, hq, q)
    return {"worst": worst, "at": arg}


def near_far_both(v: Venue, ins: Install, approach=0.5, eirp=EIRP_UK, plan=PLAN):
    """Actors waiting in BOTH wings: pack X at antenna L's boom and pack Y at R's (mirror image), every other pack Z
    anywhere on stage. Z's gap copy must beat the Wi-Fi and both hot packs on the antenna it uses; it keeps its frames
    if that holds on either antenna (RX-5). Returns the worst headroom over all (X, Y, Z) and stage points."""
    e = evaluate(v, ins)
    _, n_near, n_far = near(v, ins, approach, eirp)       # X: n_near at L, n_far at R; Y mirrored
    worst, arg = 99.0, None
    tol = lambda g, fs: min(neighbour_tolerance_db(abs(g - f)) if abs(g - f) < 10 else 99.0 for f in fs)
    for x in plan:
        for y in plan:
            if x == y:
                continue
            for z in plan:
                if z in (x, y):
                    continue
                g = gap_carrier(z)
                tx, ty = tol(g, plan[x]), tol(g, plan[y])
                if tx > 50 and ty > 50:
                    continue
                for q, sL, sR, _, _, _ in e.rows:
                    hL = min(sL - e.iw["L"][0] - e.thr - MARGIN_DB, sL - (n_near - tx), sL - (n_far - ty))
                    hR = min(sR - e.iw["R"][0] - e.thr - MARGIN_DB, sR - (n_far - tx), sR - (n_near - ty))
                    h = max(hL, hR)
                    if h < worst:
                        worst, arg = h, (x, y, z, q)
    return {"worst": worst, "at": arg}


# Rack chain from PR #95 (hw/rack, ADR-0018 draft at 01570d9/d7105bc; audit.py Audit 6 there). Worst-case values:
# QPL9057 |S21| 23.0 dB at 2442 (datasheet table), input P1dB >= -7.6 dBm; QPQ1907 2.2 dB max; Wilkinson 10.61 +
# 0.5 layout; u.FL 1.0; sub-board 0.9; module nRF21540 RX 13 dB, input P1dB -18.0 dBm min (OPS v0.5.2), NO bypass;
# nRF5340 PRX,MAX 0 dBm. "Does not compress" = total input >= 6 dB under each stage's worst P1dB (PR #95's rule).
CHAIN = {"conn_db": 0.5, "front_end_db": 0.4, "lna_gain": 23.0, "lna_ip1db_min": -7.6, "filter_db": 2.2,
         "splitter_db": 11.1, "ufl_db": 1.0, "subboard_db": 0.9, "mod_lna_gain": 13.0, "mod_ip1db_min": -18.0,
         "nrf5340_pmax": 0.0, "backoff": 6.0}
PAD_DB = 10.0   # the fixed-pad alternative to the BT40E (PR #95's 10 dB row: NF 15.9 dB at 6 dB coax)
RX_MODULE = "BT40E"   # ADR-0021 recommendation for the receiver sub-board (no FEM; PR #95 option b)


MODULES = {  # receiver module on the sub-board: RX gain ahead of the nRF5340, its input P1dB, NF; USD qty 100
    "BT40NE": {"g": 13.0, "ip1db": -18.0, "nf": 2.7, "usd": 16.76},   # nRF21540 always on (no bypass)
    "BT40E": {"g": -0.3, "ip1db": None, "nf": 0.3, "usd": 9.55},       # no FEM: u.FL straight to the nRF5340 (est. 0.3 dB)
}
NRF5340_NF = 7.0          # est., as Audit 3/6
LNA_G_NF_PROXY = 21.5     # PR #95: minimum-gain proxy for the NF cascade (the levels use 23.0)
BAW_EDGE_DB = 2.0         # PR #95 BAW_SKIRT_EST_DB: band-edge carriers (2403, 2482) see 2 dB more


def chain_levels(p_ant, coax_db=0.0, pad_db=0.0, c=CHAIN, module="BT40NE"):
    """(rack LNA input, module input, nRF5340 input) dBm for p_ant dBm (total) at the antenna connector."""
    lna_in = p_ant - c["conn_db"] - coax_db - c["front_end_db"]
    fem_in = lna_in + c["lna_gain"] - c["filter_db"] - pad_db - c["splitter_db"] - c["ufl_db"] - c["subboard_db"]
    return lna_in, fem_in, fem_in + MODULES[module]["g"]


def chain_margins(p_ant, coax_db=0.0, pad_db=0.0, c=CHAIN, module="BT40NE"):
    """Headroom (dB, >= 0 passes) of the rack LNA, the module LNA (none on a BT40E: +inf) and the nRF5340 against
    P1dB / PRX,MAX - 6 dB (PR #95's back-off rule)."""
    lna_in, fem_in, radio = chain_levels(p_ant, coax_db, pad_db, c, module)
    ip = MODULES[module]["ip1db"]
    return (c["lna_ip1db_min"] - c["backoff"] - lna_in, (ip - c["backoff"] - fem_in) if ip is not None else math.inf,
            c["nrf5340_pmax"] - c["backoff"] - radio)


def imd_margin_db(strong_dbm, wanted_dbm, coax_db=0.0, pad_db=0.0, module="BT40NE", c=CHAIN, pimd=-22.0,
                  pimd_wanted=-64.0):
    """nRF5340 PIMD (PS v1.1: -22 dBm interferers at a -64 dBm wanted), scaled 3rd-order as PR #95 does: headroom
    (dB, >= 0 passes) for the two strongest signals strong_dbm (antenna-connector dBm) and a wanted_dbm pack."""
    post = lambda p: chain_levels(p, coax_db, pad_db, c, module)[2]
    a, b = sorted((post(x) for x in strong_dbm), reverse=True)[:2]
    allowed = pimd + (post(wanted_dbm) - pimd_wanted) / 3
    return 3 * allowed - (2 * a + b)


def system_nf_db(coax_db=6.0, pad_db=0.0, module="BT40NE", edge=True, c=CHAIN):
    """Friis NF at the antenna connector, worst case (PR #95's chain, band-edge carrier if edge)."""
    lossy = lambda d: (-d, d)
    m = MODULES[module]
    st = [lossy(coax_db), lossy(c["front_end_db"]), (LNA_G_NF_PROXY, 0.9),
          lossy(c["filter_db"] + (BAW_EDGE_DB if edge else 0)), lossy(pad_db), lossy(c["splitter_db"]),
          lossy(c["ufl_db"]), lossy(c["subboard_db"]), (m["g"], m["nf"]), (0.0, NRF5340_NF)]
    f, g = 0.0, 0.0
    for gain_db, nf_db in st:
        fl = 10 ** (nf_db / 10)
        f += fl if f == 0.0 else (fl - 1) / (10 ** (g / 10))
        g += gain_db
    return 10 * math.log10(f)


def noise_cost_db(nf_db, wanted_dbm, ci_req_db=10.0, margin_db=MARGIN_DB):
    """dB of the R1 margin that receiver noise uses (Audit 6's r1_noise_cost_db form) for a pack at wanted_dbm."""
    n = -174 + 10 * math.log10(2e6) + nf_db
    return 10 * math.log10(1 + 10 ** ((n - (wanted_dbm - ci_req_db - margin_db)) / 10))


def nf_needed_db(wanted_dbm, cost_db=0.5):
    """Largest system NF whose noise costs <= cost_db of the R1 margin for a pack at wanted_dbm."""
    return next(x / 10 for x in range(400, 0, -1) if noise_cost_db(x / 10, wanted_dbm) <= cost_db)


def on_axis_equiv_m(level_dbm, eirp_dbm, gain_dbi=8.0, f=F_MHZ):
    """Distance at which a source of eirp_dbm straight in front of an 8 dBi panel gives level_dbm (PR #95's tables
    are on-axis free-space distances)."""
    return 10 ** ((eirp_dbm + gain_dbi - level_dbm - (20 * math.log10(f) - 27.55)) / 20)


def phone_dbm(v, ins, ue_dbm=23.0, f=2390.0):
    """Worst class-3 phone (LTE B40, unfiltered ahead of the LNA) in the audience at antenna L (envelope gain)."""
    L = antennas(v, ins)[0]
    return max(ue_dbm - fspl_db(dist(L[1], q), f) + gain(L, q, False) - wall_loss(v, L[1], q) for q in audience(v))


def dbm_sum(*p):
    return 10 * math.log10(sum(10 ** (x / 10) for x in p))


# ---------------------------------------------------------------- the recommended rule and the bsim files

RULE = Install(offstage=1.0, y_frac=0.25, z=4.0, toe=30.0, tilt=10.0, crew_ap_m=99.0)   # ADR-0021
RULE_LO = replace(RULE, z=2.0, tilt=10.0)   # the same, on a 2 m stand (no boom): near-far sensitivity


def att(a, q, eirp, pess):
    """multiatt attenuation radio -> receiver: the bsim pack radio is 0 dBm, so att = -(EIRP - FSPL + G) = -level."""
    return round(-(eirp - fspl_db(dist(a[1], q)) + gain(a, q, pess)), 1)


def distinct(cands, taken, n, gap=1.5):
    out = []
    for q in cands:
        if all(dist(q, p) >= gap for p in taken + out):
            out.append(q)
        if len(out) == n:
            break
    return out


def bsim_case(v: Venue, ins: Install, near_id=7, approach=0.5, on_axis=False, eirp=EIRP_UK, plan=PLAN, near_r=None):
    """run.py --geometry JSON. Pack near_id walks past antenna L (near()). Its 3 MHz neighbours stand where their gap
    copy is weakest with it there; the rest at the stage points with the lowest RX-5 margin; pack 1 (no gap carrier
    in bsim, which stops at 2480: ADR-0016) at centre stage. Attenuations radio -> antenna L/R. Wi-Fi: the worst
    audience source per antenna, all three channels there (crew Wi-Fi excluded by the rule). near_r: a second
    actor waiting at antenna R's boom (mirror image), so both wings are occupied; victims then face both."""
    e = evaluate(v, ins)
    nq, nL, nR = near(v, ins, approach, eirp, on_axis)
    pos = {near_id: ("near", nq, [round(-nL, 1), round(-nR, 1)])}
    taken = [nq]
    hot = [(plan[near_id], (nL, nR))]
    if near_r:
        mq = (-nq[0], nq[1], nq[2])
        pos[near_r] = ("near R", mq, [round(-nR, 1), round(-nL, 1)])
        taken.append(mq)
        hot.append((plan[near_r], (nR, nL)))
    for y in plan:
        g = gap_carrier(y)
        if y not in pos and y != 1 and any(min(abs(g - f) for f in fs) <= 4 for fs, _ in hot):
            hs = [victim_headroom(e, lv, fs, g) for fs, lv in hot]
            h = sorted(((r[0], min(x[i][1] for x in hs), min(x[i][2] for x in hs)) for i, r in enumerate(hs[0])),
                       key=lambda r: max(r[1], r[2]))
            q = distinct([r[0] for r in h], taken, 1)[0]
            pos[y] = ("victim", q, None)
            taken.append(q)
    centre = (0.0, v.depth / 2, PACK_Z)
    pos[1] = ("centre", centre, None)
    taken.append(centre)
    rest = [y for y in plan if y not in pos]
    for y, q in zip(rest, distinct([r[0] for r in sorted(e.rows, key=lambda r: r[4])], taken, len(rest))):
        pos[y] = ("worst", q, None)
        taken.append(q)
    single = min(e.rows, key=lambda r: r[4])[0]
    packs = {}
    for y, (kind, q, a) in sorted(pos.items()):
        packs[str(y)] = {"kind": kind, "pos": [round(c, 2) for c in q],
                         "att": a or [att(ant, q, eirp, True) for ant in e.ants]}
    return {"venue": v.name, "install": ins.label(), "eirp": eirp, "near": near_id, "near_r": near_r,
            "near_case": f"{'on axis' if on_axis else 'walking past'} {approach} m", "near_dbm": [round(nL, 1), round(nR, 1)],
            "antennas": {a[0]: [round(c, 2) for c in a[1]] for a in e.ants},
            "wifi": {a[0]: {"att": round(-(e.iw[a[0]][0] - WIFI_DBM), 1), "at": [round(c, 2) for c in e.iw[a[0]][1]]}
                     for a in e.ants},
            "single": {"pos": [round(c, 2) for c in single], "att": [att(ant, single, eirp, True) for ant in e.ants]},
            "packs": packs}


def bsim_case_any(v: Venue, ins: Install, both=False, eirp=EIRP_UK):
    """run.py --geometry JSON for near_far_any's worst arrangement (packs 2-8: bsim cannot run pack 1's 2482): hot
    pack X where it hurts most (boom or stage), victim Z where it is weakest, the mirror-image hot pack Y if both;
    pack 1 at centre stage; the rest at the lowest-margin stage points."""
    plan = {k: f for k, f in PLAN.items() if k != 1}
    r = near_far_any(v, ins, eirp=eirp, plan=plan, both=both, k_hot=12 if both else 40)
    x, y, z, hq, q = r["at"]
    e = evaluate(v, ins)
    pos = {x: ("hot", hq, False), z: ("victim", q, True)}
    if y:
        pos[y] = ("hot mirror", (-hq[0], hq[1], hq[2]), False)
    centre = (0.0, v.depth / 2, PACK_Z)
    pos[1] = ("centre", centre, True)
    taken = [p[1] for p in pos.values()]
    rest = [k for k in PLAN if k not in pos]
    for k, pq in zip(rest, distinct([row[0] for row in sorted(e.rows, key=lambda row: row[4])], taken, len(rest))):
        pos[k] = ("worst", pq, True)
        taken.append(pq)
    single = min(e.rows, key=lambda row: row[4])[0]
    return {"venue": v.name, "install": ins.label(), "eirp": eirp, "model_worst_db": round(r["worst"], 2),
            "near_case": "near_far_any worst" + (" (both sides)" if both else ""),
            "antennas": {a[0]: [round(c, 2) for c in a[1]] for a in e.ants},
            "wifi": {a[0]: {"att": round(-(e.iw[a[0]][0] - WIFI_DBM), 1), "at": [round(c, 2) for c in e.iw[a[0]][1]]}
                     for a in e.ants},
            "single": {"pos": [round(c, 2) for c in single], "att": [att(ant, single, eirp, True) for ant in e.ants]},
            "packs": {str(k): {"kind": kind, "pos": [round(c, 2) for c in pq],
                               "att": [att(ant, pq, eirp, pess) for ant in e.ants]}
                      for k, (kind, pq, pess) in sorted(pos.items())}}


ANY_CASES = {"prosc12-any": (LARGE, False), "prosc12-any-both": (LARGE, True), "studio-any-both": (STUDIO, True),
             "prosc10-any-both": (PROSC, True)}


CASES = {  # file stem: (venue, install, near pack, approach, on axis)
    "studio-rule": (STUDIO, RULE, 7, 0.5, False),
    "prosc10-rule": (PROSC, RULE, 7, 0.5, False),
    "prosc12-rule": (LARGE, RULE, 7, 0.5, False),
    "prosc12-near2": (LARGE, RULE, 2, 0.5, False),
    "prosc12-onaxis": (LARGE, RULE, 7, 0.5, True),
    "studio-onaxis": (STUDIO, RULE, 7, 0.5, True),
    "prosc12-both": (LARGE, RULE, 2, 0.5, False, 6),     # actors in both wings: 2 at L, 6 at R; victim 3 (2426)
    "studio-both": (STUDIO, RULE, 2, 0.5, False, 6),
}


def options():
    """The options table rows: (venue, install) -> summary + near-far. Printed by main, asserted by audit.py."""
    rows = []
    for v in VENUES:
        for ins in (Install(), RULE, RULE_LO, replace(RULE, crew_ap_m=3.0), replace(RULE, ant=OMNI3),
                    replace(Install(ant=WIDE6), crew_ap_m=99.0, toe=15.0, tilt=20.0)):
            if ins == Install():
                ins = replace(ins, crew_ap_m=99.0)
            rows.append((v, ins, summary(evaluate(v, ins)), near_far(v, ins)))
    return rows


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--write", default="", help="directory for the run.py --geometry JSON files")
    a = ap.parse_args()
    thr = ci_threshold_db(2423)
    print(f"twin threshold, 11 MHz gap carrier, TD-length copy: C/I >= {thr:.1f} dB per Wi-Fi channel;"
          f" design needs {thr + MARGIN_DB:.1f}. Neighbour tolerance 3/4/5 MHz: "
          + ", ".join(f"{neighbour_tolerance_db(o):.1f}" for o in (3, 4, 5)) + " dB")
    for v, ins, s, nf in options():
        print(f"{v.name:<16} {ins.label():<80} margin ok {s['pass_sel']:6.1%} of the stage, worst {s['worst_margin']:+5.1f}"
              f" dB | near-far worst {nf['worst']:+5.1f}, extra {nf['extra_fail']:.1%} (strict RSSI {nf['strict_extra_fail']:.1%})")
    if a.write:
        d = Path(a.write)
        d.mkdir(parents=True, exist_ok=True)
        for stem, (v, ins, n, ap_m, ax, *nr) in CASES.items():
            (d / f"{stem}.json").write_text(json.dumps(bsim_case(v, ins, n, ap_m, ax, near_r=(nr or [None])[0]),
                                                       indent=1) + "\n")
            print(f"wrote {d / stem}.json")
        for stem, (v, b) in ANY_CASES.items():
            (d / f"{stem}.json").write_text(json.dumps(bsim_case_any(v, RULE, b), indent=1) + "\n")
            print(f"wrote {d / stem}.json")


if __name__ == "__main__":
    main()
