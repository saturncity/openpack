"""Pack PCB (#34): DRC clean against the JLCPCB rules, fab outputs made from the committed board, board matches
the netlist, board + parts clear the enclosure. Needs kicad-cli (KiCad 10) for the DRC and gerber checks; skips
those without it. Regenerate everything with `python3 hw/pack/layout.py` (system python with pcbnew)."""
import hashlib, json, pathlib, shutil, subprocess, sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
PACK = ROOT / "hw" / "pack"
FAB = PACK / "out" / "fab"
sys.path.insert(0, str(PACK))

KICAD = shutil.which("kicad-cli")
needs_kicad = pytest.mark.skipif(KICAD is None, reason="kicad-cli (KiCad 10) not installed")


def _copy_board(tmp):
    for name in ("pack.kicad_pcb", "pack.kicad_pro", "pack.kicad_dru"):
        shutil.copy(PACK / name, tmp / name)
    return tmp / "pack.kicad_pcb"


@needs_kicad
def test_drc_zero_errors(tmp_path):
    board = _copy_board(tmp_path)
    out = tmp_path / "drc.json"
    subprocess.run([KICAD, "pcb", "drc", "--format", "json", "--severity-all", "--refill-zones", "-o", str(out), str(board)],
                   check=True, capture_output=True)
    rep = json.loads(out.read_text())
    errors = [v for v in rep["violations"] if v["severity"] == "error"]
    print(f"DRC: {len(errors)} errors, {len(rep['violations']) - len(errors)} warnings, "
          f"{len(rep['unconnected_items'])} unconnected")
    assert not errors, [(v["type"], v["description"]) for v in errors]
    assert not rep["unconnected_items"]


def test_fab_outputs_match_board():
    man = json.loads((FAB / "manifest.json").read_text())
    assert man["board_sha256"] == hashlib.sha256((PACK / "pack.kicad_pcb").read_bytes()).hexdigest(), \
        "pack.kicad_pcb changed after the fab outputs were made: run python3 hw/pack/outputs.py"
    for rel, h in man["files"].items():
        assert hashlib.sha256((FAB / rel).read_bytes()).hexdigest() == h, f"{rel} edited after export"


def _strip(p):
    # drop the creation-date comments kicad-cli writes into every gerber/drill file
    return [l for l in p.read_text().splitlines() if not l.startswith(("G04", ";", "%TF.CreationDate"))]


@needs_kicad
def test_gerbers_regenerate_identically(tmp_path):
    board = _copy_board(tmp_path)
    import outputs
    g = tmp_path / "g"
    g.mkdir()
    subprocess.run([KICAD, "pcb", "export", "gerbers", "--layers", outputs.GERBER_LAYERS, "--no-x2", "--use-drill-file-origin",
                    "--subtract-soldermask", "-o", str(g) + "/", str(board)], check=True, capture_output=True)
    subprocess.run([KICAD, "pcb", "export", "drill", "--format", "excellon", "--excellon-separate-th", "-o", str(g) + "/", str(board)],
                   check=True, capture_output=True)
    for f in sorted(g.iterdir()):
        if f.suffix in (".gbrjob",):
            continue
        assert _strip(f) == _strip(FAB / "gerber" / f.name), f"stale {f.name}"


def test_board_matches_netlist():
    import layout
    comps, nets = layout.read_netlist()
    txt = (PACK / "pack.kicad_pcb").read_text()
    refs = set()
    for line in txt.splitlines():
        line = line.strip()
        if line.startswith('(property "Reference"'):
            refs.add(line.split('"')[3])
    assert refs == set(comps), (set(comps) ^ refs)
    assert set(layout.PLACE) == set(comps)


def test_fit_in_enclosure():
    import fit
    res, _, _ = fit.checks()
    print({k: v for k, v in res.items() if not isinstance(v, dict)})
    assert not res["fail"], res["fail"]


def test_rf_50_ohm_width():
    import layout
    w = layout.width_for(50.0)
    z, _ = layout.microstrip_z0(w)
    assert 0.30 < w < 0.40 and abs(z - 50.0) < 0.1
    assert "0.346mm" in (PACK / "pack.kicad_dru").read_text()
    assert abs(w - 0.346) < 0.0015
