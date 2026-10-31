"""RX-6 PLC: repeat the last good frame for the first 10 ms of loss (frames 1-10), frame 11 repeats it with a
1 ms linear fade to 0, then mute; the next good frame plays as is. ponytail: no fade-in on recovery."""
import numpy as np

N, MUTE_AFTER = 48, 10
FADE = np.linspace(1, 0, N, endpoint=False)


def apply_plc(frames, lost):
    """frames int16[F,48] decoded; lost bool[F] -> int16[F,48]."""
    out, last, run = frames.copy(), np.zeros(N, np.int16), 0
    for i in range(len(frames)):
        if not lost[i]:
            last, run = frames[i], 0
            continue
        run += 1
        out[i] = last if run <= MUTE_AFTER else (last * FADE).astype(np.int16) if run == MUTE_AFTER + 1 else 0
    return out
