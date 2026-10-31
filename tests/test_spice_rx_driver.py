"""RX-8 / ADR-0014: run hw/spice/rx_driver.cir (receiver DAC -> balanced line driver) in ngspice and assert
gain/level vs SPEC, flatness, op-amp common mode and output swing vs its rails, Zout, rail rejection, noise."""
import math, os, pathlib, shutil, subprocess
import pytest

CIR = pathlib.Path(__file__).resolve().parents[1] / "hw/spice/rx_driver.cir"
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
        swing[name] = (rail, out_lo, out_hi)
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
    print(f"gain {g:.2f} dB | 0 dBFS = {fs_dbu:+.2f} dBu, -20 dBFS = {fs_dbu - 20:+.2f} dBu"
          f" | 20 Hz-20 kHz {min(band) - g:+.2f}..{max(band) - g:+.2f} dB (10k), {min(a600) - g:+.2f} dB (600R)"
          f" | out {lo[1]:.2f}..{lo[2]:.2f} V on {lo[0]:.2f} V, {hi[1]:.2f}..{hi[2]:.2f} V on {hi[0]:.2f} V"
          f" | Zout {z1k:.0f} ohm @1k, {z20:.0f} @20 Hz | rail->out {at(rail_db, 1e3):.0f} dB @1k, {at(rail_db, 20):.0f} @20 Hz"
          f" | noise {noise_dbu:.1f} dBu 20-20k")
    assert abs(fs_dbu - 18.0) <= 0.3                 # RX-8: max +18 dBu
    assert abs((fs_dbu - 20) - (-2.0)) <= 0.3        # RX-8: nominal -20 dBFS = -2 dBu
    assert max(band) - min(band) <= 0.2              # SYS-4 allows +-0.5 dB for the whole chain
    assert z1k <= 100.0                              # RX-8: Zout <= 100 ohm (balanced, 1 kHz)
    assert at(rail_db, 1e3) <= -60.0
    assert noise_dbu <= -100.0                       # >= 6 dB under the DAC floor (+18 dBu - 112 dB = -94 dBu)
