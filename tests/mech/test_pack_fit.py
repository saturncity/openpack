"""Pack PCB (#34) against the CadQuery enclosure: the board STEP from kicad-cli (hw/pack/out/fab/pack.step) and the
per-part envelope boxes (out/fab/envelope.json: courtyard x datasheet height) must not intersect the printed body,
the holder or the cell. Skips without cadquery outside CI. hw/pack/fit.py runs the same check without CadQuery."""
import json, os, sys
from pathlib import Path

import pytest

# CI installs cadquery (ci.yml check job): there a missing cadquery is a failure, not a skip
if os.environ.get("CI"):
    import cadquery as cq
else:
    cq = pytest.importorskip("cadquery")
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "mech"))
import pack  # noqa: E402

FAB = ROOT / "hw" / "pack" / "out" / "fab"
USB4105_BODY = (8.94, 3.26)   # GCT USB4105 shell width x height


def box(x0, x1, y0, y1, z0, z1):
    return cq.Workplane("XY").box(x1 - x0, y1 - y0, z1 - z0, centered=False).translate((x0, y0, z0))


@pytest.fixture(scope="module")
def solids():
    ps = pack.parts()
    return {k: ps[k] for k in ("base", "lid", "door", "holder", "cell")}


def _vol(a, b):
    i = a.intersect(b)
    return i.val().Volume() if i.vals() else 0.0


def test_board_step_clear(solids):
    board = cq.importers.importStep(str(FAB / "pack.step")).translate((-100.0, 100.0, pack.PCB["z0"]))
    bb = board.val().BoundingBox()
    assert abs(bb.xmin - pack.PCB["x0"]) < 0.05 and abs(bb.xmax - pack.PCB["x1"]) < 0.05, (bb.xmin, bb.xmax)
    bad = {k: round(_vol(board, s), 3) for k, s in solids.items() if _vol(board, s) > 1e-3}
    assert not bad, bad


def test_parts_clear(solids):
    top = pack.PCB["z0"] + pack.PCB["t"]
    inner_x = pack.L / 2 - pack.WALL
    bad = {}
    for e in json.loads((FAB / "envelope.json").read_text()):
        if e["h"] <= 0:
            continue
        x0, x1, y0, y1, h = e["x0"], e["x1"], e["y0"], e["y1"], e["h"]
        if e["ref"] == "J2":    # receptacle shell runs into the wall opening; the courtyard also covers the shield tabs
            w, hh = USB4105_BODY
            y0, y1, h = pack.USB_Y - w / 2, pack.USB_Y + w / 2, hh
        if e["ref"] == "J1":    # bushing passes through the teardrop hole; check the body inside the wall
            x1 = min(x1, inner_x)
        b = box(x0, x1, y0, y1, top, top + h)
        for k, s in solids.items():
            v = _vol(b, s)
            if v > 1e-3:
                bad[f"{e['ref']}&{k}"] = round(v, 3)
    assert not bad, bad
