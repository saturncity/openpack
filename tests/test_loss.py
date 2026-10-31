import os, sys
import numpy as np

ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, os.path.join(ROOT, "sim", "loss"))
import traces, plc


def B(s):
    return np.array([c == "x" for c in s])


def test_frame_lost_and_td():
    a, b = B("xx.x......"), B("x..x......")
    assert list(traces.frame_lost(a, b, False).nonzero()[0]) == [0, 3]   # both copies lost
    # frame 0 recovered by packet 2 (arrives), frame 3 recovered by packet 5
    assert not traces.frame_lost(a, b, True).any()
    a, b = B("x.x......."), B("x.x.......")                               # n and n+2 both lost
    assert list(traces.frame_lost(a, b, True).nonzero()[0]) == [0]        # 2 recovered by packet 4


def test_metrics():
    lost = B("..xxx..xx.x")
    pct, mx, ev = traces.metrics(lost, frames_per_h=lost.size)
    assert mx == 3 and ev == 1 and abs(pct - 600 / 11) < 1e-9


def test_trace_reproducible_and_busy():
    la, lb = traces.trace(0.2, frames=200_000)
    la2, _ = traces.trace(0.2, frames=200_000)
    assert (la == la2).all() and la.size == 200_000
    assert 0.17 < la.mean() * 1 / 0.9 < 0.23 and not (la & lb).all()


def test_plc():
    f = np.tile(np.arange(1, 13, dtype=np.int16)[:, None] * 1000, (1, 48))
    lost = np.zeros(12, bool); lost[1:] = True
    out = plc.apply_plc(f, lost)
    assert (out[0] == 1000).all() and (out[1:11] == 1000).all()          # repeat for 10 ms
    assert out[11, 0] == 1000 and out[11, -1] < 50 and (np.diff(out[11]) <= 0).all()  # 1 ms fade
    g = np.vstack([f, f[:2] * 0 + 7])
    out = plc.apply_plc(g, np.r_[lost, True, False])
    assert not out[12].any() and (out[13] == 7).all()                    # mute after fade, then recover
    assert not plc.apply_plc(f, np.ones(12, bool)).any()                 # nothing heard yet -> silence


def test_per_copy_busy():
    la, lb = traces.trace(0.01, 0.9, frames=300_000)
    assert la.mean() < 0.02 and 0.7 < lb.mean() < 0.9
