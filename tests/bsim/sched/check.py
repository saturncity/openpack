"""AIR-4 schedule check from a bsim phy Tx dump (one pack, fw defaults). Asserts per frame, +-5 us:
copy A every 1000 us on fA, copy B on fB starting T_GAP after copy A ends, copy B ends before the
reserved RX slot (t0 + 700, t0 = copy A TXEN = A.start - ramp), copies identical, and seq (payload
byte 0, dump byte 2 after S0 + LENGTH) advances by 1 or repeats, never skips: every IPC frame (FW-2)
reaches the air. Repeats are the placeholder source's k_timer (1 ms rounds to 33 RTC ticks = 1007 us,
~0.7 % repeats); bounded at 1 %. The real source is the ADC, on the same crystal as TIMER0.
Prints worst-case errors; exit code != 0 on failure."""
import csv
import sys

FA, FB, T_GAP, RAMP, RX_SLOT, TOL = 2424, 2473, 100, 41, 700, 5
SETTLE = 5  # frames sent before the app core's first IPC message arrives
SEQ = 2


def main(path):
    tx = [(float(r["start_time"]), float(r["end_time"]), round(2400 + float(r["center_freq"])),
           bytes.fromhex(r["packet"])) for r in csv.DictReader(open(path))]
    assert tx and tx[0][2] == FA, "first packet is not copy A on fA"
    frames = [tx[i:i + 2] for i in range(0, len(tx) - 1, 2)]
    assert len(frames) >= 200, f"only {len(frames)} frames"
    w_per = w_gap = 0.0
    slack = 1e9
    skips = repeats = 0
    for k, (a, b) in enumerate(frames):
        assert (a[2], b[2]) == (FA, FB), f"frame {k}: carriers {a[2]} {b[2]}"
        assert a[3] == b[3], f"frame {k}: copies differ"
        gap = b[0] - a[1] - T_GAP
        assert abs(gap) <= TOL, f"frame {k}: B.start - A.end - T_GAP = {gap} us"
        w_gap = max(w_gap, abs(gap))
        slack = min(slack, a[0] - RAMP + RX_SLOT - b[1])
        assert slack >= 0, f"frame {k}: copy B runs into the RX slot"
        if k:
            per = a[0] - frames[k - 1][0][0] - 1000
            assert abs(per) <= TOL, f"frame {k}: period error {per} us"
            w_per = max(w_per, abs(per))
        if k > SETTLE:
            d = (a[3][SEQ] - frames[k - 1][0][3][SEQ]) % 256
            skips += d > 1
            repeats += d == 0
    assert skips == 0, f"{skips} IPC frames never reached the air"
    assert repeats <= 0.01 * len(frames), f"{repeats} repeated frames"
    print(f"SCHED_CHECK frames={len(frames)} worst_period_err_us={w_per:g} worst_gap_err_us={w_gap:g} "
          f"rx_slot_slack_us={slack:g} seq_skips={skips} repeats={repeats} PASS")


if __name__ == "__main__":
    main(sys.argv[1])
