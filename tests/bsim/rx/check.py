"""RX-2/RX-3/RX-4/RX-10 check from a bsim receiver log (tests/bsim/rx/run.sh).
usage: check.py <rx log> <pack boot times, s, comma list> <pack stop times, s, comma list>
For each pack boot: the receiver locks (net core "RX lock t_us=") within LOCK_MAX s (RX-2). Every whole
RXAPP second (app core, one line per second of merged frames received over IPC) between that lock
and the pack's stop must show 1000 +- 1 frames, all valid, 0 lost, 0 seq skips, and both copies
received (clean channel: RX-3 tracks windows A and B). Exit code != 0 on failure."""
import re
import sys

LOCK_MAX = 2.0


def main(path, starts, stops):
    starts = [float(x) for x in starts.split(",")]
    stops = [float(x) for x in stops.split(",")]
    text = open(path, errors="replace").read()
    locks = [int(t) / 1e6 for t in re.findall(r"RX lock epoch=\d+ t_us=(\d+)", text)]
    reacq = [int(t) / 1e6 for t in re.findall(r"RX reacquire epoch=\d+ t_us=(\d+)", text)]
    secs = [{k: int(v) for k, v in re.findall(r"(\w+)=(-?\d+)", m)}
            for m in re.findall(r"RXAPP (.*)", text)]
    ok = True
    out = []
    for k, (s, e) in enumerate(zip(starts, stops)):
        nxt = starts[k + 1] if k + 1 < len(starts) else 1e9
        lk = [t for t in locks if s <= t < nxt]
        if not lk:
            print(f"pack {k}: boot {s:.4f} s, no lock")
            ok = False
            continue
        dt = lk[0] - s
        ok &= dt <= LOCK_MAX
        steady = [x for x in secs if x["t_ms"] / 1e3 - 1 >= lk[0] and x["t_ms"] / 1e3 <= e]
        tot = {f: sum(x[f] for x in steady) for f in ("frames", "valid", "lost", "a_ok", "b_ok", "skips")}
        bad = [x["t_ms"] for x in steady if not (999 <= x["frames"] <= 1001 and x["lost"] == 0 and
               x["skips"] == 0 and x["a_ok"] == x["b_ok"] == x["valid"] == x["frames"])]
        ok &= bool(steady) and not bad
        out.append(f"pack{k}_lock_s={dt:.4f}")
        print(f"pack {k}: boot {s:.4f} s, lock {lk[0]:.6f} s (+{dt * 1e3:.1f} ms), steady seconds "
              f"{len(steady)}, {tot}, bad seconds at t_ms {bad or 'none'}")
    print(f"reacquire at s: {[round(t, 4) for t in reacq]}")
    print(f"RX_CHECK {' '.join(out)} {'PASS' if ok else 'FAIL'}")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main(*sys.argv[1:4])
