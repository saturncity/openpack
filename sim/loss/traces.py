"""Per-frame loss traces: audit.py's Gilbert-Elliott (same defaults, same busy->transition math), two independent
channels (A, B >= 40 MHz apart), numpy-vectorised via geometric sojourn times. Run: python3 sim/loss/traces.py"""
import inspect, os, sys
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
import audit

_D = {k: v.default for k, v in inspect.signature(audit.burst_loss).parameters.items()}
FRAMES_1H = 3_600_000
BUSY = [0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40]


def ge_channel(busy, frames, rng, mean_burst=_D["mean_burst_frames"], p_bad=_D["p_bad"], p_good=_D["p_good"]):
    """bool[frames]: copy lost. Same transition probabilities as audit.burst_loss."""
    b2g = 1 / mean_burst
    g2b = b2g * busy / (1 - busy)
    n = frames // 2 + 2                      # every good+bad cycle lasts >= 2 frames
    lens = np.empty(2 * n, np.int64)
    lens[0::2], lens[1::2] = rng.geometric(g2b, n), rng.geometric(b2g, n)
    state = np.repeat(np.tile([False, True], n), lens)[:frames]
    return rng.random(frames) < np.where(state, p_bad, p_good)


def frame_lost(la, lb, time_div):
    """Lost = both copies lost; with time diversity also needs packet n+2 (either copy) to fail."""
    lost = la & lb
    if time_div:
        lost[:-2] &= lost[2:].copy()
    return lost


def metrics(lost, frames_per_h=FRAMES_1H):
    """(residual %, max consecutive lost, dropout events/h = runs >= 3, scaled to 1 h)."""
    d = np.diff(np.concatenate([[0], lost.view(np.int8), [0]]))
    runs = np.flatnonzero(d == -1) - np.flatnonzero(d == 1)
    return 100 * lost.mean(), int(runs.max(initial=0)), (runs >= 3).sum() * frames_per_h / lost.size


def trace(busy, frames=FRAMES_1H, seed=1):
    """(lostA, lostB) for one busy fraction; fixed seed -> reproducible."""
    rng = np.random.default_rng([seed, int(round(busy * 1000))])
    return ge_channel(busy, frames, rng), ge_channel(busy, frames, rng)


def table():
    rows = ["| busy % | TD off: residual % | max run | events/h | TD on: residual % | max run | events/h |",
            "|---|---|---|---|---|---|---|"]
    for b in BUSY:
        la, lb = trace(b)
        m0, m1 = metrics(frame_lost(la, lb, False)), metrics(frame_lost(la, lb, True))
        rows.append(f"| {b:.0%} | {m0[0]:.3f} | {m0[1]} | {m0[2]:.0f} | {m1[0]:.3f} | {m1[1]} | {m1[2]:.0f} |")
    return "\n".join(rows)


if __name__ == "__main__":
    print(table())
