"""Receiver sub-board PCB (#34): DRC clean against the JLCPCB rules (and the rules really load), fab outputs made from
the committed board, board pads match the netlist, current paths wide and on outer copper, RF line at the computed
50 ohm width, digital nets kept out of the analog region, JLC BOM/CPL complete. Needs kicad-cli (KiCad 10) for the DRC
and gerber checks; skips those without it. Regenerate with `python3 hw/rx/layout_rx.py` (system python with pcbnew)."""
import csv, hashlib, importlib.util, json, math, pathlib, re, shutil, subprocess

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
RX = ROOT / "hw" / "rx"
FAB = RX / "out" / "fab"
KICAD = shutil.which("kicad-cli")
needs_kicad = pytest.mark.skipif(KICAD is None, reason="kicad-cli (KiCad 10) not installed")


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def lay():
    return _load("hw_rx_layout_t", RX / "layout_rx.py")


@pytest.fixture(scope="module")
def outp():
    return _load("hw_rx_outputs_t", RX / "outputs_rx.py")


def _copy_board(tmp, dru_extra=""):
    for name in ("rx.kicad_pcb", "rx.kicad_pro"):
        shutil.copy(RX / name, tmp / name)
    (tmp / "rx.kicad_dru").write_text((RX / "rx.kicad_dru").read_text() + dru_extra)
    return tmp / "rx.kicad_pcb"


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
    assert not errors, [(v["type"], v["description"]) for v in errors]
    assert not rep["unconnected_items"]


@needs_kicad
def test_saved_fill_is_the_drc_fill(tmp_path):
    """the committed zone fill (what the gerbers carry) already has the 0.25 mm RF gap: DRC without a refill is clean"""
    rep = _drc(_copy_board(tmp_path), refill=False)
    assert not [v for v in rep["violations"] if v["severity"] == "error"]


@needs_kicad
def test_dru_rules_are_loaded(tmp_path):
    """KiCad drops the whole .kicad_dru silently on one bad rule (the pack's min_resolved_spokes did): a probe rule
    appended to the file must fire"""
    rep = _drc(_copy_board(tmp_path, '\n(rule "probe"\n  (constraint track_width (min 5mm)))\n'), refill=False)
    assert any(v["type"] == "track_width" for v in rep["violations"])


def test_fab_outputs_match_board():
    man = json.loads((FAB / "manifest.json").read_text())
    assert man["board_sha256"] == hashlib.sha256((RX / "rx.kicad_pcb").read_bytes()).hexdigest(), \
        "rx.kicad_pcb changed after the fab outputs were made: run python3 hw/rx/outputs_rx.py"
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
    """(ref, pad) -> net name from the committed board"""
    root = lay.pk.sexp((RX / "rx.kicad_pcb").read_text())
    out = {}
    for fp in lay.pk._find(root, "footprint"):
        ref = next(p[2] for p in lay.pk._find(fp, "property") if p[1] == "Reference")
        for pad in lay.pk._find(fp, "pad"):
            net = lay.pk._find(pad, "net")
            out.setdefault((ref, pad[1]), set()).add(net[0][-1] if net else "")
    return out


def test_board_matches_netlist(lay):
    """netlist-vs-pads parity (#104 review S4): every netlist node is on its pad, and no pad carries a net the netlist
    does not give it (kicad-cli's --schematic-parity has no schematic to compare here)"""
    comps, nets = lay.read_netlist()
    pads = _board_pads(lay)
    refs = {r for r, _ in pads} - set(lay.MOUNT)
    assert refs == set(comps), refs ^ set(comps)
    want = {}
    for name, nodes in nets.items():
        for ref, pin in nodes:
            want[(ref, pin)] = name
    for key, name in want.items():
        assert pads.get(key) == {name}, (key, name, pads.get(key))
    stray = {k: v for k, v in pads.items() if k not in want and v - {""} and k[0] not in lay.MOUNT}
    assert not stray, stray


def test_rf_gcpw_50_ohm(lay):
    rf = lay.rf_line
    assert (lay.RF_W, lay.RF_GAP) == (0.31, 0.25)
    # raw bare-copper solve (no calibration, #116 review N1): within 2 ohm of 50, and 50 +-1 with the solder mask
    assert abs(rf.z0(lay.RF_W, lay.RF_GAP) - 50.0) < 2.0 and abs(rf.Z_MASKED_REVIEW - 50.0) < 1.0
    # the solver's microstrip check sits within 3 % of Hammerstad-Jensen (the pack's 0.346 mm line)
    assert abs(rf.RESULTS[(0.346, None)][0] - lay.pk.microstrip_z0(0.346)[0]) < 0.03 * 50
    # monotonic in w around the chosen width
    assert rf.z0(0.30, 0.25) > rf.z0(0.31, 0.25) > rf.z0(0.32, 0.25)
    assert "0.31mm" in (RX / "rx.kicad_dru").read_text()
    pro = json.loads((RX / "rx.kicad_pro").read_text())
    rf = next(c for c in pro["net_settings"]["classes"] if c["name"] == "RF_50R")
    assert rf["clearance"] == lay.RF_GAP and rf["track_width"] == lay.RF_W
    segs = [s for s in lay.segments() if s[0] in lay.RF_NETS]
    assert {s[0] for s in segs} == set(lay.RF_NETS)
    assert all(s[1] == "F.Cu" and s[2] == lay.RF_W for s in segs), segs
    assert sum(s[3] for s in segs) < 25.0          # J3/J4 -> switch -> J5 is short


def test_rf_solver_reproduces_record(lay):
    """re-run the field solve for the chosen line when numpy/scipy exist (the .ws venv; KiCad's python has neither)"""
    pytest.importorskip("numpy")
    pytest.importorskip("scipy")
    z, _ = lay.rf_line.solve(lay.RF_W, lay.RF_GAP)
    assert z == pytest.approx(lay.rf_line.RESULTS[(lay.RF_W, lay.RF_GAP)][0], abs=0.05)


def test_current_paths_outer_and_wide(lay):
    """#104 review M1 lesson: rails, relay coil and audio output legs on 35 um outer copper at 0.5 mm; 0.3 mm necks
    only next to small pads (<= 2 mm each); 0.2 mm only for the no-current logic ties (LOGIC_TIES, +3V3)"""
    segs = [s for s in lay.segments() if s[0] in lay.WIDE_NETS]
    assert {s[0] for s in segs} == set(lay.WIDE_NETS)
    assert not [s for s in segs if s[1] not in ("F.Cu", "B.Cu")]
    necks = [s for s in segs if s[2] < lay.WIDE_W]
    assert all(s[2] >= lay.NECK_W - 1e-6 or s[0] == "+3V3" for s in necks), necks
    assert all(s[3] <= 2.0 for s in necks if s[2] >= lay.NECK_W - 1e-6), [s for s in necks if s[3] > 2.0]
    # logic ties (PCM5102A FLT, PE4259 VDD 9 uA + its 100 nF): microamps, so length is not a current question
    assert sum(s[3] for s in necks if s[2] < lay.NECK_W - 1e-6) <= 20.0
    for n in lay.WIDE_NETS:
        tot = sum(s[3] for s in segs if s[0] == n)
        wide = sum(s[3] for s in segs if s[0] == n and s[2] >= lay.WIDE_W)
        assert wide >= 0.6 * tot, (n, wide, tot)


def test_noisy_nets_outside_analog_region(lay):
    """no digital/switching track (or via) crosses the analog region on any layer"""
    txt = (RX / "rx.kicad_pcb").read_text()
    seg = re.compile(r'\(segment\s+\(start ([-\d.]+) ([-\d.]+)\)\s+\(end ([-\d.]+) ([-\d.]+)\)\s+\(width [\d.]+\)\s+'
                     r'\(layer "[^"]+"\)\s+\(net "([^"]*)"\)')

    def inside(x, y):
        return any(r[0] < x < r[2] and r[1] < y < r[3] for r in lay.ANALOG_RECTS)
    bad = []
    for m in seg.finditer(txt):
        x0, y0, x1, y1 = (float(v) for v in m.groups()[:4])
        if m[5] not in lay.NOISY_NETS:
            continue
        for k in range(11):
            x, y = x0 + (x1 - x0) * k / 10 - lay.OX, lay.OY - (y0 + (y1 - y0) * k / 10)
            if inside(x, y):
                bad.append((m[5], round(x, 2), round(y, 2)))
                break
    assert not bad, bad


def test_jlc_bom_has_lcsc_or_dnp(outp):
    rows = list(csv.DictReader(open(FAB / "bom_jlc.csv")))
    bom = list(csv.DictReader(open(RX / "out" / "bom.csv")))
    refs = {r for b in bom for r in b["refs"].split() if r != "-"}
    listed = {d for r in rows for d in r["Designator"].split(",")}
    assert listed == refs, listed ^ refs
    bad = [r for r in rows if not (re.fullmatch(r"C\d+", r["LCSC Part #"]) or r["LCSC Part #"] in ("DNP", "CONSIGN"))]
    assert not bad, bad
    assert all(r["LCSC source"] for r in rows)
    # every LCSC code was read from its LCSC/JLC record; only the module is consigned
    assert all(r["LCSC source"].startswith("LCSC/JLC record") for r in rows if re.fullmatch(r"C\d+", r["LCSC Part #"]))
    assert {d for r in rows if r["LCSC Part #"] == "CONSIGN" for d in r["Designator"].split(",")} == {"U1"}
    cpl = {r["Designator"] for r in csv.DictReader(open(FAB / "cpl_jlc.csv"))}
    dnp = {d for r in rows if r["LCSC Part #"] == "DNP" for d in r["Designator"].split(",")}
    assert not dnp & cpl
    assert {"R33", "R34", "R35", "J1", "C47", "C48"} <= dnp
    placed = refs - dnp
    assert placed == cpl, placed ^ cpl


def test_cpl_rotations_corrected(outp, lay):
    """CPL rotation = KiCad rotation + the JLC correction for that package (SOT-23* +180, SOIC +270)"""
    cpl = {r["Designator"]: float(r["Rotation"]) for r in csv.DictReader(open(FAB / "cpl_jlc.csv"))}
    assert cpl["U6"] == (lay.PLACE["U6"][2] + 270) % 360          # SOIC-8
    assert cpl["Q1"] == (lay.PLACE["Q1"][2] + 180) % 360          # SOT-23
    assert cpl["U7"] == (lay.PLACE["U7"][2] + 180) % 360          # SOT-23-6
    assert cpl["R40"] == lay.PLACE["R40"][2] % 360                # passives unchanged


def test_mech_record(lay):
    """the outline and connector positions #33 needs, written next to the gerbers"""
    m = json.loads((FAB / "mech.json").read_text())
    assert tuple(m["board"]) == (lay.BW, lay.BH) and tuple(m["j1_pin1"]) == lay.J1_PIN1
    assert 8 * m["slot_pitch_min"] <= 425 and m["slot_pitch_min"] >= lay.BW + 4
    # tallest part from its datasheet (C47/C48 UEP1J470MPD, 16 + 1.5 mm) stacked on the 11 mm header + 1.6 mm board;
    # 1U leaves about 35 mm above the main board (44.45 - 2 x 1.2 sheet - 5 standoff - 1.6 board)
    assert m["top_max_height"] >= 17.5
    assert m["above_main_board"] == pytest.approx(m["header_stack"] + m["thickness"] + m["top_max_height"])
    assert m["above_main_board"] <= 35.0
    txt = (RX / "rx.kicad_pcb").read_text()
    assert '(layer "B.Cu")' in txt.split('"openpack:PinHeader_2x13_P2.54mm_Key14"')[1][:400]


PROBE_GAPS = ('\n(rule "probe gap"\n  (constraint clearance (min 0.125mm)))\n'
              '(rule "probe audio gap"\n  (condition "A.NetClass == \'Audio_I\' || B.NetClass == \'Audio_I\'")\n'
              '  (constraint clearance (min 0.15mm)))\n')


@needs_kicad
def test_pour_gaps_per_class(tmp_path):
    """#116 review M1: on the committed (filled) copper, every gap is >= 0.125 mm and every gap to an audio/phantom net
    >= 0.15 mm (IPC-2221 B4, coated, 31-100 V: 0.13). Probe rules appended last override the file's own, and DRC runs
    without a refill, so it measures the fill the gerbers carry. A 0.16 mm probe must fire (the probe is live)."""
    rep = _drc(_copy_board(tmp_path, PROBE_GAPS), refill=False)
    bad = [(v["description"], [i["description"][:50] for i in v["items"]]) for v in rep["violations"] if v["type"] == "clearance"]
    assert not bad, bad[:10]
    rep = _drc(_copy_board(tmp_path, '\n(rule "live"\n  (constraint clearance (min 0.16mm)))\n'), refill=False)
    assert any(v["type"] == "clearance" for v in rep["violations"])


def test_j1_key_has_no_hole_at_14(lay):
    """#116 review S1: J1 has no pad (no hole) at 14, so a full 26-pin header cannot be fitted; the header and the keyed
    main-board socket are real part numbers"""
    pads = _board_pads(lay)
    j1 = {num for ref, num in pads if ref == "J1"}
    assert len(j1) == 25 and "14" not in j1
    assert '(pad "14"' not in (RX / "openpack.pretty" / "PinHeader_2x13_P2.54mm_Key14.kicad_mod").read_text()
    bom = {r["refs"]: r for r in csv.DictReader(open(RX / "out" / "bom.csv"))}
    assert bom["J1"]["mpn"] == "PZ254V-12-26P"
    assert "C22465887" in open(FAB / "bom_jlc.csv").read()
    # #34: the keyed socket is the BOOMELE C64320 with contact 14 pulled (ADR-0014 / ADR-0018 amended), and the
    # rack footprint has no hole at 14 either (tests/test_rack_layout.py)
    assert "C64320" in (ROOT / "docs" / "adr" / "0014-rx-backplane-connector.md").read_text()
    assert "contact 14 pulled" in (ROOT / "docs" / "adr" / "0018-rack-backplane-rf-and-host.md").read_text()


def test_rf_ground_pads_solid(lay):
    """#116 review S2: GND pads of the u.FLs, the PE4259 and the BT40E connect to the pours solidly (zone_connect 2);
    other GND pads keep thermal relief"""
    root = lay.pk.sexp((RX / "rx.kicad_pcb").read_text())
    solid, thermal = set(), set()
    for fp in lay.pk._find(root, "footprint"):
        ref = next(p[2] for p in lay.pk._find(fp, "property") if p[1] == "Reference")
        for pad in lay.pk._find(fp, "pad"):
            net = lay.pk._find(pad, "net")
            if not net or net[0][-1] != "GND":
                continue
            zc = lay.pk._find(pad, "zone_connect")
            (solid if zc and zc[0][1] == "2" else thermal).add((ref, pad[1]))
    for ref in lay.RF_SOLID_GND:
        assert any(r == ref for r, _ in solid), ref
        assert not any(r == ref for r, _ in thermal), (ref, [k for k in thermal if k[0] == ref])
    assert {r for r, _ in solid} >= set(lay.RF_SOLID_GND)       # (+ the LDO exposed pads, solid in KiCad's library)
    assert len(thermal) > 30


POLARIZED = ["K1", "D1", "D2", "D3", "D4", "D5", "D6", "D7", "D8", "D9", "D10", "Q1", "C7", "C9", "C40", "C43", "C49",
             "U1", "U2", "U3", "U4", "U5", "U6", "U7"]


def test_polarized_parts_pin1_marker_and_cpl(lay, outp):
    """#116 review S3: every polarized part (relay, diodes, electrolytics, ICs) has a silkscreen marker on its pin-1 side
    (silk reaches further out past pad 1 than past the pad farthest from it, in footprint coordinates), and its CPL rotation is the board rotation
    plus the JLC correction for its package (K1 included: TQ2SA +270)"""
    root = lay.pk.sexp((RX / "rx.kicad_pcb").read_text())
    F = lay.pk._find
    cpl = {r["Designator"]: float(r["Rotation"]) for r in csv.DictReader(open(FAB / "cpl_jlc.csv"))}

    def pts(item):
        out = []
        for key in ("start", "end", "center", "mid", "at"):
            for e in F(item, key):
                out.append((float(e[1]), float(e[2])))
        for p_ in F(item, "pts"):
            out += [(float(x[1]), float(x[2])) for x in F(p_, "xy")]
        return out
    for fp in F(root, "footprint"):
        ref = next(p[2] for p in F(fp, "property") if p[1] == "Reference")
        if ref not in POLARIZED:
            continue
        pads = {p[1]: (float(F(p, "at")[0][1]), float(F(p, "at")[0][2])) for p in F(fp, "pad")}
        p1 = pads["1"]
        far = max(pads.values(), key=lambda q: math.dist(q, p1))
        silk = [q for kind in ("fp_line", "fp_circle", "fp_poly", "fp_rect", "fp_arc")
                for it in F(fp, kind) if F(it, "layer") and F(it, "layer")[0][1] in ("F.SilkS", "F.Silkscreen") for q in pts(it)]
        silk += [q for t in F(fp, "fp_text") if F(t, "layer")[0][1] in ("F.SilkS", "F.Silkscreen") and t[2] == "+" for q in pts(t)]
        assert silk, ref
        marks = [q for it in F(fp, "fp_poly") if F(it, "layer")[0][1] in ("F.SilkS", "F.Silkscreen") for q in pts(it)]
        if marks:
            # KiCad's filled pin-1 triangle (SOT, SOIC, TSSOP, HVSSOP): nearer pad 1 than the far pad
            assert min(math.dist(q, p1) for q in marks) < min(math.dist(q, far) for q in marks), ref
        else:
            # cathode bar, "+", relay/module dot: the silk reaches further out past pad 1 than past the far pad
            c = ((p1[0] + far[0]) / 2, (p1[1] + far[1]) / 2)
            L = math.dist(p1, far)
            u = ((p1[0] - far[0]) / L, (p1[1] - far[1]) / L)
            proj = [(q[0] - c[0]) * u[0] + (q[1] - c[1]) * u[1] for q in silk]
            assert max(proj) > -min(proj) + 0.05, (ref, round(max(proj), 2), round(-min(proj), 2))
        fpname = F(fp, "footprint")[0][1] if F(fp, "footprint") else fp[1]
        fpname = fpname.split(":")[-1]
        assert cpl[ref] == outp.jlc_rot(fpname, lay.PLACE[ref][2]), (ref, fpname, cpl[ref])
    assert cpl["K1"] == (lay.PLACE["K1"][2] + 270) % 360
