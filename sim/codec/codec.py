"""Reference codecs for OpenPack (SPEC AIR-3 / FW-4). Integer-only math so C can match bit-exactly.

Frame = 48 int16 samples (1 ms @ 48 kHz). Encoded = 3 B codec_state header + audio payload.
Every frame is self-contained: the header carries the decoder state.
  ADPCM-N : state = pred int16 BE (== sample 0, decoded exactly) + step index u8; audio = 48 x N-bit
            sign-magnitude codes, MSB-first (code 0 is padding, sample 0 comes from the header).
  BF 8+3  : state = 3 x 3-bit exponents in the top 9 bits of the 24-bit field (rest 0); audio =
            3 blocks x 16 signed 8-bit mantissas. Sample = mant << (exp+1).
"""
import numpy as np

N = 48
AIR3_MAX = 85  # AIR-3 max payload; fixed overhead seq 1 + status 2 = 3 B (no time diversity)
STEPS = [7, 8, 9, 10, 11, 12, 13, 14, 16, 17, 19, 21, 23, 25, 28, 31, 34, 37, 41, 45, 50, 55, 60, 66,
         73, 80, 88, 97, 107, 118, 130, 143, 157, 173, 190, 209, 230, 253, 279, 307, 337, 371, 408,
         449, 494, 544, 598, 658, 724, 796, 876, 963, 1060, 1166, 1282, 1411, 1552, 1707, 1878, 2066,
         2272, 2499, 2749, 3024, 3327, 3660, 4026, 4428, 4871, 5358, 5894, 6484, 7132, 7845, 8630,
         9493, 10442, 11487, 12635, 13899, 15289, 16818, 18500, 20350, 22385, 24623, 27086, 29794, 32767]
IDX_ADJ = [-1, -1, -1, -1, 2, 4, 6, 8]


def _clamp(x, lo, hi):
    return lo if x < lo else hi if x > hi else x


def _pack(codes, bits):
    acc = 0
    for c in codes:
        acc = (acc << bits) | c
    return acc.to_bytes(len(codes) * bits // 8, "big")


def _unpack(b, bits):
    acc = int.from_bytes(b, "big")
    return [(acc >> (bits * (N - 1 - i))) & ((1 << bits) - 1) for i in range(N)]


def _recon(code, bits, step):
    m = 1 << (bits - 1)
    mag = code & (m - 1)
    d = step * (2 * mag + 1) // m
    return (-d if code & m else d), mag


def _adpcm_enc(frame, bits):
    x = [int(v) for v in frame]
    m = 1 << (bits - 1)
    mad = sum(abs(x[i] - x[i - 1]) for i in range(1, N)) // (N - 1)
    idx = next((i for i, s in enumerate(STEPS) if s >= mad), len(STEPS) - 1)
    pred, hdr = x[0], bytes([(x[0] >> 8) & 255, x[0] & 255, idx])
    codes = [0]
    for i in range(1, N):
        step = STEPS[idx]
        diff = x[i] - pred
        mag = min(m - 1, abs(diff) * m // (2 * step))
        code = mag | (m if diff < 0 else 0)
        pred = _clamp(pred + _recon(code, bits, step)[0], -32768, 32767)
        idx = _clamp(idx + IDX_ADJ[mag * 8 // m], 0, len(STEPS) - 1)
        codes.append(code)
    return hdr + _pack(codes, bits)


def _adpcm_dec(b, bits):
    pred = int.from_bytes(b[0:2], "big", signed=True)
    idx = _clamp(b[2], 0, len(STEPS) - 1)
    m = 1 << (bits - 1)
    out = [pred]
    for code in _unpack(b[3:], bits)[1:]:
        d, mag = _recon(code, bits, STEPS[idx])
        pred = _clamp(pred + d, -32768, 32767)
        idx = _clamp(idx + IDX_ADJ[mag * 8 // m], 0, len(STEPS) - 1)
        out.append(pred)
    return np.array(out, dtype=np.int16)


def _bf_enc(frame):
    x = [int(v) for v in frame]
    exps, mants = 0, []
    for blk in range(3):
        b = x[16 * blk:16 * blk + 16]
        q = lambda v, e: (v + ((1 << (e + 1)) >> 1)) >> (e + 1)  # round half up
        e = next((e for e in range(8) if all(-128 <= q(v, e) <= 127 for v in b)), 7)
        mants += [_clamp(q(v, e), -128, 127) for v in b]
        exps = (exps << 3) | e
    return (exps << 15).to_bytes(3, "big") + bytes(v & 255 for v in mants)


def _bf_dec(b):
    exps = int.from_bytes(b[:3], "big") >> 15
    out = []
    for blk in range(3):
        e = (exps >> (3 * (2 - blk))) & 7
        out += [_clamp((v - 256 if v > 127 else v) << (e + 1), -32768, 32767) for v in b[3 + 16 * blk:19 + 16 * blk]]
    return np.array(out, dtype=np.int16)


def _chk(f):
    f = np.asarray(f)
    assert f.shape == (N,) and f.dtype == np.int16, "frame must be int16[48]"
    return f


# name -> (encode, decode); encode(int16[48]) -> bytes, decode(bytes) -> int16[48]
CODECS = {
    "adpcm6": (lambda f: _adpcm_enc(_chk(f), 6), lambda b: _adpcm_dec(b, 6)),
    "adpcm8": (lambda f: _adpcm_enc(_chk(f), 8), lambda b: _adpcm_dec(b, 8)),
    "bf8_3": (lambda f: _bf_enc(_chk(f)), _bf_dec),
}
FRAME_BYTES = {"adpcm6": 39, "adpcm8": 51, "bf8_3": 51}  # incl. 3 B codec_state


def snr_db(a, b):
    a, b = a.astype(float), b.astype(float)
    return 10 * np.log10(((a * a).sum() + 1e-9) / (((a - b) ** 2).sum() + 1e-9))


def test_signal(frames=200):
    """Deterministic whisper->scream sweep: 440 Hz + 3 kHz tones, amplitude 30..24000, plus noise."""
    t = np.arange(frames * N) / 48000
    amp = np.geomspace(30, 24000, t.size)
    rng = np.random.default_rng(12)
    s = amp * (0.7 * np.sin(2 * np.pi * 440 * t) + 0.25 * np.sin(2 * np.pi * 3000 * t)) + rng.normal(0, 1, t.size) * amp * 0.02
    return np.clip(np.round(s), -32768, 32767).astype(np.int16).reshape(frames, N)


def selfcheck():
    """Asserts sizes, edge cases, SNR floors; returns {codec: SNR dB}."""
    sig = test_signal()
    floor = {"adpcm6": 25, "adpcm8": 40, "bf8_3": 35}
    edge = np.where(np.arange(N) % 2, 32767, -32768).astype(np.int16)
    res = {}
    for name, (enc, dec) in CODECS.items():
        assert all(len(enc(f)) == FRAME_BYTES[name] for f in sig)
        assert 3 + FRAME_BYTES[name] <= AIR3_MAX, name  # + seq/status
        assert (dec(enc(np.zeros(N, np.int16))) == 0).all()
        dec(enc(edge))  # extremes must not crash/overflow
        out = np.concatenate([dec(enc(f)) for f in sig])
        res[name] = round(float(snr_db(sig.ravel(), out)), 1)
        assert res[name] > floor[name], (name, res[name])
    return res


if __name__ == "__main__":
    print(selfcheck())
