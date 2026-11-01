"""Quasi-static 2D field solve of the receiver's RF line cross-section (#34): the check behind layout_rx.RF_W / RF_GAP.

    /home/lenzj/openpack/.ws/.venv/bin/python hw/rx/rf_line.py     (needs numpy + scipy: the .ws venv, not KiCad's python)

Why a solver: the closed-form conductor-backed CPW formula (Wadell 3.4.3, also KiCad's calculator) is only good for
gaps under about the dielectric height. Here h = 0.2104 mm (JLC04161H-7628 L1-L2 prepreg), so a buildable gap is
already > h and that formula misses by +7 ohm at the microstrip limit. The solver is checked against the pack's
Hammerstad-Jensen microstrip (hw/pack/layout.py microstrip_z0) with the side grounds removed.

Model: finite differences on a uniform grid (5 um), L2 plane at y = 0, FR4 7628 er 4.4 up to h, 35 um copper on top
(trace + coplanar grounds, which extend to the box sides), air above, grounded box 1.5 mm above the board.
C with the dielectric and C0 in air give eeff = C / C0, Z0 = 1 / (c sqrt(C C0)). No solder mask (it lowers Z0 by
about 1-2 ohm on JLC's LPI mask; inside JLC's +-10 % impedance tolerance).
Grid check: 5 um -> 2.5 um lowers Z0 by 0.7 ohm, a 2x larger box raises it by 0.4 ohm. The microstrip case reads
51.35 ohm against Hammerstad-Jensen's 50.0, so the solver's raw numbers carry a +1.35 ohm offset; CAL removes it.
Result (2026-11-01, RESULTS): w = 0.31 mm with a 0.25 mm gap -> 51.48 raw, 50.1 ohm calibrated (0.30: 51.0, 0.32: 49.3).
layout_rx.py takes RF_W / RF_GAP from here; tests/test_rx_layout.py checks the record (and re-solves when numpy exists).
"""
import sys

H, T, ER = 0.2104, 0.035, 4.4
DX = 0.005
C_LIGHT, EPS0 = 299792458.0, 8.8541878128e-12

# (w, gap) -> raw (Z0 ohm, eeff) from solve() at DX = 5 um; gap None = no coplanar ground (microstrip)
RESULTS = {(0.346, None): (51.35, 3.13), (0.30, 0.25): (52.33, 2.93), (0.31, 0.25): (51.48, 2.94), (0.32, 0.25): (50.66, 2.95),
           (0.33, 0.25): (49.87, 2.96), (0.39, 0.25): (45.63, 3.02), (0.35, 0.5): (50.17, 3.10), (0.31, 0.30): (52.26, 2.98)}
HJ_MICROSTRIP_0346 = 50.0                      # hw/pack/layout.py microstrip_z0(0.346)
CAL = RESULTS[(0.346, None)][0] - HJ_MICROSTRIP_0346
RF_W, RF_GAP = 0.31, 0.25


def z_cal(w, gap):
    return RESULTS[(w, gap)][0] - CAL


def solve(w, gap=None, half_width=1.6, top=1.5):
    import numpy as np
    from scipy.sparse import lil_matrix
    from scipy.sparse.linalg import spsolve
    nx = int(round(half_width / DX)) + 1                    # x >= 0 (symmetric half, Neumann at x = 0)
    ny = int(round((H + T + top) / DX)) + 1
    jh, jt = int(round(H / DX)), int(round((H + T) / DX))
    xs = np.arange(nx) * DX

    def run(er_sub):
        fixed = np.zeros((ny, nx), bool)
        v = np.zeros((ny, nx))
        fixed[0, :] = True; fixed[-1, :] = True; fixed[:, -1] = True     # L2 plane, box lid, box side (0 V)
        for j in range(jh, jt + 1):
            tr = xs <= w / 2 + 1e-9
            fixed[j, tr] = True; v[j, tr] = 1.0
            if gap is not None:
                gnd = xs >= w / 2 + gap - 1e-9
                fixed[j, gnd] = True
        eps = np.ones((ny, nx)); eps[:jh, :] = er_sub                    # cell (j, i) material below row j+1/2
        idx = -np.ones((ny, nx), int)
        free = np.argwhere(~fixed)
        idx[~fixed] = np.arange(len(free))
        A = lil_matrix((len(free), len(free)))
        b = np.zeros(len(free))
        for k, (j, i) in enumerate(free):
            # face permittivities: vertical faces average the two cells' eps, horizontal faces use the lower/upper cell
            nb = []
            for dj, di in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                jj, ii = j + dj, i + di
                if ii < 0:
                    ii = 1                                                   # mirror at x = 0
                e = eps[min(j, jj), i] if dj else 0.5 * (eps[j, i] + eps[j - 1, i] if j > 0 else 2 * eps[j, i])
                nb.append((jj, ii, e))
            diag = 0.0
            for jj, ii, e in nb:
                diag += e
                if fixed[jj, ii]:
                    b[k] += e * v[jj, ii]
                else:
                    A[k, idx[jj, ii]] -= e
            A[k, k] = diag
        sol = spsolve(A.tocsr(), b)
        v[~fixed] = sol
        # energy: W = 1/2 sum eps |grad V|^2 over cell faces (x2 for the mirrored half)
        ex = np.diff(v, axis=1); ey = np.diff(v, axis=0)
        epsv = eps.copy()
        epsv[1:, :] = 0.5 * (eps[1:, :] + eps[:-1, :])                    # node row j sits between cells j-1 and j
        epx = epsv[:, :-1]                                                   # same weights as the matrix rows
        epy = eps[:-1, :]
        energy = (epx * ex ** 2).sum() + (epy * ey ** 2).sum()
        return 2 * EPS0 * energy                                             # C per metre for V = 1 (both halves)
    C, C0 = run(ER), run(1.0)
    return 1 / (C_LIGHT * (C * C0) ** 0.5), C / C0


def main():
    for (w, g), (zr, _) in RESULTS.items():
        z, ee = solve(w, g)
        print(f"w {w:.3f} gap {g}: Z0 {z:.2f} ohm raw (recorded {zr}), {z - CAL:.1f} calibrated, eeff {ee:.2f}")


if __name__ == "__main__":
    sys.exit(main())
