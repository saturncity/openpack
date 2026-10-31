"""Audio quality metrics. visqol(ref, deg, fs) -> MOS-LQO (audio mode, 48 kHz); pesq_wb(ref, deg, fs) -> PESQ WB MOS.

ViSQOL is google/visqol v3.3.3 built with bazel (see sim/codec/RESULTS.md); binary found via $VISQOL_BIN or
sim/.cache/visqol_src/bazel-bin/visqol. Inputs: 1-D numpy arrays (int16 or float in [-1, 1]) at fs.
"""
import os, re, subprocess, tempfile
import numpy as np
from scipy.io import wavfile
from scipy.signal import resample_poly

_HERE = os.path.dirname(os.path.abspath(__file__))
VISQOL_BIN = os.environ.get("VISQOL_BIN", os.path.join(_HERE, ".cache", "visqol_src", "bazel-bin", "visqol"))


def have_visqol():
    return os.path.exists(VISQOL_BIN)


def _f(x):
    x = np.asarray(x)
    return x.astype(np.float64) / 32768 if x.dtype.kind == "i" else x.astype(np.float64)


def visqol(ref, deg, fs=48000):
    assert fs == 48000, "audio mode needs 48 kHz"
    with tempfile.TemporaryDirectory() as d:
        p = []
        for n, x in (("r", ref), ("d", deg)):
            p.append(f"{d}/{n}.wav")
            wavfile.write(p[-1], fs, np.round(np.clip(_f(x), -1, 1) * 32767).astype(np.int16))  # 16-bit file I/O
        out = subprocess.run([VISQOL_BIN, "--reference_file", p[0], "--degraded_file", p[1]],
                             capture_output=True, text=True, check=True).stdout
    return float(re.search(r"MOS-LQO:\s*([\d.]+)", out).group(1))


def pesq_wb(ref, deg, fs=48000):
    from pesq import pesq
    r, d = (resample_poly(_f(x), 16000, fs) for x in (ref, deg))
    return float(pesq(16000, r, d, "wb"))
