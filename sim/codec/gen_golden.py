"""Regenerate golden vectors: python3 sim/codec/gen_golden.py  (deterministic)."""
import os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(__file__))
import codec

d = os.path.join(os.path.dirname(__file__), "golden")
os.makedirs(d, exist_ok=True)
edge = np.where(np.arange(codec.N) % 2, 32767, -32768).astype(np.int16)
pcm = np.vstack([np.zeros(codec.N, np.int16), edge, codec.test_signal(30)])  # silence, full-scale, sweep
pcm.astype("<i2").tofile(os.path.join(d, "pcm_in.bin"))
for name, (enc, dec) in codec.CODECS.items():
    e = [enc(f) for f in pcm]
    open(os.path.join(d, name + "_enc.bin"), "wb").write(b"".join(e))
    np.concatenate([dec(x) for x in e]).astype("<i2").tofile(os.path.join(d, name + "_dec.bin"))
