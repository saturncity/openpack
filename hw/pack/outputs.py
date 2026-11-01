"""Fab outputs and review renders for hw/pack/pack.kicad_pcb, all through kicad-cli (KiCad 10).

    python3 hw/pack/outputs.py            # gerbers, drill, BOM, CPL, STEP, envelope, PNG renders
    python3 hw/pack/outputs.py renders    # renders only

hw/pack/out/fab/: gerbers + Excellon (JLCPCB naming), bom_jlc.csv, cpl_jlc.csv, pack.step, envelope.json,
manifest.json (sha256 of the board each output was made from; tests/test_pack_layout.py checks it).
hw/pack/out/render/: one PNG per copper layer (+ edge, + pads), top/bottom 3D views.
Needs ImageMagick (`magick`) to rasterise kicad-cli's SVGs.
"""
import csv, hashlib, json, pathlib, shutil, subprocess, sys

HERE = pathlib.Path(__file__).resolve().parent
BOARD = HERE / "pack.kicad_pcb"
FAB = HERE / "out" / "fab"
GERBER = FAB / "gerber"
RENDER = HERE / "out" / "render"

LAYERS = {"L1_F.Cu": "F.Cu", "L2_In1.Cu": "In1.Cu", "L3_In2.Cu": "In2.Cu", "L4_B.Cu": "B.Cu"}
GERBER_LAYERS = "F.Cu,In1.Cu,In2.Cu,B.Cu,F.Paste,B.Paste,F.SilkS,B.SilkS,F.Mask,B.Mask,Edge.Cuts"
# component heights above the board top (mm) for the enclosure fit check: datasheet body heights, rounded up
HEIGHT = {"U1": 2.0, "J1": 9.6, "J2": 3.3, "SW1": 3.5, "H1": 0.0, "H2": 0.0, "U3": 1.75, "U2": 0.8, "U4": 0.6, "L1": 1.2, "BT1": 0.0,
          "J3": 0.0, **{f"TP{i}": 0.0 for i in range(1, 12)}, "Q1": 1.1, "D6": 1.1, "U5": 1.45, "U6": 1.45, "U7": 1.45, "F1": 0.9}
HEIGHT_BY_FP = {"C_1206": 1.8, "C_0805": 1.35, "C_0603": 0.95, "C_0402": 0.6, "R_0402": 0.4, "D_0402": 0.6, "LED_0603": 0.8}


def sh(*args):
    r = subprocess.run(list(args), capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"{' '.join(args)}\n{r.stdout}\n{r.stderr}")
    return r.stdout


def board_hash():
    return hashlib.sha256(BOARD.read_bytes()).hexdigest()


def svg_png(svg, png, density=400, width=2200):
    sh("magick", "-density", str(density), str(svg), "-background", "white", "-flatten", "-resize", f"{width}x",
       "-colors", "16", f"PNG8:{png}")
    svg.unlink()


def renders():
    RENDER.mkdir(parents=True, exist_ok=True)
    for name, layer in LAYERS.items():
        svg = RENDER / f"{name}.svg"
        sh("kicad-cli", "pcb", "export", "svg", "--layers", f"{layer},Edge.Cuts", "--mode-single", "--fit-page-to-board",
           "--exclude-drawing-sheet", "-o", str(svg), str(BOARD))
        svg_png(svg, RENDER / f"{name}.png")
    svg = RENDER / "top_assembly.svg"
    sh("kicad-cli", "pcb", "export", "svg", "--layers", "F.Cu,F.SilkS,F.Fab,F.CrtYd,Edge.Cuts", "--mode-single",
       "--fit-page-to-board", "--exclude-drawing-sheet", "-o", str(svg), str(BOARD))
    svg_png(svg, RENDER / "top_assembly.png")
    for side in ("top", "bottom"):
        out = RENDER / f"3d_{side}.png"
        sh("kicad-cli", "pcb", "render", "--side", side, "--width", "1800", "--height", "900", "--quality", "high",
           "--zoom", "1.9", "--background", "opaque", "-o", str(out), str(BOARD))
        sh("magick", str(out), "-colors", "128", f"PNG8:{out}")


def gerbers():
    if GERBER.exists():
        shutil.rmtree(GERBER)
    GERBER.mkdir(parents=True)
    sh("kicad-cli", "pcb", "export", "gerbers", "--layers", GERBER_LAYERS, "--no-x2", "--use-drill-file-origin",
       "--subtract-soldermask", "-o", str(GERBER) + "/", str(BOARD))
    sh("kicad-cli", "pcb", "export", "drill", "--format", "excellon", "--excellon-separate-th", "--generate-map",
       "--map-format", "gerberx2", "-o", str(GERBER) + "/", str(BOARD))


# ---- JLCPCB assembly ------------------------------------------------------------------------------------------
# LCSC part numbers, each checked against LCSC's product record (productModel) on 2026-11-01. "DNP" = not placed by
# the assembler (off-board, hand-soldered THT, pads only); "CONSIGN" = not stocked at LCSC, supply it (or JLC global
# sourcing). Keyed by MPN, or (MPN, value) for the generic resistor line.
LCSC = {
    ("R_0402_1%", "100k"): "C25741", ("R_0402_1%", "330"): "C25104", ("R_0402_1%", "1M"): "C26083",
    ("R_0402_1%", "1k"): "C11702", ("R_0402_1%", "5.1k"): "C25905", ("R_0402_1%", "732k"): "C137940",
    ("R_0402_1%", "100"): "C25076", ("R_0402_1%", "2.2k"): "C25879",
    ("R_0402_1%", "180k"): "C25760",           # UNI-ROYAL 0402WGF1803TCE
    "C_10u_0603_X5R": "C19702", "C_10u_1206_X7R": "C47971", "GRM31CR60J107ME39L": "C15008",   # C15008 = CL31A107MQHNNNE (pack_uk.csv swap)
    "C_100n_0402": "C1525", "C_1u_0402": "C52923", "GRM21BR61A226ME51L": "C45783", "GRM31CR61A476ME15L": "C96123",
    "C_22p_0402_C0G": "C1555", "LTST-C191KGKT": "C125098", "LTST-C191KRKT": "C125099", "LTST-C191KSKT": "C125100",
    "TPD1E10B06DPYR": "C48260", "BAV199,215": "C40919", "SF-1206F300-2": "CONSIGN",   # Bourns F300 not listed at LCSC
    "SJ1-3543": "DNP", "USB4105-GF-A": "C3020560", "TC2030-pads": "DNP", "DFE252012F-1R0M=P2": "C435392",
    "DMG2305UX-7": "C150470", "JS102011SAQN": "C221660", "TP-pad": "DNP", "BT40NE": "CONSIGN",
    "PCM1840IRTWR": "C2864564", "OPA1656IDR": "C1849431", "TPS61023DRLR": "C919459", "TLV75533PDBVR": "C404027",
    "USBLC6-2SC6": "C7519", "MY-18650-04-J/05-J": "DNP",   # cradle contacts sit in the enclosure, wired to BT1
}
# CPL rotation corrections KiCad -> JLC, by footprint name. Patterns follow the community JLC rotation DB
# (JLCKicadTools cpl_rotations_db: SOT-23* 180, QFN/DFN 270, SOIC 270); everything else 0. JLC's CPL preview stays
# the final check (end-of-project DFM step).
ROT_CORR = [(r"^SOT-23", 180), (r"QFN-", 270), (r"^SOIC-", 270)]


def jlc_rot(fp_name, rot):
    import re
    for pat, d in ROT_CORR:
        if re.search(pat, fp_name):
            return (rot + d) % 360
    return rot % 360


def lcsc_for(mpn, value):
    return LCSC.get((mpn, value), LCSC.get(mpn, ""))


def bom_cpl():
    pos = FAB / "pos_raw.csv"
    sh("kicad-cli", "pcb", "export", "pos", "--format", "csv", "--units", "mm", "--side", "both", "-o", str(pos), str(BOARD))
    mpn = {}
    with open(HERE / "out" / "bom.csv") as f:
        for r in csv.DictReader(f):
            for ref in r["refs"].split():
                mpn[ref] = r["mpn"]
    rows = [r for r in csv.DictReader(open(pos)) if r["Ref"] in mpn]   # mounting holes are not parts
    part = {r["Ref"]: lcsc_for(mpn[r["Ref"]], r["Val"]) for r in rows}
    with open(FAB / "cpl_jlc.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Designator", "Mid X", "Mid Y", "Layer", "Rotation"])
        for r in rows:
            if part[r["Ref"]] == "DNP":
                continue
            w.writerow([r["Ref"], f"{float(r['PosX']):.3f}mm", f"{float(r['PosY']):.3f}mm", "Top" if r["Side"] == "top" else "Bottom",
                        f"{jlc_rot(r['Package'], float(r['Rot'])):.0f}"])
    groups = {}
    for r in rows:
        key = (r["Val"], r["Package"], mpn.get(r["Ref"], ""))
        groups.setdefault(key, []).append(r["Ref"])
    with open(FAB / "bom_jlc.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Comment", "Designator", "Footprint", "MPN", "LCSC Part #"])
        for (val, pkg, m), refs in sorted(groups.items(), key=lambda kv: kv[1][0]):
            w.writerow([val, ",".join(sorted(refs)), pkg, m, lcsc_for(m, val)])
    pos.unlink()


def step_and_envelope():
    sh("kicad-cli", "pcb", "export", "step", "--force", "--no-components", "--no-optimize-step", "-o", str(FAB / "pack.step"), str(BOARD))
    import re
    txt = (FAB / "pack.step").read_text(errors="ignore")
    (FAB / "pack.step").write_text(re.sub(r"FILE_NAME\(.*?\);", "FILE_NAME('pack.step','',(''),(''),'','','');", txt, count=1, flags=re.S))
    env = []
    for r in envelope_boxes():
        env.append(r)
    (FAB / "envelope.json").write_text(json.dumps(env, indent=1) + "\n")


def envelope_boxes():
    """component boxes (courtyard plan x height) in the board frame, from the pcbnew API (system python)"""
    try:
        import pcbnew as P
    except ImportError:
        return json.loads((FAB / "envelope.json").read_text())
    b = P.LoadBoard(str(BOARD))
    out = []
    for fp in b.GetFootprints():
        ref = fp.GetReference()
        bb = fp.GetCourtyard(P.F_CrtYd).BBox()
        fpn = str(fp.GetFPID().GetLibItemName())
        h = HEIGHT.get(ref)
        if h is None:
            h = next((v for k, v in HEIGHT_BY_FP.items() if fpn.startswith(k)), 1.0)
        x0, x1 = P.ToMM(bb.GetLeft()) - 100, P.ToMM(bb.GetRight()) - 100
        y0, y1 = 100 - P.ToMM(bb.GetBottom()), 100 - P.ToMM(bb.GetTop())
        out.append(dict(ref=ref, x0=round(x0, 3), x1=round(x1, 3), y0=round(y0, 3), y1=round(y1, 3), h=h))
    return out


def manifest():
    files = sorted(p for p in FAB.rglob("*") if p.is_file() and p.name != "manifest.json")
    m = {"board_sha256": board_hash(), "files": {str(p.relative_to(FAB)): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}}
    (FAB / "manifest.json").write_text(json.dumps(m, indent=1) + "\n")


def run_all():
    FAB.mkdir(parents=True, exist_ok=True)
    gerbers()
    bom_cpl()
    step_and_envelope()
    manifest()
    renders()


if __name__ == "__main__":
    renders() if sys.argv[1:] == ["renders"] else run_all()
