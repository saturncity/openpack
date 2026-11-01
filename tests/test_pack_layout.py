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
    assert refs - set(layout.MOUNT) == set(comps), (set(comps) ^ (refs - set(layout.MOUNT)))
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


def test_battery_path_on_l1_wide():
    """#104 review M1: BT1+ -> F1 -> Q1 -> SW1 -> VSYS on L1 (35 um) at >= 1.0 mm; necks (to small pads) only short"""
    import layout
    segs = [x for x in layout.segments() if x[0] in layout.BAT_NETS]
    assert {x[0] for x in segs} == set(layout.BAT_NETS)
    bad_layer = [x for x in segs if x[1] != "F.Cu"]
    assert not bad_layer, bad_layer
    necks = [x for x in segs if x[2] < layout.BAT_W]
    assert all(x[2] >= 0.25 and x[3] <= 1.5 for x in necks), [x for x in necks if x[3] > 1.5 or x[2] < 0.25]
    for n in layout.BAT_NETS:
        tot = sum(x[3] for x in segs if x[0] == n)
        wide = sum(x[3] for x in segs if x[0] == n and x[2] >= layout.BAT_W)
        assert wide >= 0.7 * tot, (n, wide, tot)
    r = layout.battery_path_ohm()
    print(f"battery path tracks {r * 1e3:.1f} mOhm")
    assert r <= 0.05


def test_jlc_bom_has_lcsc_or_dnp():
    import csv, re
    rows = list(csv.DictReader(open(FAB / "bom_jlc.csv")))
    assert rows
    bad = [r for r in rows if not (re.fullmatch(r"C\d+", r["LCSC Part #"]) or r["LCSC Part #"] in ("DNP", "CONSIGN"))]
    assert not bad, bad
    dnp = {d for r in rows if r["LCSC Part #"] == "DNP" for d in r["Designator"].split(",")}
    cpl = list(csv.DictReader(open(FAB / "cpl_jlc.csv")))
    assert not dnp & {r["Designator"] for r in cpl}


def test_jlc_rotation_corrections():
    import outputs
    assert outputs.jlc_rot("SOT-23", 0) == 180 and outputs.jlc_rot("SOT-23-5", 270) == 90
    assert outputs.jlc_rot("WQFN-24-1EP_4x4mm_P0.5mm_EP2.6x2.6mm", 180) == 90
    assert outputs.jlc_rot("SOIC-8_3.9x4.9mm_P1.27mm", 0) == 270 and outputs.jlc_rot("C_0402_1005Metric", 90) == 90
