import os, sys
import numpy as np

ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, os.path.join(ROOT, "sim", "codec"))
import codec

G = os.path.join(ROOT, "sim", "codec", "golden")


def test_selfcheck():
    codec.selfcheck()


def test_golden_vectors_match():
    pcm = np.fromfile(os.path.join(G, "pcm_in.bin"), "<i2").reshape(-1, codec.N)
    for name, (enc, dec) in codec.CODECS.items():
        want = open(os.path.join(G, name + "_enc.bin"), "rb").read()
        sz = codec.FRAME_BYTES[name]
        e = [enc(f) for f in pcm]
        assert b"".join(e) == want, name
        want_dec = np.fromfile(os.path.join(G, name + "_dec.bin"), "<i2")
        assert (np.concatenate([dec(x) for x in e]) == want_dec).all(), name
        assert len(want) == sz * len(pcm)
