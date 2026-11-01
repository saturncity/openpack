"""Mechanical gates (#35): PK-5, PK-11, wall >= 1.6, interference = 0, printable on a 180 x 180 mm PETG bed without supports.
Skips cleanly without cadquery / trimesh (/ PrusaSlicer for the slice tests)."""
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
# Bambu A1 mini: 180^3 bed, 0.4 mm nozzle, PETG on textured PEI
SLICER = ["--bed-shape", "0x0,180x0,180x180,0x180", "--max-print-height", "180", "--nozzle-diameter", "0.4", "--filament-type", "PETG",
          "--temperature", "250", "--first-layer-temperature", "250", "--bed-temperature", "70", "--first-layer-bed-temperature", "70",
          "--support-material", "--support-material-auto", "--support-material-threshold", "45", "--center", "90,90"]


def rot(wp, axis, deg):
    return wp.rotate((0, 0, 0), axis, deg)


def printable_parts():
    """name -> part in PRINT orientation (z up, lowest face on the bed)"""
    d = {k: v for k, v in pack.parts().items() if k in pack.PRINTED}
    d["door"] = rot(d["door"], (1, 0, 0), 180)    # door prints outer-face-down, snap arms up
    d["clip"] = rot(d["clip"], (1, 0, 0), 90)     # clip prints on its side: layers run along the spring arm
    d["lid"] = rot(d["lid"], (1, 0, 0), 180)      # lid prints outer-face-down: light-pipe chimneys point up
    d["switch_ext"] = rot(d["switch_ext"], (1, 0, 0), 90)   # switch fork prints lying on its flat side
    d.update({f"panel_{k}": v for k, v in panel.parts().items()})
    return d


@pytest.fixture(scope="module")
def parts():
    return pack.parts()


def mesh(wp):
    f = os.path.join(tempfile.mkdtemp(), "m.stl")
    cq.exporters.export(wp, f, tolerance=0.02, angularTolerance=0.1)
    return trimesh.load(f)


def bb(wp):
    b = wp.val().BoundingBox()
    return b.xmin, b.xmax, b.ymin, b.ymax, b.zmin, b.zmax


def test_interference_zero(parts):
    bad = {}
    for (a, pa), (b, pb) in itertools.combinations(parts.items(), 2):
        i = pa.intersect(pb)
        v = i.val().Volume() if i.vals() else 0.0
        if v > 1e-3:
            bad[f"{a}&{b}"] = round(v, 3)
    assert not bad, bad


def test_panel_interference_zero():
    ps = panel.parts()
    bad = {}
    for (a, pa), (b, pb) in itertools.combinations(ps.items(), 2):
        i = pa.intersect(pb)
        if i.vals() and i.val().Volume() > 1e-3:
            bad[f"{a}&{b}"] = i.val().Volume()
    assert not bad, bad


def test_pk11_envelope(parts):  # body only: the printed clip is excluded
    xs = [bb(parts[k]) for k in pack.ENCLOSURE]
    dims = (max(b[1] for b in xs) - min(b[0] for b in xs), max(b[3] for b in xs) - min(b[2] for b in xs), max(b[5] for b in xs) - min(b[4] for b in xs))
    print("enclosure body dims", [round(d, 2) for d in dims])
    assert dims[0] <= 100 and dims[1] <= 65 and dims[2] <= 25, dims


def test_clip_opening_and_flex(parts):
    c = bb(parts["clip"])
    assert abs(-c[4] - (2 * pack.CLIP_T + pack.CLIP_OPEN)) < 1e-6        # plate + opening + root-thick arm
    assert pack.CLIP_OPEN >= 4.0
    # arm as a cantilever opened by 3 mm: peak strain 3 t d / (2 L^2) must stay under PETG yield (~2.5 %)
    eps = 3 * pack.CLIP_T * 3.0 / (2 * pack.CLIP_ARM ** 2)
    assert eps < 0.025, eps


def test_clip_inserts_wall():  # boss ring around each heat-set insert
    assert (pack.BOSS_D - pack.INSERT_D) / 2 >= pack.WALL


def test_pk5_whip(parts):
    assert abs((bb(parts["whip"])[5] - pack.Z_TOP - pack.WALL) - pack.WHIP_L) < 1e-6   # 31 mm outside the top face
    assert bb(parts["whip"])[5] > bb(parts["lid"])[5]                                   # exits the top face
    d = parts["whip"].val().distance(parts["cell"].val())
    assert d >= 40, d                                                                   # >= 40 mm from the cell


def min_thickness(wp):
    m = mesh(wp)
    c, n = m.triangles_center, m.face_normals
    loc, idx, _ = m.ray.intersects_location(c - n * 1e-3, -n, multiple_hits=False)
    assert len(idx) > 0.9 * len(c)   # faces whose inward ray escapes are skipped
    return np.linalg.norm(loc - c[idx], axis=1).min()


@pytest.mark.parametrize("name", list(pack.PRINTED))
def test_min_wall(parts, name):
    assert min_thickness(parts[name]) >= pack.WALL - 0.05, name


@pytest.mark.parametrize("name", ["seg0", "seg1", "seg2", "strip0"])
def test_panel_min_wall(name):
    assert min_thickness(panel.parts()[name]) >= pack.WALL - 0.05, name


def overhangs(m):
    """faces tilted >45 deg past vertical and not on the bed; flat ceilings <= 8 mm span count as bridges"""
    n, c = m.face_normals, m.triangles_center
    zmin = m.bounds[0][2]
    bad = np.where((n[:, 2] < -0.75) & (n[:, 2] > -0.99) & (c[:, 2] > zmin + 0.05))[0]
    flat = np.where((n[:, 2] <= -0.99) & (c[:, 2] > zmin + 0.05))[0]
    spans = []
    for z in np.unique(np.round(c[flat, 2], 2)):
        tri = m.triangles[flat][np.round(c[flat, 2], 2) == z].reshape(-1, 3)
        spans.append((tri.max(0) - tri.min(0))[:2].min())
    return len(bad), max(spans, default=0)


@pytest.mark.parametrize("name", list(printable_parts()))
def test_overhang_and_bed(name):
    wp = printable_parts()[name]
    b = bb(wp)
    assert max(b[1] - b[0], b[3] - b[2]) <= panel.BED - 2 * panel.BED_MARGIN and b[5] - b[4] <= 180, name   # A1 mini, 5 mm margin
    steep, span = overhangs(mesh(wp))
    assert steep == 0, f"{name}: {steep} faces overhang > 45 deg"
    assert span <= 8.0, f"{name}: flat ceiling bridge {span:.1f} mm"


def test_panel_cutouts():  # inside with >= 3 mm margin, none overlapping, none crossing a seam
    cs = panel.cutouts()
    for n, k, x, y, sz in cs:
        x0, x1, y0, y1 = panel.bbox(k, x, y, sz)
        m = min(x0 + panel.W / 2, panel.W / 2 - x1, y0 + panel.H / 2, panel.H / 2 - y1)
        assert m >= panel.EDGE_MARGIN, (n, m)
        assert not any(x0 < s < x1 for s in panel.SEAMS), (n, "crosses a seam")
    cut = [panel.cutter(k, x, y, sz).val() for _, k, x, y, sz in cs]
    for i, j in itertools.combinations(range(len(cs)), 2):
        v = cq.Workplane().add(cut[i]).intersect(cq.Workplane().add(cut[j]))
        assert not v.vals() or v.val().Volume() < 1e-6, (cs[i][0], cs[j][0])


def test_panel_ears_5mm():
    for s in (panel.segments()[0], panel.segments()[2]):
        assert bb(s)[5] - bb(s)[4] >= 5.0


def test_mass_estimate(parts):
    v = sum(parts[k].val().Volume() for k in pack.PRINTED) / 1000
    g = v * PETG_G_CC
    print(f"printed pack parts solid {v:.1f} cm3 = {g:.1f} g PETG (100% fill upper bound)")
    assert g < 90


@pytest.mark.skipif(not os.path.exists(PRUSA), reason="PrusaSlicer not installed")
@pytest.mark.parametrize("name", list(printable_parts()))
def test_prusaslicer_no_supports(name, tmp_path):
    stl, gc = tmp_path / f"{name}.stl", tmp_path / f"{name}.gcode"
    cq.exporters.export(printable_parts()[name], str(stl), tolerance=0.02, angularTolerance=0.1)
    r = subprocess.run([PRUSA, "--export-gcode", *SLICER, "--output", str(gc), str(stl)], capture_output=True, text=True, timeout=300)
    assert r.returncode == 0 and gc.exists(), r.stderr[-500:] + r.stdout[-500:]
    assert ";TYPE:Support material" not in gc.read_text(), f"{name} needs supports"
