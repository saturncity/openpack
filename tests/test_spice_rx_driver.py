"""RX-8 / ADR-0014: run hw/spice/rx_driver.cir (receiver DAC -> balanced line driver) in ngspice and assert
gain/level vs SPEC, flatness, op-amp common mode and output swing vs its rails, Zout, rail rejection, noise."""
import math, os, pathlib, shutil, subprocess, cmath
import pytest

SPICE = pathlib.Path(__file__).resolve().parents[1] / "hw/spice"
CIR = SPICE / "rx_driver.cir"
if not os.environ.get("CI"):   # CI installs ngspice: a skip there would hide a broken driver
    pytestmark = pytest.mark.skipif(not shutil.which("ngspice"), reason="ngspice not installed")

DAC_FS_VRMS = 2.1      # PCM5102A full-scale single-ended output (TI SLAS859C, Device Comparison)
DBU = 0.7746           # 0 dBu in Vrms
SWING = 0.5            # OPA1656 output kept 0.5 V from each rail: AOL test range at RL = 2k (SBOS901C 6.6)
CM_HEADROOM = 2.25     # OPA1656 input CM range (V-)..(V+) - 2.25 V (SBOS901C 6.6)


def rows(p):
    return [tuple(map(float, l.split())) for l in p.read_text().splitlines() if l.strip()]


def at(data, f):
    return min(data, key=lambda r: abs(r[0] - f))[1]


def cols(p):   # wrdata writes (x, y) pairs per vector
    t = rows(p)
    return [[r[2 * i + 1] for r in t] for i in range(len(t[0]) // 2)]


def test_rx_driver(tmp_path):
    r = subprocess.run(["ngspice", "-b", str(CIR)], cwd=tmp_path, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout[-1500:] + r.stderr[-1500:]
    ac = rows(tmp_path / "ac10k.txt")
    g = at(ac, 1e3)                                             # dB, balanced out / DAC out
    fs_dbu = 20 * math.log10(DAC_FS_VRMS * 10 ** (g / 20) / DBU)
    band = [r[1] for r in ac if 20 <= r[0] <= 20e3]
    a600 = [r[1] for r in rows(tmp_path / "ac600.txt") if 20 <= r[0] <= 20e3]
    z1k = at(rows(tmp_path / "zout.txt"), 1e3)
    z20 = at(rows(tmp_path / "zout.txt"), 20)
    swing = {}
    for name in ("lo", "hi"):
        diff, oa, ob, vcm, ina, inb, v12a, cp, hp = cols(tmp_path / f"tran_{name}.txt")
        rail = min(v12a)
        out_lo, out_hi = min(min(oa), min(ob)), max(max(oa), max(ob))
        swing[name] = (rail, out_lo, out_hi, min(vcm), max(vcm))
        # no clipping: output inside the swing limit with 0.2 V to spare, and the full 0 dBFS peak arrives
        assert out_lo >= SWING + 0.2 and out_hi <= rail - SWING - 0.2, (name, out_lo, out_hi, rail)
        pk = (max(diff) - min(diff)) / 2
        unclipped = DAC_FS_VRMS * math.sqrt(2) * 10 ** (g / 20) * 2e3 / (2e3 + z1k)   # tran load is 2k balanced
        assert pk >= 0.99 * unclipped, (name, pk, unclipped)
        # op-amp inputs (both + at VCM, both - virtual grounds) inside the CM range with 0.2 V margin
        cm = vcm + ina + inb
        assert min(cm) >= 0.2 and max(cm) <= rail - CM_HEADROOM - 0.2, (name, min(cm), max(cm))
        # BAV99 clamp nodes stay between the rails: the clamps never conduct on programme
        assert min(cp + hp) > 0.0 and max(cp + hp) < rail, name
    rail_db = rows(tmp_path / "rail.txt")
    n = rows(tmp_path / "noise.txt")
    noise_v = math.sqrt(sum(a[1] ** 2 * (b[0] - a[0]) for a, b in zip(n, n[1:])))
    noise_dbu = 20 * math.log10(noise_v / DBU)
    lo, hi = swing["lo"], swing["hi"]
    # headroom above +18 dBu full scale before the outputs reach the swing limit, at the worst (lowest) rail
    leg_pk = min(lo[3] - SWING, lo[0] - SWING - lo[4])
    clip_dbu = 20 * math.log10(2 * leg_pk / math.sqrt(2) / DBU)
    print(f"gain {g:.2f} dB | 0 dBFS = {fs_dbu:+.2f} dBu, -20 dBFS = {fs_dbu - 20:+.2f} dBu"
          f" | 20 Hz-20 kHz {min(band) - g:+.2f}..{max(band) - g:+.2f} dB (10k), {min(a600) - g:+.2f} dB (600R)"
          f" | out {lo[1]:.2f}..{lo[2]:.2f} V on {lo[0]:.2f} V, {hi[1]:.2f}..{hi[2]:.2f} V on {hi[0]:.2f} V"
          f" | Zout {z1k:.0f} ohm @1k, {z20:.0f} @20 Hz | rail->out {at(rail_db, 1e3):.0f} dB @1k, {at(rail_db, 20):.0f} @20 Hz"
          f" | noise {noise_dbu:.1f} dBu 20-20k | rail->out {at(rail_db, 100):.0f} dB @100 Hz"
          f" | clip {clip_dbu:+.1f} dBu at {lo[0]:.2f} V: headroom {clip_dbu - fs_dbu:.1f} dB over full scale")
    assert abs(fs_dbu - 18.0) <= 0.3                 # RX-8: max +18 dBu
    assert abs((fs_dbu - 20) - (-2.0)) <= 0.3        # RX-8: nominal -20 dBFS = -2 dBu
    assert max(band) - min(band) <= 0.2              # SYS-4 allows +-0.5 dB for the whole chain
    assert z1k <= 100.0                              # RX-8: Zout <= 100 ohm (balanced, 1 kHz)
    assert at(rail_db, 1e3) <= -60.0
    assert at(rail_db, 100) <= -80.0                 # 100 Hz brick ripple (UK 50 Hz mains, #81 review S2)
    assert clip_dbu - fs_dbu >= 1.0                  # covers PCM5102A full-scale spread (2.1 Vrms is typical only)
    assert noise_dbu <= -100.0                       # >= 6 dB under the DAC floor (+18 dBu - 112 dB = -94 dBu)


def run(deck, tmp_path):
    r = subprocess.run(["ngspice", "-b", str(SPICE / deck)], cwd=tmp_path, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout[-1500:] + r.stderr[-1500:]
    assert "Timestep too small" not in r.stdout + r.stderr


def test_rx_driver_cable_and_phantom(tmp_path):
    """#81 review S5/M2: 10 nF per leg (~100 m mic cable) + 600 ohm: phase margin and step overshoot;
    phantom short: S1J clamp surge vs its rating."""
    run("rx_driver_load.cir", tmp_path)
    pms = []
    for f in ("loopa.txt", "loopb.txt"):
        t = [(r[0], -complex(r[1], r[2]) / complex(r[4], r[5])) for r in rows(tmp_path / f)]
        fc, tc = next((f2, t2) for (f1, t1), (f2, t2) in zip(t, t[1:]) if abs(t1) >= 1 > abs(t2))
        pms.append((fc, 180 + math.degrees(cmath.phase(tc))))
    st = rows(tmp_path / "step.txt")
    over = []
    for i in range(4):                      # oa, ob, hot, cold
        v = [r[2 * i + 1] for r in st if r[0] > 9e-6]
        step = v[-1] - v[0]
        over.append(100 * (max((y - v[0]) / step for y in v) - 1))
    sh = rows(tmp_path / "short.txt")
    t, i_d4 = [r[0] for r in sh], [abs(r[1]) for r in sh]
    i2t = sum(a * a * (t2 - t1) for a, t1, t2 in zip(i_d4, t, t[1:]))
    print(f"loop A fc {pms[0][0] / 1e6:.1f} MHz PM {pms[0][1]:.0f} deg | loop B fc {pms[1][0] / 1e6:.1f} MHz PM {pms[1][1]:.0f} deg"
          f" | step overshoot {max(over):.2f} % | phantom short: S1J peak {max(i_d4):.2f} A, I2t {i2t * 1e3:.2f} mA2s")
    assert all(pm >= 45 for _, pm in pms)                 # coordinator: phase margin >= 45 deg into 10 nF + 600R
    assert max(over) <= 10.0                              # and <= 10 % overshoot on a step
    # S1J: IFSM 30 A for an 8.3 ms half sine = 3.7 A2s; keep the event under a tenth of that, and the peak under 30 A
    assert max(i_d4) < 30 and i2t < 0.37


def test_rx_driver_power_cycle(tmp_path):
    """#81 review M1/M3: brick on, relay closes at 5 s, brick dies at 6 s: no thump at the XLR, op-amp inputs safe."""
    run("rx_driver_power.cir", tmp_path)
    r = rows(tmp_path / "power.txt")
    t = [x[0] for x in r]
    hot, cold, vcm, v12a, rly = ([x[2 * i + 1] for x in r] for i in range(5))
    diff = [abs(h - c) for h, c in zip(hot, cold)]
    cm = [abs(h + c) / 2 for h, c in zip(hot, cold)]
    t_close = next(a for a, b in zip(t, rly) if b > 0.5)
    t_open = next(a for a, b in zip(t, rly) if a > t_close and b < 0.5)
    print(f"relay closes {t_close:.3f} s, opens {t_open:.4f} s | XLR diff max {max(diff) * 1e3:.3f} mV,"
          f" common mode max {max(cm) * 1e3:.3f} mV | VCM - (+12VA) max {max(v - w for v, w in zip(vcm, v12a)):.2f} V")
    assert 5.0 < t_close < 5.05 and 6.0 < t_open < 6.02
    assert max(diff) < 1e-3 and max(cm) < 10e-3         # no thump: < -58 dBu differential at power-up and power-down
    assert max(v - w for v, w in zip(vcm, v12a)) < 0.5  # +IN never above V+ + 0.5 V (SBOS901C 6.1)
