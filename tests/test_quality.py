import os, sys
import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "sim"))
quality = pytest.importorskip("quality")


@pytest.mark.skipif(not quality.have_visqol(), reason="visqol binary not built")
def test_visqol_identical_high():
    t = np.arange(48000 * 3) / 48000
    x = (0.3 * np.sin(2 * np.pi * 440 * t) * np.sin(2 * np.pi * 3 * t) + np.random.default_rng(0).normal(0, .01, t.size))
    assert quality.visqol(x, x) > 4.0


def test_pesq_identical_high():
    pytest.importorskip("pesq")
    t = np.arange(48000 * 3) / 48000
    x = 0.3 * np.sin(2 * np.pi * 300 * t) * (1 + np.sin(2 * np.pi * 4 * t))
    assert quality.pesq_wb(x, x) > 4.0
