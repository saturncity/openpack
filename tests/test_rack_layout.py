"""Rack main board PCB (#34): DRC clean against the JLC rules (and the rules really load), fab outputs made from the
committed board, pads match the netlist, current paths wide and on outer copper, RF lines at the solved widths with
their pour gap, the Wilkinson trees as routed inside ADR-0018, keyed slots, JLC BOM/CPL complete, chassis fit.
Needs kicad-cli (KiCad 10) for DRC and gerbers and skips those without it. Regenerate with `python3 hw/rack/layout.py`
(system python with pcbnew), then `.ws/.venv/bin/python hw/rack/rf_routed.py` and `python3 mech/rack.py`."""
import csv, hashlib, importlib.util, json, math, pathlib, re, shutil, subprocess

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
RK = ROOT / "hw" / "rack"
FAB = RK / "out" / "fab"
KICAD = shutil.which("kicad-cli")
needs_kicad = pytest.mark.skipif(KICAD is None, reason="kicad-cli (KiCad 10) not installed")


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def lay():
    return _load("hw_rack_layout_t", RK / "layout.py")


@pytest.fixture(scope="module")
def outp():
    return _load("hw_rack_outputs_t", RK / "outputs_rack.py")


def _copy_board(tmp, dru_extra=""):
    for name in ("rack.kicad_pcb", "rack.kicad_pro"):
        shutil.copy(RK / name, tmp / name)
    (tmp / "rack.kicad_dru").write_text((RK / "rack.kicad_dru").read_text() + dru_extra)
    return tmp / "rack.kicad_pcb"


def _drc(board, refill=True):
    out = board.parent / "drc.json"
    args = [KICAD, "pcb", "drc", "--format", "json", "--severity-all", "-o", str(out), str(board)]
    if refill:
        args.insert(-1, "--refill-zones")
    subprocess.run(args, check=True, capture_output=True)
    return json.loads(out.read_text())


@needs_kicad
def test_drc_zero_errors(tmp_path):
    rep = _drc(_copy_board(tmp_path))
    errors = [v for v in rep["violations"] if v["severity"] == "error"]
    print(f"DRC: {len(errors)} errors, {len(rep['violations']) - len(errors)} warnings, {len(rep['unconnected_items'])} unconnected")
    assert not errors, [(v["type"], v["description"]) for v in errors][:20]
    assert not rep["unconnected_items"]


@needs_kicad
def test_saved_fill_is_the_drc_fill(tmp_path):
    """the committed zone fill (what the gerbers carry) already has the RF pour gap: DRC without a refill is clean"""
    rep = _drc(_copy_board(tmp_path), refill=False)
    assert not [v for v in rep["violations"] if v["severity"] == "error"]


@needs_kicad
def test_dru_rules_are_loaded(tmp_path):
    """KiCad drops the whole .kicad_dru silently on one bad rule: a probe rule appended to it must fire"""
    rep = _drc(_copy_board(tmp_path, '\n(rule "probe"\n  (constraint track_width (min 5mm)))\n'), refill=False)
    assert any(v["type"] == "track_width" for v in rep["violations"])


PROBE_GAPS = ('\n(rule "probe gap"\n  (constraint clearance (min 0.125mm)))\n'
              '(rule "probe audio gap"\n  (condition "A.NetClass == \'Audio_I\' || B.NetClass == \'Audio_I\'")\n'
              '  (constraint clearance (min 0.15mm)))\n'
              '(rule "probe rf pour"\n  (condition "(A.NetClass == \'RF\' && B.Type == \'Zone\') || (B.NetClass == \'RF\' && A.Type == \'Zone\')")\n'
              '  (constraint clearance (min 0.49mm)))\n')


@needs_kicad
def test_pour_gaps_per_class(tmp_path):
    """#116 review M1: on the filled copper every gap is >= 0.125 mm, every gap to an audio/phantom net >= 0.15 mm
    and every RF line keeps its 0.5 mm pour gap; a 0.16 mm probe must fire (the probe is live)"""
    rep = _drc(_copy_board(tmp_path, PROBE_GAPS), refill=False)
    bad = [(v["description"], [i["description"][:50] for i in v["items"]]) for v in rep["violations"] if v["type"] == "clearance"]
    assert not bad, bad[:10]
    rep = _drc(_copy_board(tmp_path, '\n(rule "live"\n  (constraint clearance (min 0.16mm)))\n'), refill=False)
    assert any(v["type"] == "clearance" for v in rep["violations"])


def test_fab_outputs_match_board():
    man = json.loads((FAB / "manifest.json").read_text())
    assert man["board_sha256"] == hashlib.sha256((RK / "rack.kicad_pcb").read_bytes()).hexdigest(), \
        "rack.kicad_pcb changed after the fab outputs were made: run python3 hw/rack/outputs_rack.py"
    for rel, h in man["files"].items():
        assert hashlib.sha256((FAB / rel).read_bytes()).hexdigest() == h, f"{rel} edited after export"


def _strip(p):
    return [l for l in p.read_text().splitlines() if not l.startswith(("G04", ";", "%TF.CreationDate"))]


@needs_kicad
def test_gerbers_regenerate_identically(tmp_path, outp):
    board = _copy_board(tmp_path)
    g = tmp_path / "g"
    g.mkdir()
    subprocess.run([KICAD, "pcb", "export", "gerbers", "--layers", outp.GERBER_LAYERS, "--no-x2", "--use-drill-file-origin",
                    "--subtract-soldermask", "-o", str(g) + "/", str(board)], check=True, capture_output=True)
    subprocess.run([KICAD, "pcb", "export", "drill", "--format", "excellon", "--excellon-separate-th", "-o", str(g) + "/", str(board)],
                   check=True, capture_output=True)
    for f in sorted(g.iterdir()):
        if f.suffix != ".gbrjob":
            assert _strip(f) == _strip(FAB / "gerber" / f.name), f"stale {f.name}"


def _board_pads(lay):
    root = lay.pk.sexp((RK / "rack.kicad_pcb").read_text())
    out = {}
    for fp in lay.pk._find(root, "footprint"):
        ref = next(p[2] for p in lay.pk._find(fp, "property") if p[1] == "Reference")
        for pad in lay.pk._find(fp, "pad"):
            net = lay.pk._find(pad, "net")
            out.setdefault((ref, pad[1]), set()).add(net[0][-1] if net else "")
    return out


def test_board_matches_netlist(lay):
    """netlist-vs-pads parity (#104 review S4): every node on its pad, no pad with a net the netlist does not give it"""
    comps, nets = lay.read_netlist()
    pads = _board_pads(lay)
    refs = {r for r, _ in pads if not r.startswith("H")}
    assert refs == set(comps), refs ^ set(comps)
    want = {}
    for name, nodes in nets.items():
        for ref, pin in nodes:
            want[(ref, pin)] = name
    for key, name in want.items():
        assert pads.get(key) == {name}, (key, name, pads.get(key))
    stray = {k: v for k, v in pads.items() if k not in want and v - {""} and not k[0].startswith("H")}
    assert not stray, stray


def test_rf_lines_at_solved_widths(lay):
    """every RF track is one of the solved widths (50 ohm 0.35, 70.7 ohm 0.17) or a short pad stub; the solve record
    is within 1 ohm of the targets; the lambda/4 arms are the computed length"""
    s = lay.RF_SOLVE
    assert abs(s[(lay.W50, lay.RF_GAP)][0] - 50.0) < 1.0 and abs(s[(lay.W70, lay.RF_GAP)][0] - 70.71) < 1.0
    assert lay.LQ == pytest.approx(18.02, abs=0.05)
    geo = json.loads((RK / "out" / "rf_geometry.json").read_text())
    tracks = [t for t in geo["tracks"] if "pts" in t]
    for t in tracks:
        L = sum(math.dist(a, b) for a, b in zip(t["pts"], t["pts"][1:]))
        assert t["w"] in (lay.W50, lay.W70) or L <= 3.0, t
        assert t["layer"] in ("F.Cu", "B.Cu")
    arms = [t for t in tracks if t["w"] == lay.W70 and t["net"].startswith("WK_") and
            sum(math.dist(a, b) for a, b in zip(t["pts"], t["pts"][1:])) > 1.0]
    assert len(arms) == 28
    for t in arms:   # arm copper + 0.2 mm junction stub + 0.8 mm net tie = lambda/4
        L = sum(math.dist(a, b) for a, b in zip(t["pts"], t["pts"][1:]))
        assert L + 0.2 + 0.8 == pytest.approx(lay.LQ, abs=0.02), t["net"]
    segs = [s_ for s_ in lay.segments() if lay.is_rf(s_[0])]
    assert segs and all(w <= 0.36 for _, _, w, _ in segs)


def test_rf_solver_reproduces_record(lay):
    pytest.importorskip("numpy"); pytest.importorskip("scipy")
    rf = _load("rx_rf_line_t", ROOT / "hw" / "rx" / "rf_line.py")
    z, ee = rf.solve(lay.W50, lay.RF_GAP)
    assert z == pytest.approx(lay.RF_SOLVE[(lay.W50, lay.RF_GAP)][0], abs=0.05)


def test_wilkinson_as_routed_meets_adr0018():
    """hw/rack/rf_routed.py (scikit-rf, the drawn copper): isolation and return loss inside ADR-0018's limits at
    nominal and at the er / width tolerance corners; insertion loss as recorded, and audit.py uses it"""
    rec = json.loads((RK / "out" / "rf_routed.json").read_text())
    lim = rec["limits"]
    for key in ("worst", "worst_tolerance"):
        r = rec[key]
        assert r["iso_db"] >= lim["iso_db"], (key, r)
        assert r["rl_in_db"] >= lim["rl_db"] and r["rl_out_db"] >= lim["rl_db"], (key, r)
    assert rec["worst"]["il_db"] <= 14.0
    if importlib.util.find_spec("skrf") and importlib.util.find_spec("numpy"):
        rr = _load("hw_rack_rf_routed_t", RK / "rf_routed.py")
        geo = json.loads((RK / "out" / "rf_geometry.json").read_text())
        assert rr.summary(geo, "A")["il_db"] == pytest.approx(rec["A"]["il_db"], abs=0.01)


def test_current_paths_outer_and_wide(lay):
    """#104 review M1: every power / audio / 12 V entry track on 35 um outer copper; widths at their class
    (necks only beside pads too small for them, <= 2 mm each); the 12 V entry >= 1.5 mm for most of its length"""
    segs = [s for s in lay.segments() if s[0] in lay.WIDE_NETS]
    assert not [s for s in segs if s[1] not in ("F.Cu", "B.Cu")]
    for n in set(s[0] for s in segs):
        tot = sum(s[3] for s in segs if s[0] == n)
        full = lay.BIG_W if n in lay.BIG_NETS else lay.WIDE_W
        wide = sum(s[3] for s in segs if s[0] == n and s[2] >= full - 1e-6)
        assert wide >= 0.6 * tot or tot < 3.0, (n, wide, tot)
        assert all(s[2] >= lay.NECK_W - 1e-6 for s in segs if s[0] == n), n
    pro = json.loads((RK / "rack.kicad_pro").read_text())
    pats = {p["pattern"]: p["netclass"] for p in pro["net_settings"]["netclass_patterns"]}
    assert all(pats.get(n) == "Big" for n in lay.BIG_NETS)
    assert all(pats.get(n) == "Audio_I" for n in lay.AUDIO_NETS)


def test_bus_pours_on_outer_copper(lay):
    """+12V_BUS and +5V (3.5 A / 3 A) are B.Cu pours, CHASSIS a B.Cu strip along the rear panel"""
    txt = (RK / "rack.kicad_pcb").read_text()
    for net in ("+12V_BUS", "+5V", "CHASSIS"):
        m = re.search(r'\(zone\s+\(net "' + re.escape(net) + r'"\)\s+\(net_name "[^"]*"\)\s+\(layer "([^"]+)"\)', txt) or \
            re.search(r'\(zone\s+\(net "' + re.escape(net) + r'"\)\s+\(layer "([^"]+)"\)', txt)
        assert m and m.group(1) == "B.Cu", net


def test_slot_key_and_socket_positions(lay):
    """ADR-0014 key: no pad (no hole) at position 14 on every slot socket, silk 'KEY' on it; socket pins land on the
    receiver's J1 (mech.json) pin for pin"""
    pads = _board_pads(lay)
    for k in range(8):
        j = f"J{10 + k}"
        nums = {num for ref, num in pads if ref == j}
        assert len(nums) == 25 and "14" not in nums
    assert '(pad "14"' not in (RK / "openpack.pretty" / "PinSocket_2x13_P2.54mm_Key14.kicad_mod").read_text()
    root = lay.pk.sexp((RK / "rack.kicad_pcb").read_text())
    for fp in lay.pk._find(root, "footprint"):
        ref = next(p[2] for p in lay.pk._find(fp, "property") if p[1] == "Reference")
        if not re.fullmatch(r"J1\d", ref):
            continue
        k = int(ref[2])
        at = lay.pk._find(fp, "at")[0]
        x0, y0 = float(at[1]), float(at[2])
        rot = math.radians(float(at[3]) if len(at) > 3 else 0.0)
        for pad in lay.pk._find(fp, "pad"):
            n = int(pad[1])
            pa = lay.pk._find(pad, "at")[0]
            px, py = float(pa[1]), float(pa[2])
            gx = x0 + px * math.cos(rot) + py * math.sin(rot)
            gy = y0 - px * math.sin(rot) + py * math.cos(rot)
            want = lay.j1_pin(k, n)
            assert (gx - lay.OX, lay.OY - gy) == pytest.approx(want, abs=0.01), (ref, n)


def test_rf_ground_pads_solid(lay):
    """#116 review S2: GND pads of the u.FLs, BNCs, LNAs and BAW filters join the pours solidly"""
    root = lay.pk.sexp((RK / "rack.kicad_pcb").read_text())
    solid = set()
    for fp in lay.pk._find(root, "footprint"):
        ref = next(p[2] for p in lay.pk._find(fp, "property") if p[1] == "Reference")
        for pad in lay.pk._find(fp, "pad"):
            net = lay.pk._find(pad, "net")
            if net and net[0][-1] == "GND":
                zc = lay.pk._find(pad, "zone_connect")
                if zc and zc[0][1] == "2":
                    solid.add(ref)
    assert set(lay.RF_SOLID_GND) <= solid


def test_test_points_on_every_rail_and_bus(lay):
    """#104 review M2: a test pad on every rail, every slot's rails / UART / reset, SPI1 and the IRQs"""
    comps, nets = lay.read_netlist()
    tp = {nets_name for nets_name, nodes in nets.items() for r, _ in nodes if r.startswith("TP")}
    need = {"+12V_PROT", "+12V_BUS", "+5V", "+3V3", "+12V_HOST", "GND", "BIAS_A_DC", "BIAS_B_DC", "+5V_LNA_A", "+5V_LNA_B",
            "HOST_GPIO6", "HOST_GPIO18", "HOST_GPIO17", "HOST_GPIO19", "HOST_GPIO20", "HOST_GPIO21", "HOST_GPIO24", "HOST_GPIO25"}
    need |= {f"{p}{k}" for k in range(8) for p in ("+12V_S", "+5V_S")}
    need |= {f"S{k}_BP_{s}" for k in range(8) for s in ("UART_TX", "UART_RX", "nRESET")}
    assert need <= tp, need - tp


def test_jlc_bom_has_lcsc_or_dnp(outp):
    rows = list(csv.DictReader(open(FAB / "bom_jlc.csv")))
    bom = list(csv.DictReader(open(RK / "out" / "bom.csv")))
    refs = {r for b in bom for r in b["refs"].split() if r != "-"}
    listed = {d for r in rows for d in r["Designator"].split(",")}
    assert listed == refs, listed ^ refs
    bad = [r for r in rows if not (re.fullmatch(r"C\d+", r["LCSC Part #"]) or r["LCSC Part #"] in ("DNP", "CONSIGN"))]
    assert not bad, bad
    assert all(r["LCSC source"] for r in rows)
    assert all(r["LCSC source"].startswith("LCSC/JLC record") for r in rows if re.fullmatch(r"C\d+", r["LCSC Part #"]))
    cpl = {r["Designator"] for r in csv.DictReader(open(FAB / "cpl_jlc.csv"))}
    dnp = {d for r in rows if r["LCSC Part #"] == "DNP" for d in r["Designator"].split(",")}
    assert not dnp & cpl
    placed = refs - dnp - {r for r in refs if r.startswith("TL")}
    assert placed == cpl, placed ^ cpl


POLARIZED = ["D1", "D2", "C1", "C6", "U1", "U2", "U3", "U4", "U5", "U6", "U7", "U8", "U9", "Q1", "Y1", "Y2"]


def test_cpl_rotations_corrected(outp):
    """CPL rotation = board rotation + the JLC correction for its package; every polarized part is listed with it"""
    cpl = {r["Designator"]: float(r["Rotation"]) for r in csv.DictReader(open(FAB / "cpl_jlc.csv"))}
    pos = {}
    txt = (RK / "rack.kicad_pcb").read_text()
    for m in re.finditer(r'\(footprint "(?:[^":]+:)?([^"]+)"\s.*?\(at [-\d.]+ [-\d.]+(?: ([-\d.]+))?\).*?\(property "Reference" "([^"]+)"', txt, re.S):
        pos[m.group(3)] = (m.group(1), float(m.group(2) or 0))
    for ref in POLARIZED:
        if ref in cpl:
            fpname, rot = pos[ref]
            assert cpl[ref] == outp.jlc_rot(fpname, rot), (ref, fpname, rot, cpl[ref])
    assert outp.jlc_rot("SOIC-8_3.9x4.9mm_P1.27mm", 0) == 270 and outp.jlc_rot("TSSOP-28_4.4x9.7mm_P0.65mm", 90) == 0


def test_mech_record_and_fit():
    """the mechanical record mech/rack.py builds the chassis from, and its interference check"""
    m = json.loads((FAB / "mech.json").read_text())
    assert m["board"][0] <= m["case_inside"][0] - 2 and m["board"][1] <= m["case_inside"][1]
    rx = json.loads((ROOT / "hw" / "rx" / "out" / "fab" / "mech.json").read_text())
    assert m["slot_pitch"] == rx["slot_pitch_min"] and m["sub_above_main"] == rx["above_main_board"]
    rack = _load("mech_rack_t", ROOT / "mech" / "rack.py")
    res, fail = rack.checks(m)
    assert not fail, fail
    assert res["margins"]["lid_over_receivers"] >= 2.0
