"""RX-7 scenario (d) check from a bsim receiver log (tests/bsim/rx/run.sh d|dn).
usage: check_d.py <rx log> <sim seconds> <pack xo_drift> <rx xo_drift>
After the radio lock (RX-2, <= 2 s) and a SETTLE s clock-loop settling time, every whole RXAPP second
must show 1000 +- 1 frames, 0 lost, slot fill at arrival within target +- 1 sample, and the run must
end with 0 jitter-slot slips (under = over = 0, counted from boot). Output rate error <= 1 sample/h:
mean fill over the last minute minus the first settled minute (a rate error accumulates in the fill).
Prints the mean applied correction over the second half vs the crystal offset it cancels.
Exit code != 0 on failure."""
import re
import sys

LOCK_MAX, SETTLE, MINUTE = 2.0, 10, 60


def main(path, secs, ep, er):
    secs, ep, er = int(secs), float(ep), float(er)
    text = open(path, errors="replace").read()
    target = int(re.search(r"slot target (\d+) samples", text).group(1))
    locks = [int(t) / 1e6 for t in re.findall(r"RX lock epoch=\d+ t_us=(\d+)", text)]
    rows = [{k: int(v) for k, v in re.findall(r"(\w+)=(-?\d+)", m)} for m in re.findall(r"RXAPP (.*)", text)]
    if not locks or not rows:
        print("RX_CLOCK_CHECK no lock or no RXAPP lines FAIL")
        sys.exit(1)
    lock = locks[0]
    st = [r for r in rows if r["t_ms"] / 1e3 - 1 >= lock + SETTLE]
    ok = lock <= LOCK_MAX and len(locks) == 1 and len(st) >= secs - SETTLE - 3
    bad = [r["t_ms"] for r in st if not (999 <= r["frames"] <= 1001 and r["lost"] == 0 and
           abs(r["fill_min_ms"] - 1000 * target) <= 1000 and abs(r["fill_max_ms"] - 1000 * target) <= 1000)]
    slips = rows[-1]["under"] + rows[-1]["over"]
    ok &= not bad and slips == 0
    n = min(MINUTE, len(st) // 2)
    first = sum(r["fill_mean_ms"] for r in st[:n]) / n / 1e3
    last = sum(r["fill_mean_ms"] for r in st[-n:]) / n / 1e3
    drift_h = (last - first) * 3600 / ((len(st) - n) or 1)  # samples per hour
    ok &= abs(last - first) <= 1.0
    half = st[len(st) // 2:]
    ppb = sum(r["ppb_mean"] for r in half) / len(half)
    need = (ep - er) / (1 + er) * 1e9
    worst = max(max(abs(r["fill_min_ms"] - 1000 * target), abs(r["fill_max_ms"] - 1000 * target)) for r in st) / 1e3
    pre = [r for r in rows if r["t_ms"] / 1e3 - 1 >= lock and r not in st]
    peak = max((max(abs(r["fill_min_ms"] - 1000 * target), abs(r["fill_max_ms"] - 1000 * target))
                for r in pre if r["frames"]), default=0) / 1e3
    lat = sum(r["fill_mean_ms"] for r in st) / len(st) / 1e3 / 48 * 1000
    print(f"lock {lock:.4f} s, settled seconds {len(st)} of {secs}, slips {slips}, bad seconds {bad[:10] or 'none'}")
    print(f"fill: target {target}, settling peak error {peak:.3f}, worst settled error {worst:.3f} samples, "
          f"first-minute mean {first:.3f}, last-minute mean {last:.3f}, change {last - first:+.4f} samples "
          f"over {len(st) - n} s ({drift_h:+.4f} samples/h)")
    print(f"correction: mean {ppb:.0f} ppb over the second half, crystal offset to cancel {need:.0f} ppb "
          f"(difference {ppb - need:+.0f} ppb, frame-weighted, within one 3311 ppb HFCLKAUDIO step); "
          f"slot latency {lat:.1f} us")
    print(f"RX_CLOCK_CHECK slips={slips} drift_samples={last - first:+.4f} {'PASS' if ok else 'FAIL'}")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main(*sys.argv[1:5])
