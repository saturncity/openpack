"""Rack chassis (#34, mech/rack.py) with CadQuery solids: the same boxes as the box-model check, intersected pairwise
(volume, not bounding boxes), plus the drilled rear panel against the connector bodies. Skips without cadquery outside
CI (ci.yml's check job installs it, so there a missing cadquery is a failure)."""
import importlib.util, os
from pathlib import Path

import pytest

if os.environ.get("CI"):
    import cadquery as cq  # noqa: F401
else:
    cq = pytest.importorskip("cadquery")
ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("mech_rack_cq", ROOT / "mech" / "rack.py")
rack = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rack)


def _vol(a, b):
    i = a.intersect(b)
    return i.val().Volume() if i.vals() else 0.0


def test_no_solid_interference():
    m = rack.load()
    S = rack.solids(m)
    parts = rack.cadquery_solids(m)
    bad = []
    for i, (na, _, ga) in enumerate(S):
        for nb, _, gb in S[i + 1:]:
            if (ga, gb) in rack.ALLOWED or (gb, ga) in rack.ALLOWED:
                continue
            v = _vol(parts[na], parts[nb])
            if v > 1e-3:
                bad.append((na, nb, round(v, 3)))
    assert not bad, bad[:10]


def test_rear_panel_drilled_and_clear():
    parts = rack.cadquery_solids()
    panel = parts["rear_panel"]
    W, H, t = rack.CASE["in_w"], rack.CASE["in_h"], rack.CASE["panel_t"]
    assert panel.val().Volume() < W * H * t * 0.9          # the cut-outs are really there
