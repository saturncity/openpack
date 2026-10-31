"""PK-2 / ADR-0006 / ADR-0012: run hw/spice/preamp.cir in ngspice batch and assert the three numbers."""
import math, pathlib, shutil, subprocess
import pytest

CIR = pathlib.Path(__file__).resolve().parents[1] / "hw/spice/preamp.cir"
pytestmark = pytest.mark.skipif(not shutil.which("ngspice"), reason="ngspice not installed")


def rows(p):
    return [tuple(map(float, l.split())) for l in p.read_text().splitlines() if l.strip()]


def a_weight(f):  # IEC 61672 A-weighting, linear magnitude, 0 dB at 1 kHz
    s = f * f
    return 1.2588966 * 148840000 * s * s / ((s + 424.36) * math.sqrt((s + 11599.29) * (s + 544496.41)) * (s + 148840000))


def test_preamp(tmp_path):
    subprocess.run(["ngspice", "-b", str(CIR)], cwd=tmp_path, check=True, capture_output=True)
    # .noise: input-referred (to mic EMF, 1k source + 2.2k bias included), A-weighted 20 Hz-20 kHz
    n = rows(tmp_path / "noise.txt")
    uv = 1e6 * math.sqrt(sum((a[1] * a_weight(a[0])) ** 2 * (b[0] - a[0]) for a, b in zip(n, n[1:])))
    # .ac: mid-band gain and 20 Hz-40 kHz flatness
    ac = rows(tmp_path / "ac.txt")
    mid = min(ac, key=lambda r: abs(r[0] - 1e3))[1]
    lo, hi = min(r[1] for r in ac), max(r[1] for r in ac)
    # .tran: 0.6 Vrms (0.8485 V pk) at 1 kHz; rails 0..5 V, op-amp swing clamp 0.05..4.95 V
    tr = rows(tmp_path / "tran.txt")
    vmax, vmin = max(r[1] for r in tr), min(r[1] for r in tr)
    # PCM1840 pin: pseudo-differential (INM AC-grounded) full scale assumed 1 Vrms = 1.414 V peak (ADR-0012)
    adc_pk = max(abs(r[3]) for r in tr)
    # 5 V rail -> preamp output with the 100R/47u mic-bias filter (#31): 1 V on the rail, signal off
    rail = rows(tmp_path / "rail.txt")
    rail_1k = min(rail, key=lambda r: abs(r[0] - 1e3))[1]
    print(f"noise {uv:.3f} uV A-wtd | gain {mid:.2f} dB, {lo:.2f}..{hi:.2f} dB | out {vmin:.2f}..{vmax:.2f} V"
          f" | adc {adc_pk:.2f} V pk | rail->out {rail_1k:.1f} dB @1k")
    assert uv <= 1.0
    assert adc_pk < 1.414
    assert rail_1k <= -30.0
    assert hi - lo <= 3.0 and lo > mid - 3.0           # -3 dB at 20 Hz and 40 kHz at worst
    assert 0.2 < vmin and vmax < 4.8                   # >=150 mV clear of the clamp: no clipping
