"""Fab outputs and review renders for hw/rack/rack.kicad_pcb through kicad-cli (KiCad 10): the hw/rx/outputs_rx.py
flow with the rack's LCSC table and JLC rotation corrections.

    python3 hw/rack/outputs_rack.py            # gerbers, drill, BOM, CPL, STEP, PNG renders, manifest
    python3 hw/rack/outputs_rack.py renders    # renders only

hw/rack/out/fab/: gerbers + Excellon (JLCPCB naming), bom_jlc.csv, cpl_jlc.csv, rack.step, mech.json, manifest.json.
hw/rack/out/render/: every copper / silk / mask / paste layer, top and bottom assembly, 3D top and bottom, and crops
of the RF area for the review.
"""
import csv, hashlib, importlib.util, json, pathlib, re, shutil, subprocess, sys

HERE = pathlib.Path(__file__).resolve().parent
BOARD = HERE / "rack.kicad_pcb"
FAB = HERE / "out" / "fab"
GERBER = FAB / "gerber"
RENDER = HERE / "out" / "render"

_spec = importlib.util.spec_from_file_location("hw_pack_outputs_r", HERE.parent / "pack" / "outputs.py")
pko = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(pko)
sh, svg_png, GERBER_LAYERS = pko.sh, pko.svg_png, pko.GERBER_LAYERS

# KiCad -> JLC rotation: the pack's table (SOT-23 +180, QFN +270, SOIC +270) plus the rack's other IC packages, which
# JLC/EasyEDA draw with pin 1 bottom-left and the pin rows horizontal (KiCad: pin 1 top-left, rows vertical), and the
# electrolytic / SMB whose JLC library parts sit at 180 to KiCad's. Check the polarized parts first in JLC's CPL
# preview (hw/REVIEW.md rack section lists them).
ROT_CORR = [(r"^TSSOP-", 270), (r"^DFN-", 270), (r"^HVSSOP-", 270), (r"^Texas_DSG0008A", 270), (r"^SOT-583", 180),
            (r"^CP_Elec", 180), (r"^D_SMB", 180)] + pko.ROT_CORR


def jlc_rot(fp_name, rot):
    for pat, d in ROT_CORR:
        if re.search(pat, fp_name):
            return (rot + d) % 360
    return rot % 360


LAYERS = {"L1_F.Cu": "F.Cu", "L2_In1.Cu": "In1.Cu", "L3_In2.Cu": "In2.Cu", "L4_B.Cu": "B.Cu",
          "F.Silkscreen": "F.SilkS", "B.Silkscreen": "B.SilkS", "F.Mask": "F.Mask", "B.Mask": "B.Mask",
          "F.Paste": "F.Paste", "B.Paste": "B.Paste"}

# ---- JLCPCB assembly ------------------------------------------------------------------------------------------
# LCSC part numbers, each read from its JLC parts record (jlcpcb.com parts API, 2026-11-01, stock unconfirmed) or
# given by the coordinator from its jlcpcb partdetail page. "DNP" = not placed by the assembler (hand-soldered THT,
# pads only, copper); "CONSIGN" = not stocked at LCSC (supply it, or JLC global sourcing). Keyed by MPN, or
# (MPN, value) for the generic resistor lines.
V = "LCSC/JLC record read 2026-11-01: "
H = "THT, hand-solder after reflow: "
LCSC = {
    **{("R_0402_1%", v): (c, V + "UNI-ROYAL 0402WGF" + m + "TCE") for v, c, m in (
        ("10k", "C25744", "1002"), ("73.2k", "C26986", "7322"), ("576", "C45320", "5760"), ("511k", "C64042", "5113"),
        ("88.7k", "C25922", "8872"), ("53.6k", "C53398", "5362"), ("10.2k", "C11660", "1022"), ("1.37k", "C423239", "1371"),
        ("1k", "C11702", "1001"), ("100k", "C25741", "1003"), ("4.42k", "C52269", "4421"), ("5.1k", "C25905", "5101"),
        ("100", "C25076", "1000"), ("560", "C25126", "5600"))},
    "R_0402_0R": ("C17168", V + "UNI-ROYAL 0402WGF0000TCE"),
    "R_0402_100R_TF": ("C445575", V + "Panasonic ERA2AEB101X 0.1 % 25 ppm thin film (alt. C844260 Vishay TNPW0402100RBEED)"),
    "R_2512_1R_1W": ("C11254", V + "UNI-ROYAL 25121WF100KT4E 1 W"),
    "C_22n_0402": ("C1532", V + "FH 0402B223K500NT"), "C_100n_0402": ("C1525", V + "Samsung CL05B104KO5NNNC"),
    "C_1u_0402": ("C52923", V + "Samsung CL05A105KA5NQNC 25 V"), "C_33n_0402": ("C106862", V + "YAGEO CC0402KRX7R9BB333"),
    "C_10n_0402": ("C15195", V + "Samsung CL05B103KB5NNNC"), "C_100p_0402_C0G": ("C1546", V + "FH 0402CG101J500NT"),
    "C_22p_0402_C0G": ("C1555", V + "FH 0402CG220J500NT"), "C_10u_0603_X5R": ("C19702", V + "Samsung CL10A106KP8NNNC"),
    "C_10u_1206_25V_X7R": ("C14860", V + "Samsung CL31B106KAHNNNE"), "C_22u_1206_25V_X5R": ("C12891", V + "Samsung CL31A226KAHNNNE"),
    "ALU_100u_25V": ("C7469933", V + "FOSAN FVM025ADA101M0654 6.3 x 5.4"),
    "BZT52C12": ("C12747", V + "LRC LBZT52C12T1G"), "SMBJ12A": ("C135038", V + "Diodes SMBJ12A-13-F"),
    "SMF12A": ("C123800", V + "MDD SMF12A"), "SMAJ58CA": ("C148235", V + "Littelfuse SMAJ58CA"),
    "ESD103-B1-02EL": ("C535146", V + "Infineon ESD103-B1-02EL E6327 (201 in stock)"),
    "ESD101-B1-02EL": ("C535143", V + "Infineon ESD101-B1-02EL E6327 (0 in stock: JLC global sourcing or consign)"),
    "AO4407A": ("C16072", V + "AOS AO4407A"), "TPS259541DSGR": ("C2155673", V + "TI TPS259541DSGR"),
    "TPS259531DSGR": ("C2155674", V + "TI TPS259531DSGR"), "TPS62933DRLR": ("C3200405", V + "TI TPS62933DRLR"),
    "TLV76733DGNR": ("C2873382", V + "TI TLV76733DGNR"), "SC16IS752IPW,128": ("C57156", V + "NXP SC16IS752IPW,128"),
    "QPL9057TR7": ("C470931", V + "Qorvo QPL9057TR7 (0 in stock: global sourcing, or consign from DigiKey UK)"),
    "QPQ1907SR": ("CONSIGN", "Qorvo QPQ1907SR not at LCSC (C22413100 is the TR13 10k reel, 0 stock): DigiKey UK, consign"),
    "FB_0603_600R": ("C85833", V + "Murata BLM18KG601SN1D 1.3 A"),
    "0451004.MRL": ("C27515", V + "Littelfuse 0451004.MRL NANO2 2410 = KiCad Fuse_Littelfuse-NANO2-451_453 pads"),
    "CS0603-39NJ-S": ("C142171", V + "Chilisin CS0603-39NJ-S 39 nH 0603, SRF 2.2 GHz: above SRF it is a ~0.13 pF "
                                       "self-capacitance, |Z| > 1 kohm across 2400-2483.5 MHz, so the shunt choke still costs < 0.02 dB"),
    "SDWL1005C18NGSTF": ("C361616", V + "Sunlord SDWL1005C18NGSTF 18 nH 2 %, Q 25 at 250 MHz, SRF 4.5 GHz (equivalent)"),
    "C3E-14.7456-18-3030-R": ("C6523919", V + "AKER C3E-14.7456-18-3030-R, 18 pF like the CX3225; ESR 100 ohm, -20..70 C"),
    "SRP5030T-6R8M": ("CONSIGN", "Bourns SRP5030T-6R8M (Irms 4.0 A, Isat 4.3 A): buy UK (DigiKey / Mouser / Farnell), "
                                 "not LCSC (C177249 is only 3.5 A)"),
    "U.FL-R-SMT-1(10)": ("C88373", V + "Hirose U.FL-R-SMT-1(10)"),
    "LTST-S270KGKT": ("C125113", V + "Lite-On LTST-S270KGKT side-looking"),
    "LTST-S270KRKT": ("C125114", V + "Lite-On LTST-S270KRKT side-looking"),
    "NC3MAH": ("DNP", H + "Neutrik NC3MAH = LCSC C5154126"),
    "5415025-1": ("DNP", H + "TE 5415025-1 (or Molex 73138-5033) from a UK distributor"),
    "PJ-063AH": ("DNP", H + "CUI / Same Sky PJ-063AH from DigiKey UK / Mouser UK"),
    "2.54-2*20P": ("DNP", H + "BOOMELE 2 x 20 IDC header = LCSC C9138"),
    "B2P-VH": ("DNP", H + "JST B2P-VH = LCSC C160315"),
    "2.54-2*13PFemale": ("DNP", H + "BOOMELE 2x13 female 8.5 mm = LCSC C64320; pull contact 14 and plug the cavity first "
                                   "(the footprint has no hole at 14)"),
    "TP-pad": ("DNP", "pads only"), "PCB_TRACE": ("DNP", "copper: microstrip net tie, no part"),
}
NT_MPN = "R_0402_0R"      # NT1 carries this MPN in backplane.py but is a footprint net tie (copper)


def lcsc_for(mpn, value, ref=""):
    if ref.startswith("NT"):
        return "DNP"
    hit = LCSC.get((mpn, value), LCSC.get(mpn))
    return hit[0] if hit else ""


def lcsc_src(mpn, value, ref=""):
    if ref.startswith("NT"):
        return "copper: footprint net tie (GND to chassis)"
    hit = LCSC.get((mpn, value), LCSC.get(mpn))
    return hit[1] if hit else ""


def renders():
    RENDER.mkdir(parents=True, exist_ok=True)
    for name, layer in LAYERS.items():
        svg = RENDER / f"{name}.svg"
        sh("kicad-cli", "pcb", "export", "svg", "--layers", f"{layer},Edge.Cuts", "--mode-single", "--fit-page-to-board",
           "--exclude-drawing-sheet", "-o", str(svg), str(BOARD))
        svg_png(svg, RENDER / f"{name}.png", density=200, width=2400)
    for name, layers in (("top_assembly", "F.Cu,F.SilkS,F.Fab,F.CrtYd,Edge.Cuts"), ("bottom_assembly", "B.Cu,B.SilkS,B.Fab,B.CrtYd,Edge.Cuts")):
        svg = RENDER / f"{name}.svg"
        sh("kicad-cli", "pcb", "export", "svg", "--layers", layers, "--mode-single", "--fit-page-to-board",
           "--exclude-drawing-sheet", "-o", str(svg), str(BOARD))
        svg_png(svg, RENDER / f"{name}.png", density=200, width=2400)
    for side in ("top", "bottom"):
        out = RENDER / f"3d_{side}.png"
        sh("kicad-cli", "pcb", "render", "--side", side, "--width", "2000", "--height", "1600", "--quality", "high",
           "--zoom", "1.0", "--background", "opaque", "-o", str(out), str(BOARD))
        sh("magick", str(out), "-colors", "128", f"PNG8:{out}")
    # review crops of the RF area (rear 100 mm) from a high-density L1 render
    svg = RENDER / "rf.svg"
    sh("kicad-cli", "pcb", "export", "svg", "--layers", "F.Cu,F.SilkS,Edge.Cuts", "--mode-single", "--fit-page-to-board",
       "--exclude-drawing-sheet", "-o", str(svg), str(BOARD))
    big = RENDER / "rf_big.png"
    sh("magick", "-density", "600", str(svg), "-background", "white", "-flatten", "-colors", "16", f"PNG8:{big}")
    svg.unlink()
    w, h = (int(v) for v in sh("magick", "identify", "-format", "%w %h", str(big)).split())
    sx, sy = w / 412.0, h / 323.0
    for name, (x0, y0, x1, y1) in {"crop_rf_center": (130, 0, 250, 100), "crop_rf_left": (0, 0, 130, 100),
                                   "crop_power_entry": (330, 0, 412, 60)}.items():
        # board y runs up from the rear edge; the image's y runs down from the front edge
        px0, px1 = int(x0 * sx), int(x1 * sx)
        py0, py1 = int((323 - y1) * sy), int((323 - y0) * sy)
        sh("magick", str(big), "-crop", f"{px1 - px0}x{py1 - py0}+{px0}+{py0}", "+repage", "-resize", "2000x",
           "-colors", "16", f"PNG8:{RENDER / (name + '.png')}")
    big.unlink()


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
    sh("kicad-cli", "pcb", "export", "pos", "--format", "csv", "--units", "mm", "--side", "both", "-o", str(pos), str(BOARD))
    mpn, val = {}, {}
    with open(HERE / "out" / "bom.csv") as f:
        for r in csv.DictReader(f):
            for ref in r["refs"].split():
                if ref != "-":
                    mpn[ref] = r["mpn"]; val[ref] = r["value"]
    rows = [r for r in csv.DictReader(open(pos)) if r["Ref"] in mpn]
    have = {r["Ref"] for r in rows}
    extra = sorted(set(mpn) - have)            # net ties (excluded from position files) still go in the BOM
    part = {r["Ref"]: lcsc_for(mpn[r["Ref"]], r["Val"], r["Ref"]) for r in rows}
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
        groups.setdefault((r["Val"], r["Package"], mpn[r["Ref"]]), []).append(r["Ref"])
    for ref in extra:
        groups.setdefault((val[ref], "", mpn[ref]), []).append(ref)
    with open(FAB / "bom_jlc.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Comment", "Designator", "Footprint", "MPN", "LCSC Part #", "LCSC source"])
        for (v, pkg, m), refs in sorted(groups.items(), key=lambda kv: sorted(kv[1])[0]):
            r0 = sorted(refs)[0]
            w.writerow([v, ",".join(sorted(refs)), pkg, m, lcsc_for(m, v, r0), lcsc_src(m, v, r0)])
    pos.unlink()


def step_and_mech():
    sh("kicad-cli", "pcb", "export", "step", "--force", "--no-components", "--no-optimize-step", "-o", str(FAB / "rack.step"), str(BOARD))
    txt = (FAB / "rack.step").read_text(errors="ignore")
    (FAB / "rack.step").write_text(re.sub(r"FILE_NAME\(.*?\);", "FILE_NAME('rack.step','',(''),(''),'','','');", txt, count=1, flags=re.S))
    shutil.copy(HERE / "out" / "mech.json", FAB / "mech.json")


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
