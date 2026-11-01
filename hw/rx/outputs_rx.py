"""Fab outputs and review renders for hw/rx/rx.kicad_pcb, all through kicad-cli (KiCad 10). Same flow as
hw/pack/outputs.py (the #104 template), with the receiver's LCSC table.

    python3 hw/rx/outputs_rx.py            # gerbers, drill, BOM, CPL, STEP, PNG renders, manifest
    python3 hw/rx/outputs_rx.py renders    # renders only

hw/rx/out/fab/: gerbers + Excellon (JLCPCB naming), bom_jlc.csv, cpl_jlc.csv, rx.step, mech.json, manifest.json
(sha256 of the board each output was made from; tests/test_rx_layout.py checks it).
hw/rx/out/render/: one PNG per copper layer (+ edge), silk/mask/paste per side, top assembly, top/bottom 3D views.
Needs ImageMagick (`magick`) to rasterise kicad-cli's SVGs.
"""
import csv, hashlib, importlib.util, json, pathlib, re, shutil, subprocess, sys

HERE = pathlib.Path(__file__).resolve().parent
BOARD = HERE / "rx.kicad_pcb"
FAB = HERE / "out" / "fab"
GERBER = FAB / "gerber"
RENDER = HERE / "out" / "render"

_spec = importlib.util.spec_from_file_location("hw_pack_outputs", HERE.parent / "pack" / "outputs.py")
pko = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(pko)
sh, svg_png, jlc_rot, GERBER_LAYERS = pko.sh, pko.svg_png, pko.jlc_rot, pko.GERBER_LAYERS

# every layer the fab sees gets a render (the #34 brief: "render every layer")
LAYERS = {"L1_F.Cu": "F.Cu", "L2_In1.Cu": "In1.Cu", "L3_In2.Cu": "In2.Cu", "L4_B.Cu": "B.Cu",
          "F.Silkscreen": "F.SilkS", "B.Silkscreen": "B.SilkS", "F.Mask": "F.Mask", "B.Mask": "B.Mask",
          "F.Paste": "F.Paste", "B.Paste": "B.Paste"}

# ---- JLCPCB assembly ------------------------------------------------------------------------------------------
# LCSC part numbers. "DNP" = not placed by the assembler (pads only, not fitted, or hand-soldered THT); "CONSIGN" = not
# stocked at LCSC (supply it, or JLC global sourcing). Keyed by MPN, or (MPN, value) for the generic resistor lines.
# Every code was read on 2026-11-01 from LCSC's product record (lcsc.com/product-detail/<code>.html: productModel and
# description) or JLCPCB's parts search (manufacturer part, package, stock); the second field names the part found.
V = "LCSC/JLC record read 2026-11-01: "
LCSC = {
    ("R_0402_1%", "100k"): ("C25741", V + "UNI-ROYAL 0402WGF1003TCE"), ("R_0402_1%", "1k"): ("C11702", V + "UNI-ROYAL 0402WGF1001TCE"),
    ("R_0402_1%", "100"): ("C25076", V + "UNI-ROYAL 0402WGF1000TCE"), ("R_0402_1%", "10k"): ("C25744", V + "UNI-ROYAL 0402WGF1002TCE"),
    ("R_0402_1%", "22k"): ("C25768", V + "UNI-ROYAL 0402WGF2202TCE"), ("R_0402_1%", "470"): ("C25117", V + "UNI-ROYAL 0402WGF4700TCE"),
    ("R_0402_1%", "2.0k"): ("C4109", V + "UNI-ROYAL 0402WGF2001TCE"), ("R_0402_1%", "3.65k"): ("C67235", V + "UNI-ROYAL 0402WGF3651TCE"),
    ("R_0402_1%", "4.99k"): ("C25903", V + "UNI-ROYAL 0402WGF4991TCE"), ("R_0402_1%", "249k"): ("C11425", V + "UNI-ROYAL 0402WGF2493TCE"),
    ("R_0402_1%", "9.76k"): ("C270420", V + "UNI-ROYAL 0402WGF9761TCE"),
    ("R_0603_1%", "10"): ("C22859", V + "UNI-ROYAL 0603WAF100JT5E (10 ohm 1 %)"),
    ("R_0603_1%", "22"): ("C23345", V + "UNI-ROYAL 0603WAF220JT5E (22 ohm 1 %)"),
    "C_100n_0402": ("C1525", V + "Samsung CL05B104KO5NNNC 16 V X7R"), "C_1u_0402": ("C52923", V + "Samsung CL05A105KA5NQNC 25 V X5R"),
    "C_10u_0603_X5R": ("C19702", V + "Samsung CL10A106KP8NNNC 10 V X5R"),
    "C_10p_0402_C0G": ("C32949", V + "Samsung CL05C100JB5NNNC 50 V C0G"), "C_100p_0402_C0G": ("C1546", V + "FH 0402CG101J500NT 50 V C0G"),
    "C_2n2_0402_C0G": ("C385029", V + "Murata GRM1555C1H222JA01D 50 V C0G"), "C_1n_0402": ("C1523", V + "FH 0402B102K500NT 50 V X7R"),
    "C_2u2_0603_X7R": ("C100082", V + "Samsung CL10B225KP8NNNC 10 V X7R (CAPP/CAPM/VNEG are < 3.3 V)"),
    "C_10u_1206_25V_X7R": ("C14860", V + "Samsung CL31B106KAHNNNE 25 V X7R"),
    "ALU_100u_25V": ("C7469933", V + "FOSAN FVM025ADA101M0654, 6.3 x 5.4"),
    "ALU_47u_25V": ("C696191", V + "Honor RVT1E470M0505, 5 x 5.4"), "ALU_22u_25V": ("C15848", V + "Honor RVT1E220M0505, 5 x 5.4"),
    "OPA1656IDR": ("C1849431", V + "TI OPA1656IDR"), "PE4259-63": ("C470892", V + "pSemi PE4259-63"),
    "PCM5102APWR": ("C107671", V + "TI PCM5102APWR"), "TLV76733DGNR": ("C2873382", V + "TI TLV76733DGNR, HVSSOP-8"),
    "TPS3808G01DBVR": ("C19653", V + "TI TPS3808G01DBVR, SOT-23-6"), "BSS138": ("C52895", V + "onsemi BSS138"),
    "BAT54,215": ("C85084", V + "Nexperia BAT54,215"), "S1J": ("C184326", V + "onsemi S1J, SMA, IFSM 30 A"),
    "SMF15A": ("C123802", V + "MDD SMF15A, SOD-123FL"), "SMF5.0A": ("C193402", V + "MDD SMF5.0A, SOD-123FL"),
    "U.FL-R-SMT-1(10)": ("C88374", V + "Hirose U.FL-R-SMT-1(80): same part, 80-piece-reel suffix"),
    "TQ2SA-12V": ("C2684447", V + "Panasonic TQ2SA-12V-Z (taped TQ2SA-12V), 2245 at JLC"),
    "BT40E": ("CONSIGN", "Fanstel BT40E, not at LCSC: Digi-Key UK 13174285 (prices.py)"),
    "ALU_BP_47u_63V": ("DNP", "THT radial, hand-solder: Nichicon UEP1J470MPD bi-polar 10 x 16 mm (CAT.8100L), not at LCSC; "
                              "UK: Farnell / RS"),
    "HDR_2x13_2.54_KEY14": ("DNP", "THT underside header, pin 14 pulled: hand-solder after reflow"),
    "TC2030-pads": ("DNP", "pads only"), "TP-pad": ("DNP", "pads only"), "DNP": ("DNP", "not fitted (R33-R35, ADR-0014)"),
}


def lcsc_for(mpn, value):
    hit = LCSC.get((mpn, value), LCSC.get(mpn))
    return hit[0] if hit else ""


def lcsc_src(mpn, value):
    hit = LCSC.get((mpn, value), LCSC.get(mpn))
    return hit[1] if hit else ""


def renders():
    RENDER.mkdir(parents=True, exist_ok=True)
    for name, layer in LAYERS.items():
        svg = RENDER / f"{name}.svg"
        sh("kicad-cli", "pcb", "export", "svg", "--layers", f"{layer},Edge.Cuts", "--mode-single", "--fit-page-to-board",
           "--exclude-drawing-sheet", "-o", str(svg), str(BOARD))
        svg_png(svg, RENDER / f"{name}.png", width=1600)
    for name, layers in (("top_assembly", "F.Cu,F.SilkS,F.Fab,F.CrtYd,Edge.Cuts"), ("bottom_assembly", "B.Cu,B.SilkS,B.Fab,B.CrtYd,Edge.Cuts")):
        svg = RENDER / f"{name}.svg"
        sh("kicad-cli", "pcb", "export", "svg", "--layers", layers, "--mode-single", "--fit-page-to-board",
           "--exclude-drawing-sheet", "-o", str(svg), str(BOARD))
        svg_png(svg, RENDER / f"{name}.png", width=1600)
    for side in ("top", "bottom"):
        out = RENDER / f"3d_{side}.png"
        sh("kicad-cli", "pcb", "render", "--side", side, "--width", "1000", "--height", "1600", "--quality", "high",
           "--zoom", "1.0", "--background", "opaque", "-o", str(out), str(BOARD))
        sh("magick", str(out), "-colors", "128", f"PNG8:{out}")


def gerbers():
    if GERBER.exists():
        shutil.rmtree(GERBER)
    GERBER.mkdir(parents=True)
    sh("kicad-cli", "pcb", "export", "gerbers", "--layers", GERBER_LAYERS, "--no-x2", "--use-drill-file-origin",
       "--subtract-soldermask", "-o", str(GERBER) + "/", str(BOARD))
    sh("kicad-cli", "pcb", "export", "drill", "--format", "excellon", "--excellon-separate-th", "--generate-map",
       "--map-format", "gerberx2", "-o", str(GERBER) + "/", str(BOARD))


def bom_cpl():
    pos = FAB / "pos_raw.csv"
    # --exclude-dnp would drop R33-R35 silently; filter here instead so the BOM still lists them as DNP
    sh("kicad-cli", "pcb", "export", "pos", "--format", "csv", "--units", "mm", "--side", "both", "-o", str(pos), str(BOARD))
    mpn = {}
    with open(HERE / "out" / "bom.csv") as f:
        for r in csv.DictReader(f):
            for ref in r["refs"].split():
                if ref != "-":          # bom.csv extras (bare PCB, U.FL jumper) are not board parts
                    mpn[ref] = r["mpn"]
    rows = [r for r in csv.DictReader(open(pos)) if r["Ref"] in mpn]
    have = {r["Ref"] for r in rows}
    # parts kicad-cli leaves out of the position file (DNP-flagged footprints) still go in the BOM
    extra = sorted(set(mpn) - have)
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
    val = {}
    for r in rows:
        groups.setdefault((r["Val"], r["Package"], mpn[r["Ref"]]), []).append(r["Ref"])
    bom = list(csv.DictReader(open(HERE / "out" / "bom.csv")))
    for ref in extra:
        v = next(b["value"] for b in bom if ref in b["refs"].split())
        groups.setdefault((v, "", mpn[ref]), []).append(ref)
    with open(FAB / "bom_jlc.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Comment", "Designator", "Footprint", "MPN", "LCSC Part #", "LCSC source"])
        for (v, pkg, m), refs in sorted(groups.items(), key=lambda kv: sorted(kv[1])[0]):
            w.writerow([v, ",".join(sorted(refs)), pkg, m, lcsc_for(m, v), lcsc_src(m, v)])
    pos.unlink()


def step_and_mech():
    sh("kicad-cli", "pcb", "export", "step", "--force", "--no-components", "--no-optimize-step", "-o", str(FAB / "rx.step"), str(BOARD))
    txt = (FAB / "rx.step").read_text(errors="ignore")
    (FAB / "rx.step").write_text(re.sub(r"FILE_NAME\(.*?\);", "FILE_NAME('rx.step','',(''),(''),'','','');", txt, count=1, flags=re.S))
    spec = importlib.util.spec_from_file_location("hw_rx_layout_m", HERE / "layout_rx.py")
    lay = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(lay)
    (FAB / "mech.json").write_text(json.dumps(lay.MECH, indent=1) + "\n")


def manifest():
    files = sorted(p for p in FAB.rglob("*") if p.is_file() and p.name != "manifest.json")
    m = {"board_sha256": hashlib.sha256(BOARD.read_bytes()).hexdigest(),
         "files": {str(p.relative_to(FAB)): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}}
    (FAB / "manifest.json").write_text(json.dumps(m, indent=1) + "\n")


def run_all():
    FAB.mkdir(parents=True, exist_ok=True)
    gerbers()
    bom_cpl()
    step_and_mech()
    manifest()
    renders()


if __name__ == "__main__":
    renders() if sys.argv[1:] == ["renders"] else run_all()
