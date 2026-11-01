"""#97 / ADR-0022: frame lead loop check from one bsim pack log (tests/bsim/sched/lead.sh).

The net core prints PACK_IPC once per second (latch margin min/max in that second, cumulative
overruns = frames overwritten before air = seq skips, underruns = slots repeated); the app core prints
PACK_LEAD once per second (the loop's reference, the earliest frame's margin, its correction).
Closed loop, asserted:
  - 0 skips (overruns) over the run; 0 repeats (underruns) after the first second (start-up: the net
    core sends before the app core's first frame)
  - every frame reached the net core before its latch (margin_us_min > 0 every second)
  - after SETTLE_S: every PACK_LEAD margin within +-HOLD_US of the reference (the lead holds)
  - the log covers the run (no early exit)
--open (negative control, loop open): asserts the opposite, that the run slipped or the lead drifted.
Prints LEAD_CHECK ... PASS; exit code != 0 on failure.

usage: check_lead.py <pack.log> <seconds> <fclk ppb> [--open]
"""
import re
import sys

SETTLE_S, HOLD_US = 60, 3


def rows(text, tag):
    return [dict((k, int(v)) for k, v in re.findall(r"(\w+)=(-?\d+)", m)) for m in re.findall(rf"{tag} (.*)", text)]


def main(path, secs, ppb, open_loop=False):
    text = open(path, errors="replace").read()
    ipc, lead = rows(text, "PACK_IPC"), rows(text, "PACK_LEAD")
    assert len(ipc) >= secs - 2 and len(lead) >= secs - 2, f"log covers {len(ipc)} / {len(lead)} of {secs} s"
    skips = ipc[-1]["overruns"]
    repeats = ipc[-1]["underruns"] - ipc[0]["underruns"]
    mmin = min(r["margin_us_min"] for r in ipc)
    ref = lead[0]["ref_us"]
    ss = [r["margin_us"] for r in lead if r["reports"] / 10 > SETTLE_S]
    dev = max((abs(m - ref) for m in ss), default=None)
    peak = max(abs(r["margin_us"] - ref) for r in lead)
    mean = sum(ss) / len(ss) if ss else float("nan")
    ppb_ss = [r["ppb"] for r in lead if r["reports"] / 10 > SETTLE_S]
    corr = sum(ppb_ss) / len(ppb_ss) if ppb_ss else float("nan")
    per_h = 3600 / secs
    line = (f"LEAD_CHECK fclk_ppb={ppb} secs={secs} {'open' if open_loop else 'closed'} skips={skips} "
            f"repeats={repeats} skips_per_h={skips * per_h:g} margin_us_min={mmin} ref_us={ref} "
            f"peak_dev_us={peak} ss_dev_us={dev} ss_margin_us={mean:.2f} ss_correction_ppb={corr:.0f}")
    if open_loop:
        assert skips + repeats > 0 or (dev is not None and dev > HOLD_US), "open loop held the lead?"
        print(line + " (negative control: slipped as expected) PASS")
        return
    assert skips == 0, f"{skips} frames never on air"
    assert repeats == 0, f"{repeats} repeated slots"
    assert mmin > 0, f"a frame reached the net core {-mmin} us after its latch"
    assert dev is not None and dev <= HOLD_US, f"lead not held: {dev} us from the reference after {SETTLE_S} s"
    print(line + " PASS")


if __name__ == "__main__":
    a = [x for x in sys.argv[1:] if x != "--open"]
    main(a[0], int(a[1]), int(a[2]), "--open" in sys.argv)
