"""AIR-4 schedule check from a bsim phy Tx dump (one pack, fw defaults). Asserts per frame, +-5 us:
copy A every 1000 us on fA, copy B on fB starting T_GAP after copy A ends, copy B ends before the
reserved RX slot (t0 + 700, t0 = copy A TXEN = A.start - ramp), copies identical, and seq (payload
byte 0, dump byte 2 after S0 + LENGTH) advances by 1 or repeats, never skips: every IPC frame (FW-2)
reaches the air. Repeats bounded at 1 % (the audio frame clock and TIMER0 share the crystal: 0).

With the input WAV (run.sh writes it): every frame's ADPCM-6 bytes equal sim/codec/codec.py's encoding
of WAV frame n (n = seq unwrapped), status = 0: the app-core pipeline (#87) is bit-exact and in order.
With the pack log: the net core's PACK_IPC lines (latch - frame arrival, us) give the worst margin
the frame thread had left; it must stay > 0 (FW-2, #87).
Prints worst-case errors; exit code != 0 on failure.

usage: check.py <Tx.csv> [pack.log [in.wav]]  |  check.py --wav <out.wav> <seconds>
"""
import csv
import math
import os
import re
import sys
import wave

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../../sim/codec"))

FA, FB, T_GAP, RAMP, RX_SLOT, TOL = 2424, 2473, 100, 41, 700, 5
SETTLE = 5  # frames sent before the app core's first IPC message arrives
SEQ, HDR, N = 2, 3, 48  # dump offset of seq; AIR-3 seq + status; samples per frame


def write_wav(path, secs):
    """Deterministic test input: a 100 Hz - 8 kHz log chirp per second, -10 dBFS, 48 kHz mono 16 bit."""
    fs, n = 48000, int(secs * 48000)
    ph, out = 0.0, bytearray()
    for i in range(n):
        f = 100 * 80 ** ((i % fs) / fs)
        ph += 2 * math.pi * f / fs
        out += int(10362 * math.sin(ph)).to_bytes(2, "little", signed=True)
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(fs)
        w.writeframes(bytes(out))


def main(path, log=None, wav=None):
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
            if d > 1:
                print(f"  seq skip at frame {k} (t = {a[0] / 1e3:.3f} ms): {d - 1} frame(s) never on air")
            skips += d > 1
            repeats += d == 0
    extra = ""
    if wav:
        import codec
        enc = codec.CODECS["adpcm6"][0]
        import numpy as np
        with wave.open(wav) as w:
            pcm = np.frombuffer(w.readframes(w.getnframes()), "<i2")
        n, bad, checked = frames[SETTLE][0][3][SEQ], 0, 0  # < 256 frames since start: n = seq
        for k in range(SETTLE + 1, len(frames)):
            p = frames[k][0][3]
            n += (p[SEQ] - frames[k - 1][0][3][SEQ]) % 256
            if (n + 1) * N > len(pcm):
                break
            checked += 1
            e = enc(pcm[n * N:(n + 1) * N])  # dump = S0, LENGTH, payload, CRC
            bad += p[SEQ + 1:SEQ + HDR] != b"\0\0" or p[SEQ + HDR:SEQ + HDR + len(e)] != e
        assert checked >= 200 and bad == 0, f"{bad} of {checked} payloads differ from codec.py (ADPCM-6)"
        extra += f" codec_bitexact={checked}"
    if log:
        rows = [dict((k, int(v)) for k, v in re.findall(r"(\w+)=(-?\d+)", m))
                for m in re.findall(r"PACK_IPC (.*)", open(log).read())]
        assert rows, "no PACK_IPC lines in the pack log (CONFIG_OP_TEST_SCHED_REPORT)"
        lo = min(r["margin_us_min"] for r in rows)
        extra += f" latch_margin_us_min={lo} latch_margin_us_max={max(r['margin_us_max'] for r in rows)}"
        assert lo > 0, f"a frame reached the net core {-lo} us after its latch"
    assert skips == 0, f"{skips} IPC frames never reached the air"
    assert repeats <= 0.01 * len(frames), f"{repeats} repeated frames"
    print(f"SCHED_CHECK frames={len(frames)} worst_period_err_us={w_per:g} worst_gap_err_us={w_gap:g} "
          f"rx_slot_slack_us={slack:g} seq_skips={skips} repeats={repeats}{extra} PASS")


if __name__ == "__main__":
    if sys.argv[1] == "--wav":
        write_wav(sys.argv[2], float(sys.argv[3]))
    else:
        main(*sys.argv[1:4])
