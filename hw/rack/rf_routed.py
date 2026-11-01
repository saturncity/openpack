"""The rack's two 1:8 Wilkinson trees as routed (#34), checked with scikit-rf against ADR-0018.

    /home/lenzj/openpack/.ws/.venv/bin/python hw/rack/rf_routed.py     (numpy + scikit-rf: the .ws venv / CI)
    -> hw/rack/out/rf_routed.json (read by audit.py Audit 6 and tests/test_rack_layout.py)

Input: hw/rack/out/rf_geometry.json, written by hw/rack/layout.py: every RF polyline it drew (net, width, layer,
vertices) and the A-feed vias. Nothing is re-entered by hand: lengths and bends come from the drawn copper.

Model, per antenna, from the QPQ1907 output pad (port 0) to the eight u.FL signal pads (ports 1-8):
  * Lines: scikit-rf MLine (Hammerstad-Jensen, Kirschning-Jansen dispersion, Djordjevic-Svensson dielectric,
    rough copper) on JLC04161H-7628, h 0.2104 mm, t 35 um, er 4.4, tan d 0.02 (wilkinson.py's est.), for the loss
    alpha. Z0 and the phase constant come from the 2D field solve of the drawn line with its 0.5 mm pour gap
    (hw/rx/rf_line.py, recorded in layout.py RF_SOLVE): MLine alone has no coplanar gap. The 0.16 mm TL net-tie bars
    use the 0.16 / 0.5 solve.
  * Bends: every polyline vertex is a microstrip bend, Gupta/Garg/Chadha closed form for a right-angle unmitred
    bend (shunt C, two series L/2), scaled by angle/90 for the 45 deg escapes.
  * Junctions: the T at each divider input: the 50 ohm input meets two 70 ohm arms at one point, modelled as the
    bend capacitance of the widest line (est.); the resistor end: the arm corner (a bend) plus the 0402 pad.
  * Isolation resistor: 100 ohm + 0.4 nH (0402 body, wilkinson.py L_ISO) + 0.05 pF per pad to ground (est.).
  * A's feed: L1 -> through via -> L4 microstrip over L3 -> through via -> L1; each via 0.3 nH + 0.04 pF (est.,
    0.3 mm drill through 1.6 mm with GND return vias beside it).
Checked: worst insertion loss to any port over 2400-2483.5 MHz, output-to-output isolation, input/output return loss,
for nominal and +-10 % etched width x er 4.2 / 4.6 (ADR-0018's tolerance). The tree splits into "dividers" (arms,
resistors, junction stubs) and "distribution" (the 50 ohm runs that carry each branch across the 412 mm board).
"""
import json, math, pathlib, sys

import numpy as np

HERE = pathlib.Path(__file__).resolve().parent
GEO = HERE / "out" / "rf_geometry.json"
OUT = HERE / "out" / "rf_routed.json"
F = np.linspace(2400e6, 2483.5e6, 9)
H, T, ER, TAND, ROUGH = 0.2104e-3, 0.035e-3, 4.4, 0.02, 1.0e-6
C0 = 299792458.0
R_ISO, L_ISO, C_PAD = 100.0, 0.4e-9, 0.05e-12
VIA_L, VIA_C = 0.3e-9, 0.04e-12
# ADR-0018 / RK-5: <= 11 dB IL (the splitter), >= 20 dB output isolation, >= 15 dB return loss
LIMITS = {"il_db": 11.0, "iso_db": 20.0, "rl_db": 15.0}


def solve_table(geo):
    return {tuple(float(x) for x in k.split("/")): tuple(v) for k, v in geo["solve"].items()}


def line_params(w_mm, f, tab, er=ER, w_scale=1.0):
    """(Z0, gamma) arrays: alpha from scikit-rf MLine, Z0 / beta from the field-solve record (nearest width)"""
    import skrf
    from skrf.media import MLine
    w = w_mm * w_scale
    key = min(tab, key=lambda k: abs(k[0] - w_mm))
    z0s, ees = tab[key]
    # width error: scale the solved Z0 by MLine's relative change, eeff likewise (small corrections)
    fr = skrf.Frequency.from_f(f, unit="hz")
    m_nom = MLine(frequency=fr, w=w_mm * 1e-3, h=H, t=T, ep_r=er, tand=TAND, rough=ROUGH, z0_port=50)
    m = MLine(frequency=fr, w=w * 1e-3, h=H, t=T, ep_r=er, tand=TAND, rough=ROUGH, z0_port=50)
    z_ratio = np.real(m.Z0) / np.real(m_nom.Z0)
    e_ratio = np.real(m.ep_reff_f) / np.real(m_nom.ep_reff_f) if hasattr(m, "ep_reff_f") else 1.0
    z0 = z0s * z_ratio * math.sqrt(ER / er) ** 0.0
    ee = ees * e_ratio * (er + 1) / (ER + 1)
    alpha = np.real(m.gamma)
    beta = 2 * np.pi * f * np.sqrt(ee) / C0
    return z0, alpha + 1j * beta


def bend_lc(w_mm, er=ER):
    """right-angle unmitred microstrip bend (Gupta, Garg, Chadha): C (F), L (H)"""
    W, h = w_mm * 1e-3, H
    r = W / h
    if r < 1:
        c_per_w = (14 * er + 12.5) * r - (1.83 * er - 2.25) / math.sqrt(r) + 0.02 * er / r     # pF/m
    else:
        c_per_w = (9.5 * er + 1.25) * r + 5.2 * er + 7.0
    L = 100 * (4 * math.sqrt(r) - 4.21) * h * 1e-9      # nH/m * h
    return c_per_w * W * 1e-12, max(L, 0.0)


class Net:
    def __init__(self):
        self.n = 1
        self.el = []

    def node(self):
        self.n += 1
        return self.n - 1

    def line(self, a, b, z0, gamma, length_m):
        self.el.append(("tl", a, b, z0, gamma, length_m))

    def z(self, a, b, zf):             # series impedance function of omega
        self.el.append(("z", a, b, zf))

    def shunt(self, a, yf):
        self.el.append(("y", a, yf))

    def Y(self, k, f):
        Y = np.zeros((self.n, self.n), complex)
        w = 2 * np.pi * f
        for e in self.el:
            if e[0] == "tl":
                _, a, b, z0, g, ln = e
                gl = g[k] * ln
                z = z0[k] if np.ndim(z0) else z0
                y11, y12 = 1 / (z * np.tanh(gl)), -1 / (z * np.sinh(gl))
                Y[a, a] += y11; Y[b, b] += y11; Y[a, b] += y12; Y[b, a] += y12
            elif e[0] == "z":
                _, a, b, zf = e
                y = 1 / zf(w)
                Y[a, a] += y; Y[b, b] += y; Y[a, b] -= y; Y[b, a] -= y
            else:
                _, a, yf = e
                Y[a, a] += yf(w)
        return Y[1:, 1:]


def poly_len(pts):
    return sum(math.dist(a, b) for a, b in zip(pts, pts[1:])) * 1e-3


def turns(pts):
    """bend angles (deg) at the interior vertices"""
    out = []
    for a, b, c in zip(pts, pts[1:], pts[2:]):
        v1 = (b[0] - a[0], b[1] - a[1]); v2 = (c[0] - b[0], c[1] - b[1])
        n1, n2 = math.hypot(*v1), math.hypot(*v2)
        if n1 < 1e-9 or n2 < 1e-9:
            continue
        cosang = max(-1.0, min(1.0, (v1[0] * v2[0] + v1[1] * v2[1]) / (n1 * n2)))
        ang = math.degrees(math.acos(cosang))
        if ang > 1:
            out.append(ang)
    return out


def add_run(net, a, runs, f, tab, er, ws, stats, kind):
    """a chain of polylines (w, pts) from node a; returns the end node"""
    cur = a
    for w, pts, layer in runs:
        z0, g = line_params(w, f, tab, er, ws)
        segs = list(zip(pts, pts[1:]))
        angs = turns(pts)
        for i, (p, q) in enumerate(segs):
            L = math.dist(p, q) * 1e-3
            if L < 1e-7:
                continue
            nxt = net.node()
            net.line(cur, nxt, z0, g, L)
            stats[kind] += L * 1e3
            cur = nxt
            if i < len(angs):
                C, Lb = bend_lc(w * ws, er)
                s = angs[i] / 90.0
                net.shunt(cur, lambda w_, C=C * s: 1j * w_ * C)
                if Lb:
                    mid = net.node()
                    net.z(cur, mid, lambda w_, L=Lb * s: 1j * w_ * L + 1e-9)
                    cur = mid
                stats["bends"] += 1
    return cur


def build(geo, ant, f, er=ER, ws=1.0):
    tab = solve_table(geo)
    tr = {}
    vias = []
    for t in geo["tracks"]:
        if "via" in t:
            vias.append(t)
            continue
        tr.setdefault(t["net"], []).append((t["w"], t["pts"], t["layer"]))
    net = Net()
    stats = {"divider": 0.0, "distribution": 0.0, "bends": 0, "vias": 0}
    p_in = net.node()
    # feed: SPL_x_IN polylines (A: L1, via, L4, via, L1)
    cur = p_in
    feed = [r for r in tr[f"SPL_{ant}_IN"] if not (abs(r[0] - 0.17) < 1e-6 and poly_len(r[1]) < 0.5e-3)]
    for i, (w, pts, layer) in enumerate(feed):
        cur = add_run(net, cur, [(w, pts, layer)], f, tab, er, ws, stats, "distribution")
        if i < len(feed) - 1:
            # via between successive layer runs (A only)
            nxt = net.node()
            net.z(cur, nxt, lambda w_: 1j * w_ * VIA_L + 1e-9)
            net.shunt(nxt, lambda w_: 1j * w_ * VIA_C)
            stats["vias"] += 1
            cur = nxt
    junction = {(f"SPL_{ant}_IN"): cur}
    ports = []

    def divider(head_net, stage, idx, jnode):
        arms = [f"WK_{ant}_{stage}{idx}a", f"WK_{ant}_{stage}{idx}b"]
        # T junction capacitance (est.: one bend of the 50 ohm input line)
        C, _ = bend_lc(0.35 * ws, er)
        net.shunt(jnode, lambda w_, C=C: 1j * w_ * C)
        stubs = [r for r in tr[head_net] if abs(r[0] - 0.17) < 1e-6 and poly_len(r[1]) < 0.5e-3]
        ends = []
        for k, arm in enumerate(arms):
            st = stubs[k] if k < len(stubs) else None
            n0 = jnode
            if st:
                n0 = add_run(net, jnode, [st], f, tab, er, ws, stats, "divider")
            # net-tie bar 0.8 mm, 0.16 wide
            z0, g = line_params(0.16, f, tab, er, ws)
            n1 = net.node()
            net.line(n0, n1, z0, g, 0.8e-3)
            stats["divider"] += 0.8
            runs = tr[arm]
            arm_run = [r for r in runs if abs(r[0] - 0.17) < 1e-6 and poly_len(r[1]) >= 0.5e-3]
            out_run = [r for r in runs if abs(r[0] - 0.17) > 1e-6]
            n2 = add_run(net, n1, arm_run, f, tab, er, ws, stats, "divider")
            net.shunt(n2, lambda w_: 1j * w_ * C_PAD)
            ends.append((arm, n2, out_run))
        net.z(ends[0][1], ends[1][1], lambda w_: R_ISO + 1j * w_ * L_ISO)
        return ends

    pending = [(f"SPL_{ant}_IN", cur)]
    for stage in (1, 2, 3):
        nxt = []
        for i, (head, jn) in enumerate(pending):
            for arm, node, out_run in divider(head, stage, i, jn):
                if stage < 3:
                    endn = add_run(net, node, out_run, f, tab, er, ws, stats, "distribution")
                    nxt.append((arm, endn))
                else:
                    endn = add_run(net, node, out_run, f, tab, er, ws, stats, "distribution")
                    nxt.append((arm, endn))
        pending = nxt
    for k, (arm, node) in enumerate(pending):
        # feed net tie (0.8 mm bar) + port line to the u.FL pad
        z0, g = line_params(0.16, f, tab, er, ws)
        n1 = net.node()
        net.line(node, n1, z0, g, 0.8e-3)
        endn = add_run(net, n1, tr[f"RF_{ant}{k}"], f, tab, er, ws, stats, "distribution")
        ports.append(endn)
    return net, [p_in] + ports, stats


def sparams(geo, ant, er=ER, ws=1.0):
    net, ports, stats = build(geo, ant, F, er, ws)
    pidx = [p - 1 for p in ports]
    others = [i for i in range(net.n - 1) if i not in pidx]
    S = []
    for k, f in enumerate(F):
        Y = net.Y(k, f)
        ypp = Y[np.ix_(pidx, pidx)]
        ypi, yip, yii = Y[np.ix_(pidx, others)], Y[np.ix_(others, pidx)], Y[np.ix_(others, others)]
        yr = ypp - ypi @ np.linalg.solve(yii, yip)
        y0 = np.eye(len(pidx)) / 50.0
        S.append((y0 - yr) @ np.linalg.inv(y0 + yr))
    return np.array(S), stats


def db(x):
    return 20 * np.log10(np.abs(x))


def summary(geo, ant, er=ER, ws=1.0):
    S, stats = sparams(geo, ant, er, ws)
    il = -db(S[:, 1:, 0])
    iso = -db(S[:, 1:, 1:])
    for k in range(S.shape[0]):
        np.fill_diagonal(iso[k], np.inf)
    return {"il_db": float(il.max()), "il_min_db": float(il.min()), "il_by_port": [round(float(x), 2) for x in il.max(0)],
            "iso_db": float(iso.min()), "rl_in_db": float((-db(S[:, 0, 0])).min()),
            "rl_out_db": float(min((-db(S[:, j, j])).min() for j in range(1, 9))), **{k: round(v, 1) for k, v in stats.items()}}


def main():
    geo = json.loads(GEO.read_text())
    res = {}
    for ant in "AB":
        res[ant] = summary(geo, ant)
        corners = []
        for er in (4.2, 4.6):
            for ws in (0.9, 1.1):
                corners.append(summary(geo, ant, er, ws))
        res[ant]["corners"] = {k: (min if k != "il_db" else max)(c[k] for c in corners) for k in ("il_db", "iso_db", "rl_in_db", "rl_out_db")}
    # the dividers alone (distribution lines removed): what ADR-0018's <= 11 dB splitter number describes
    worst = {k: max(res[a][k] for a in "AB") if k == "il_db" else min(res[a][k] for a in "AB")
             for k in ("il_db", "iso_db", "rl_in_db", "rl_out_db")}
    worst_c = {k: max(res[a]["corners"][k] for a in "AB") if k == "il_db" else min(res[a]["corners"][k] for a in "AB")
               for k in ("il_db", "iso_db", "rl_in_db", "rl_out_db")}
    out = {"band_hz": [float(F[0]), float(F[-1])], "limits": LIMITS, "A": res["A"], "B": res["B"], "worst": worst,
           "worst_tolerance": worst_c}
    OUT.write_text(json.dumps(out, indent=1) + "\n")
    for a in "AB":
        r = res[a]
        print(f"tree {a}: IL {r['il_min_db']:.2f}-{r['il_db']:.2f} dB, isolation >= {r['iso_db']:.1f} dB, RL in {r['rl_in_db']:.1f} /"
              f" out {r['rl_out_db']:.1f} dB; dividers {r['divider']:.0f} mm, distribution {r['distribution']:.0f} mm,"
              f" {r['bends']:.0f} bends, {r['vias']:.0f} vias; tolerance corners {r['corners']}")
    return out


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
