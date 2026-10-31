"""Mechanical gates (#35): PK-5, PK-11, wall >= 1.6, interference = 0, printable without supports.
Skips cleanly without cadquery / trimesh (/ PrusaSlicer for the slice test)."""
import itertools, os, shutil, subprocess, sys, tempfile
from pathlib import Path
import numpy as np
import pytest

cq = pytest.importorskip("cadquery")
trimesh = pytest.importorskip("trimesh")
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "mech"))
import pack, panel  # noqa: E402

PRUSA = shutil.which("prusa-slicer") or shutil.which("PrusaSlicer") or "/Applications/PrusaSlicer.app/Contents/MacOS/PrusaSlicer"
PETG_G_CC = 1.27


@pytest.fixture(scope="module")
def parts():
    return pack.parts()


def mesh(wp):
    d = tempfile.mkdtemp()
    f = os.path.join(d, "m.stl")
    cq.exporters.export(wp, f, tolerance=0.02, angularTolerance=0.1)
    return trimesh.load(f)


def bb(wp):
    b = wp.val().BoundingBox()
    return b.xmin, b.xmax, b.ymin, b.ymax, b.zmin, b.zmax


def test_interference_zero(parts):
    bad = {}
    for (a, pa), (b, pb) in itertools.combinations(parts.items(), 2):
        v = pa.intersect(pb).val().Volume() if pa.intersect(pb).vals() else 0.0
        if v > 1e-3:
            bad[f"{a}&{b}"] = round(v, 3)
    assert not bad, bad


def test_pk11_envelope(parts):
    xs = [bb(parts[k]) for k in pack.ENCLOSURE]
    dims = (max(b[1] for b in xs) - min(b[0] for b in xs), max(b[3] for b in xs) - min(b[2] for b in xs), max(b[5] for b in xs) - min(b[4] for b in xs))
    print("enclosure outer dims", [round(d, 2) for d in dims])
    assert dims[0] <= 100 and dims[1] <= 65 and dims[2] <= 25, dims


def test_pk5_whip(parts):
    w = parts["whip"].val()
    assert abs((bb(parts["whip"])[5] - pack.Z_TOP - pack.WALL) - pack.WHIP_L) < 1e-6   # 31 mm outside the top face
    assert bb(parts["whip"])[5] > bb(parts["lid"])[5]                                   # exits the top face
    d = w.distance(parts["cell"].val())
    assert d >= 40, d                                                                   # >= 40 mm from the cell


@pytest.mark.parametrize("name", ["base", "lid", "door", "clip"])
def test_min_wall(parts, name):
    m = mesh(parts[name])
    c, n = m.triangles_center, m.face_normals
    ray = m.ray.intersects_location(c - n * 1e-3, -n, multiple_hits=False)
    loc, idx_ray, _ = ray
    t = np.full(len(c), np.inf)
    t[idx_ray] = np.linalg.norm(loc - c[idx_ray], axis=1)
    # faces whose inward ray escapes (open pockets, sliver tris) are skipped; require plenty of coverage
    assert len(idx_ray) > 0.9 * len(c)
    assert t.min() >= pack.WALL - 0.05, (name, t.min())


def printable(m):
    """faces tilted >45 deg past vertical and not on the bed; flat ceilings <= 8 mm span count as bridges"""
    n, c = m.face_normals, m.triangles_center
    zmin = m.bounds[0][2]
    bad = np.where((n[:, 2] < -0.75) & (n[:, 2] > -0.99) & (c[:, 2] > zmin + 0.05))[0]
    flat = np.where((n[:, 2] <= -0.99) & (c[:, 2] > zmin + 0.05))[0]
    # group flat ceilings by height; bridge span = shorter side of the group's bbox
    spans = []
    for z in np.unique(np.round(c[flat, 2], 2)):
        tri = m.triangles[flat][np.round(c[flat, 2], 2) == z].reshape(-1, 3)
        spans.append((tri.max(0) - tri.min(0))[:2].min())
    return len(bad), max(spans, default=0)


@pytest.mark.parametrize("name", ["base", "lid", "door", "clip"])
def test_overhang(parts, name):  # printed as modelled: base floor-down, lid/door inner-face-down, clip arm-down
    m = mesh(parts[name])
    steep, span = printable(m)
    assert steep == 0, f"{name}: {steep} faces overhang > 45 deg"
    assert span <= 8.0, f"{name}: flat ceiling bridge {span:.1f} mm"


def test_panel():
    p = panel.panel()
    b = bb(p)
    assert abs((b[1] - b[0]) - 482.6) < 1e-6 and abs((b[3] - b[2]) - 44.45) < 1e-6
    assert b[5] - b[4] >= pack.WALL
    m = mesh(p)
    assert m.is_watertight


def test_mass_estimate(parts):
    v = sum(parts[k].val().Volume() for k in pack.ENCLOSURE) / 1000
    g = v * PETG_G_CC
    print(f"enclosure solid {v:.1f} cm3 = {g:.1f} g PETG (100% fill upper bound)")
    assert g < 80


@pytest.mark.skipif(not os.path.exists(PRUSA), reason="PrusaSlicer not installed")
@pytest.mark.parametrize("name", ["base", "lid", "door", "clip"])
def test_prusaslicer_no_supports(parts, name, tmp_path):
    stl = tmp_path / f"{name}.stl"
    cq.exporters.export(parts[name], str(stl), tolerance=0.02, angularTolerance=0.1)
    gc = tmp_path / f"{name}.gcode"
    r = subprocess.run([PRUSA, "--export-gcode", "--center", "100,100", "--support-material", "--support-material-auto",
                        "--support-material-threshold", "45", "--output", str(gc), str(stl)], capture_output=True, text=True, timeout=300)
    assert r.returncode == 0 and gc.exists(), r.stderr[-500:] + r.stdout[-500:]
    assert ";TYPE:Support material" not in gc.read_text(), f"{name} needs supports"
