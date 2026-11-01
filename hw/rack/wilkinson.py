"""1:8 Wilkinson splitter (RK-2, ADR-0018) on the rack main board: a corporate tree of three 2-way Wilkinson stages
in microstrip on the JLCPCB 4-layer stackup. Pure numpy (CI has no scikit-rf); tests/test_rack_rf.py cross-checks
it against scikit-rf's MLine when that is installed.

Run:  python hw/rack/wilkinson.py      -> prints insertion loss, isolation and match over 2400-2483.5 MHz

Model:
  * Microstrip: Hammerstad-Jensen static Z0 / eps_eff with the strip-thickness correction (Hammerstad & Jensen,
    "Accurate models for microstrip computer-aided design", MTT-S 1980), conductor loss from the surface resistance
    with the Hammerstad roughness factor, dielectric loss from tan(delta) with the filling factor.
  * Each line is a lossy 2-port in Y parameters; the tree is one nodal admittance matrix, Kron-reduced to its 9
    ports (50 ohm each), then S = (Y0 - Y)(Y0 + Y)^-1.
  * Isolation resistors are 100 ohm 0402 thin film with 0.4 nH series inductance (est., 0402 body + pads).
  * Not modelled: T-junction and bend discontinuities, the resistor pad stubs, coupling between arms. They come
    with layout (#34); audit.py adds WILK_LAYOUT_DB on top of the modelled loss for them.

Stackup: JLCPCB JLC04161H-7628 (1.6 mm, 4 layers), the default 4-layer stackup on jlcpcb.com/impedance:
L1 outer copper 1 oz (0.035 mm) over 7628 prepreg 0.2104 mm to the L2 ground plane, er 4.4 (JLCPCB's
stated value for 7628). JLCPCB does not publish a loss tangent: tan(delta) = 0.02 is the FR-4 class value at
1-3 GHz (est.; Isola FR406 0.0167 at 2 GHz, generic FR-4 0.02). Copper roughness 1.0 um rms (est., ED foil).
"""
import math

import numpy as np

C0 = 299_792_458.0
MU0 = 4e-7 * math.pi
ETA0 = 376.730313668

# ---- JLC04161H-7628 (jlcpcb.com/impedance, 4-layer 1.6 mm default), L1 signal over L2 ground ----
STACKUP = {
    "name": "JLCPCB JLC04161H-7628, L1 over L2",
    "h_m": 0.2104e-3,      # 7628 prepreg thickness (JLCPCB stackup table)
    "t_m": 0.035e-3,       # 1 oz finished outer copper
    "er": 4.4,             # JLCPCB stated dielectric constant for 7628
    "tand": 0.02,          # est. (not published by JLCPCB; FR-4 class value at 2.4 GHz)
    "sigma": 5.8e7,        # copper, S/m
    "rough_m": 1.0e-6,     # est. rms roughness, ED copper
}
BAND_HZ = (2400e6, 2483.5e6)
F0_HZ = 2441.75e6          # band centre: quarter-wave lengths are cut for it
Z0_PORT = 50.0
R_ISO = 100.0              # 2 x Z0 (Wilkinson)
L_ISO = 0.4e-9             # est.: 0402 resistor + pads
# Layout assumptions (#34 may change them; the tests re-run at the extremes): 50 ohm feed lengths in metres.
FEED_IN_M = 5e-3           # band filter -> stage 1
FEED_12_M = 10e-3          # stage 1 arm -> stage 2 input
FEED_23_M = 6e-3           # stage 2 arm -> stage 3 input
FEED_OUT_M = 5e-3          # stage 3 arm -> u.FL output


def _z_air(u):
    f = 6 + (2 * math.pi - 6) * math.exp(-((30.666 / u) ** 0.7528))
    return ETA0 / (2 * math.pi) * math.log(f / u + math.sqrt(1 + (2 / u) ** 2))


def _eeff_static(u, er):
    a = 1 + math.log((u ** 4 + (u / 52) ** 2) / (u ** 4 + 0.432)) / 49 + math.log(1 + (u / 18.1) ** 3) / 18.7
    b = 0.564 * ((er - 0.9) / (er + 3)) ** 0.053
    return (er + 1) / 2 + (er - 1) / 2 * (1 + 10 / u) ** (-a * b)


def microstrip(w_m, s=STACKUP):
    """(Z0 ohm, eps_eff) with the Hammerstad-Jensen thickness correction."""
    h, t, er = s["h_m"], s["t_m"], s["er"]
    u = w_m / h
    tn = t / h
    du1 = tn / math.pi * math.log(1 + 4 * math.e / (tn / math.tanh(math.sqrt(6.517 * u)) ** 2))
    dur = 0.5 * (1 + 1 / math.cosh(math.sqrt(er - 1))) * du1
    u1, ur = u + du1, u + dur
    ee = _eeff_static(ur, er) * (_z_air(u1) / _z_air(ur)) ** 2
    return _z_air(ur) / math.sqrt(ee), ee


def width_for(z0, s=STACKUP):
    """Strip width for a target Z0 (bisection: Z0 falls monotonically with width)."""
    lo, hi = 0.01e-3, 3e-3
    for _ in range(80):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if microstrip(mid, s)[0] > z0 else (lo, mid)
    return (lo + hi) / 2


def gamma(w_m, f_hz, s=STACKUP):
    """Propagation constant alpha + j beta (1/m) and Z0 of a microstrip of width w at f."""
    z0, ee = microstrip(w_m, s)
    er, tand = s["er"], s["tand"]
    beta = 2 * math.pi * f_hz * math.sqrt(ee) / C0
    rs = math.sqrt(math.pi * f_hz * MU0 / s["sigma"])
    skin = math.sqrt(1 / (math.pi * f_hz * MU0 * s["sigma"]))
    k_rough = 1 + 2 / math.pi * math.atan(1.4 * (s["rough_m"] / skin) ** 2)
    alpha_c = rs / (z0 * w_m) * k_rough                       # Np/m, wide-strip approximation
    alpha_c *= 1.15                                           # est.: ground-plane return current and edge crowding
    alpha_d = math.pi * f_hz / C0 * er / math.sqrt(ee) * (ee - 1) / (er - 1) * tand
    return alpha_c + alpha_d + 1j * beta, z0


def quarter_wave_m(w_m, f_hz=F0_HZ, s=STACKUP):
    return C0 / (4 * f_hz * math.sqrt(microstrip(w_m, s)[1]))


class _Net:
    """Nodal admittance matrix builder. Node 0 is ground and is dropped."""

    def __init__(self):
        self.n = 1
        self.elems = []

    def node(self):
        self.n += 1
        return self.n - 1

    def line(self, a, b, w_m, length_m):
        self.elems.append(("tl", a, b, w_m, length_m))

    def series(self, a, b, r, l=0.0):
        self.elems.append(("rl", a, b, r, l))

    def y(self, f_hz, s):
        Y = np.zeros((self.n, self.n), complex)
        for e in self.elems:
            if e[0] == "tl":
                _, a, b, w, ln = e
                g, z0 = gamma(w, f_hz, s)
                gl = g * ln
                y11, y12 = 1 / (z0 * np.tanh(gl)), -1 / (z0 * np.sinh(gl))
                Y[a, a] += y11; Y[b, b] += y11; Y[a, b] += y12; Y[b, a] += y12
            else:
                _, a, b, r, l = e
                y = 1 / (r + 2j * math.pi * f_hz * l)
                Y[a, a] += y; Y[b, b] += y; Y[a, b] -= y; Y[b, a] -= y
        return Y[1:, 1:]


def build_tree(stages=3, s=STACKUP, r_iso=R_ISO, l_iso=L_ISO, feeds=None):
    """Corporate 1:2^stages Wilkinson tree. Returns (net, port nodes [input, out1..outN]), widths used."""
    feeds = feeds or (FEED_IN_M, FEED_12_M, FEED_23_M, FEED_OUT_M)
    w50, w70 = width_for(Z0_PORT, s), width_for(Z0_PORT * math.sqrt(2), s)
    lq = quarter_wave_m(w70, F0_HZ, s)
    net = _Net()
    p_in = net.node()
    a = net.node()
    net.line(p_in, a, w50, feeds[0])
    heads = [a]
    for k in range(stages):
        nxt = []
        for h in heads:
            arms = []
            for _ in range(2):
                e = net.node()
                net.line(h, e, w70, lq)
                arms.append(e)
            net.series(arms[0], arms[1], r_iso, l_iso)
            for e in arms:
                o = net.node()
                net.line(e, o, w50, feeds[1 + k] if k + 1 < len(feeds) else feeds[-1])
                nxt.append(o)
        heads = nxt
    return net, [p_in] + heads, {"w50_m": w50, "w70_m": w70, "lq_m": lq}


def sparams(f_hz, stages=3, s=STACKUP, **kw):
    """S matrix (ports: 0 = input, 1..N = outputs, 50 ohm) at each frequency. Shape (len(f), N+1, N+1)."""
    net, ports, _ = build_tree(stages, s, **kw)
    pidx = [p - 1 for p in ports]
    others = [i for i in range(net.n - 1) if i not in pidx]
    out = []
    for f in np.atleast_1d(f_hz):
        Y = net.y(f, s)
        ypp = Y[np.ix_(pidx, pidx)]
        ypi, yip, yii = Y[np.ix_(pidx, others)], Y[np.ix_(others, pidx)], Y[np.ix_(others, others)]
        yr = ypp - ypi @ np.linalg.solve(yii, yip)
        y0 = np.eye(len(pidx)) / Z0_PORT
        out.append((y0 - yr) @ np.linalg.inv(y0 + yr))
    return np.array(out)


def db(x):
    return 20 * np.log10(np.abs(x))


def summary(n_pts=11, stages=3, s=STACKUP, **kw):
    """Worst case over the band: insertion loss (input -> any output), excess over the ideal 3n dB split, output
    to output isolation (worst pair), input and output return loss."""
    f = np.linspace(*BAND_HZ, n_pts)
    S = sparams(f, stages, s, **kw)
    n = 2 ** stages
    il = -db(S[:, 1:, 0])                       # (f, n)
    iso = -db(S[:, 1:, 1:])
    for k in range(S.shape[0]):
        np.fill_diagonal(iso[k], np.inf)
    return {
        "il_db": float(il.max()), "il_min_db": float(il.min()),
        "ideal_db": 10 * math.log10(n), "excess_db": float(il.max() - 10 * math.log10(n)),
        "imbalance_db": float((il.max(1) - il.min(1)).max()),
        "iso_db": float(iso.min()),
        "rl_in_db": float((-db(S[:, 0, 0])).min()),
        "rl_out_db": float(min((-db(S[:, j, j])).min() for j in range(1, n + 1))),
        **build_tree(stages, s, **kw)[2],
    }


if __name__ == "__main__":
    st = STACKUP
    r = summary(21)
    z50, ee50 = microstrip(r["w50_m"])
    z70, ee70 = microstrip(r["w70_m"])
    print(f"stackup {st['name']}: h {st['h_m'] * 1e3:.4f} mm, er {st['er']}, tan(d) {st['tand']} (est.),"
          f" Cu {st['t_m'] * 1e3:.3f} mm")
    print(f"  50 ohm: w {r['w50_m'] * 1e3:.3f} mm (Z0 {z50:.1f}, eeff {ee50:.2f});"
          f" 70.7 ohm: w {r['w70_m'] * 1e3:.3f} mm (Z0 {z70:.1f}, eeff {ee70:.2f}), lambda/4 {r['lq_m'] * 1e3:.2f} mm")
    print(f"  1:8 over {BAND_HZ[0] / 1e6:.0f}-{BAND_HZ[1] / 1e6:.1f} MHz: IL {r['il_min_db']:.2f}-{r['il_db']:.2f} dB"
          f" (ideal {r['ideal_db']:.2f}, excess {r['excess_db']:.2f}), imbalance {r['imbalance_db']:.2f} dB,"
          f" isolation >= {r['iso_db']:.1f} dB, RL in {r['rl_in_db']:.1f} / out {r['rl_out_db']:.1f} dB")
