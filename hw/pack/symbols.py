"""Project symbol library for the pack: pin lists from datasheets -> openpack.kicad_sym.

KiCad's stock libraries are not vendored here, so every part gets a plain box symbol
generated from its datasheet pin table (sources in BOM `Datasheet` column). A pin is
(number, name, type, side); side L/R/T/B. Types are KiCad pin electrical types.
"""
import pathlib

P, I, O, B, PI, PO, NC = "passive", "input", "output", "bidirectional", "power_in", "power_out", "no_connect"
G = 2.54


def two_pin(n1="1", n2="2", name1="~", name2="~", t=P):
    return [(n1, name1, t, "T"), (n2, name2, t, "B")]


# BT40NE: Fanstel "BT40/F/E/N/NE Product Specifications" v1.08 (Sep 2023), Pin Functions table
# (BT40F column; BT40N/NE "has the same soldering pads as BT40F"). Pads marked * drive the
# nRF21540 inside the module: never use them.
_FEM = {"Z6", "A6", "C2", "C6", "D1", "D2", "E0", "E1", "E2"}
_BT40 = [("1", "P1.02"), ("2", "P1.03"), ("3", "NC"), ("4", "NC"), ("5", "P0.04/AIN0"), ("6", "P0.05/AIN1"),
         ("7", "P0.02/NFC1"), ("8", "P0.03/NFC2"), ("9", "VDD"), ("10", "VSS"), ("11", "P0.09"), ("12", "P0.11"),
         ("13", "P0.30"), ("14", "~{RESET}"), ("15", "SWDCLK"), ("16", "SWDIO"),
         ("Z0", "P1.09"), ("Z1", "P1.10"), ("Z2", "P1.11"), ("Z3", "P1.12"), ("Z4", "P1.13"), ("Z5", "P1.14"), ("Z6", "P1.15"),
         ("A0", "VSS"), ("A1", "P0.06/AIN2"), ("A2", "P0.07/AIN3"), ("A3", "P0.08"), ("A4", "P0.16"), ("A5", "P1.00"), ("A6", "P1.08"),
         ("B0", "VSS"), ("B1", "P0.19"), ("B2", "P0.17"), ("B3", "P0.14"), ("B4", "P0.15"), ("B5", "P0.12"), ("B6", "P0.13"),
         ("C0", "VSS"), ("C1", "P0.31"), ("C2", "P0.21"), ("C3", "P0.24"), ("C4", "P0.23"), ("C5", "P0.20"), ("C6", "P0.25/AIN4"),
         ("D0", "VSS"), ("D1", "P0.26/AIN5"), ("D2", "P0.27/AIN6"), ("D3", "P0.28/AIN7"), ("D4", "P0.29"), ("D5", "P0.22"), ("D6", "P1.01"),
         ("E0", "P1.04"), ("E1", "P1.05"), ("E2", "P1.06"), ("E3", "P1.07"), ("E4", "D+"), ("E5", "D-"), ("E6", "P0.10"),
         ("F3", "P0.18"), ("F4", "VDDH"), ("F5", "NC"), ("F6", "VBUS"), ("H0", "GND"), ("H1", "GND"), ("H2", "GND"), ("H3", "GND")]


def _bt40_pins():
    pins = []
    for num, name in _BT40:
        if name in ("VDD", "VDDH", "VBUS"):
            pins.append((num, name, PI, "L"))
        elif name in ("VSS", "GND"):
            pins.append((num, name, PI, "L"))
        elif name == "NC":
            pins.append((num, name, NC, "L"))
        elif num in _FEM:
            pins.append((num, name + "*FEM", NC, "R"))   # internal nRF21540 control: no-connect outside
        else:
            pins.append((num, name, B, "R"))
    return pins


SYMBOLS = {
    # name: (ref prefix, pins, description)
    "BT40NE": ("U", _bt40_pins(), "Fanstel BT40NE nRF5340 + nRF21540 FEM module, PCB antenna + u.FL"),
    # PCM1840 WQFN-24 (RTW): TI SBAS989, Pin Functions
    "PCM1840": ("U", [("1", "AVDD", PI, "L"), ("2", "AREG", PO, "L"), ("3", "VREF", PO, "L"), ("4", "AVSS", PI, "L"),
                      ("5", "MICBIAS", PO, "L"), ("6", "IN1P", I, "L"), ("7", "IN1M", I, "L"), ("8", "IN2P", I, "L"),
                      ("9", "IN2M", I, "L"), ("10", "IN3P", I, "L"), ("11", "IN3M", I, "L"), ("12", "IN4P", I, "L"),
                      ("13", "IN4M", I, "R"), ("14", "SHDNZ", I, "R"), ("15", "FMT1", I, "R"), ("16", "FMT0", I, "R"),
                      ("17", "MSZ", I, "R"), ("18", "MD0", I, "R"), ("19", "IOVDD", PI, "R"), ("20", "MD1", I, "R"),
                      ("21", "SDOUT", O, "R"), ("22", "BCLK", B, "R"), ("23", "FSYNC", B, "R"), ("24", "DREG", PO, "R"),
                      ("25", "VSS(EP)", PI, "R")], "TI PCM1840 4-ch 2 Vrms audio ADC, hardware control"),
    # OPA1656 SOIC-8: TI SBOS901, Figure 5-3
    "OPA1656": ("U", [("3", "+INA", I, "L"), ("2", "-INA", I, "L"), ("5", "+INB", I, "L"), ("6", "-INB", I, "L"),
                      ("1", "OUTA", O, "R"), ("7", "OUTB", O, "R"), ("8", "V+", PI, "R"), ("4", "V-", PI, "R")],
                "TI OPA1656 dual low-noise CMOS audio op-amp"),
    # TPS61023 SOT-563 (DRL): TI SLVSF14B Pin Functions
    "TPS61023": ("U", [("3", "VIN", PI, "L"), ("2", "EN", I, "L"), ("4", "GND", PI, "L"),
                       ("5", "SW", P, "R"), ("6", "VOUT", PO, "R"), ("1", "FB", I, "R")], "TI TPS61023 1 A boost"),
    # TLV755P SOT-23-5 (DBV): TI SBVS320 Table 4-1
    "TLV75533P": ("U", [("1", "IN", PI, "L"), ("3", "EN", I, "L"), ("2", "GND", PI, "L"),
                        ("5", "OUT", PO, "R"), ("4", "NC", NC, "R")], "TI TLV75533P 500 mA 3.3 V LDO"),
    # USBLC6-2SC6 SOT-23-6: ST datasheet
    "USBLC6-2SC6": ("U", [("1", "I/O1", P, "L"), ("6", "I/O1", P, "R"), ("3", "I/O2", P, "L"), ("4", "I/O2", P, "R"),
                          ("5", "VBUS", P, "R"), ("2", "GND", P, "L")], "ST USBLC6-2SC6 USB ESD"),
    # 3.5 mm TRS jack, M6 threaded bushing (Same Sky SJ1-3543): tip / ring / sleeve
    "Jack_TRS_Locking": ("J", [("T", "TIP", P, "R"), ("R", "RING", P, "R"), ("S", "SLEEVE", P, "R")],
                         "3.5 mm TRS jack, threaded bushing for locking plugs"),
    # USB-C 2.0 receptacle (GCT USB4105-GF-A)
    "USB_C_2.0": ("J", [("A4", "VBUS", P, "R"), ("B4", "VBUS", P, "R"), ("A5", "CC1", P, "R"), ("B5", "CC2", P, "R"),
                        ("A6", "D+", P, "R"), ("B6", "D+", P, "R"), ("A7", "D-", P, "R"), ("B7", "D-", P, "R"),
                        ("A8", "SBU1", P, "R"), ("B8", "SBU2", P, "R"),
                        ("A1", "GND", P, "L"), ("B1", "GND", P, "L"), ("S1", "SHIELD", P, "L")], "USB-C 2.0 receptacle"),
    "Tag_TC2030": ("J", [("1", "VTREF", P, "R"), ("2", "SWDIO", P, "R"), ("3", "~{RESET}", P, "R"),
                         ("4", "SWDCLK", P, "R"), ("5", "GND", P, "R"), ("6", "SWO", P, "R")],
                   "Tag-Connect TC2030-IDC-NL SWD pads (footprint only)"),
    "Battery_18650": ("BT", two_pin("1", "2", "+", "-", P), "18650 cell holder, single cell"),
    # C&K JS102011SAQN SPDT slide: 1 / 2 common / 3
    "SW_SPDT": ("SW", [("2", "COM", P, "L"), ("1", "A", P, "R"), ("3", "B", P, "R")], "SPDT slide switch"),
    # SOT-23 P-MOSFET (DMG2305UX): 1 G, 2 S, 3 D
    "PMOS": ("Q", [("1", "G", I, "L"), ("2", "S", P, "R"), ("3", "D", P, "R")], "P-channel MOSFET"),
    # BAV199 SOT-23 (Nexperia): 1 = anode D1, 2 = cathode D2, 3 = common (cathode D1 / anode D2)
    "BAV199": ("D", [("3", "COM", P, "L"), ("1", "A1", P, "R"), ("2", "K2", P, "R")], "Low-leakage dual series diode"),
    "ESD_Bidir": ("D", two_pin(), "Bidirectional TVS/ESD diode"),
    "R": ("R", two_pin(), "Resistor"),
    "C": ("C", two_pin(), "Capacitor"),
    "L": ("L", two_pin(), "Inductor"),
    "Fuse": ("F", two_pin(), "Chip fuse"),
    "LED": ("D", two_pin("1", "2", "K", "A"), "LED"),
    "TestPoint": ("TP", [("1", "1", P, "T")], "Test point"),
}


def _pin_sexp(num, name, typ, x, y, ang):
    f = '(effects (font (size 1.27 1.27)))'
    return f'(pin {typ} line (at {x:.2f} {y:.2f} {ang}) (length 2.54) (name "{name}" {f}) (number "{num}" {f}))'


def _symbol(name, ref, pins, desc):
    L = [p for p in pins if p[3] == "L"]; R = [p for p in pins if p[3] == "R"]
    T = [p for p in pins if p[3] == "T"]; Bt = [p for p in pins if p[3] == "B"]
    rows = max(len(L), len(R), 1)
    h = rows * G
    named = len(L) + len(R) > 0
    if named:
        cw = max([len(p[1]) for p in L] or [0]) + max([len(p[1]) for p in R] or [0])
        w = max(4, int((cw * 1.0 + 3) / 2 + 1)) * G
    else:
        w, h = 2 * G, 2 * G
    w2, top = w / 2, (rows - 1) * G / 2 if named else G
    body = (f'(symbol "{name}_0_1" (rectangle (start {-w2:.2f} {top + G / 2 if named else G:.2f}) '
            f'(end {w2:.2f} {-(top + G / 2) if named else -G:.2f}) (stroke (width 0.254) (type default)) '
            f'(fill (type background))))')
    out = []
    for i, (n, nm, t, _) in enumerate(L):
        out.append(_pin_sexp(n, nm, t, -w2 - G, top - i * G, 0))
    for i, (n, nm, t, _) in enumerate(R):
        out.append(_pin_sexp(n, nm, t, w2 + G, top - i * G, 180))
    for i, (n, nm, t, _) in enumerate(T):
        out.append(_pin_sexp(n, nm, t, i * G, G * 2, 270))
    for i, (n, nm, t, _) in enumerate(Bt):
        out.append(_pin_sexp(n, nm, t, i * G, -G * 2, 90))
    ef = '(effects (font (size 1.27 1.27)))'
    hide = '(effects (font (size 1.27 1.27)) (hide yes))'
    yref = (top + G if named else G) + 1.27
    return (f'(symbol "{name}" (pin_names (offset 0.508)) (exclude_from_sim no) (in_bom yes) (on_board yes)\n'
            f'  (property "Reference" "{ref}" (at 0 {yref:.2f} 0) {ef})\n'
            f'  (property "Value" "{name}" (at 0 {-yref:.2f} 0) {ef})\n'
            f'  (property "Footprint" "" (at 0 0 0) {hide})\n'
            f'  (property "Datasheet" "" (at 0 0 0) {hide})\n'
            f'  (property "Description" "{desc}" (at 0 0 0) {hide})\n'
            f'  {body}\n  (symbol "{name}_1_1"\n    ' + "\n    ".join(out) + "))")


def write_lib(path):
    body = "\n".join(_symbol(n, *v) for n, v in SYMBOLS.items())
    pathlib.Path(path).write_text(f'(kicad_symbol_lib (version 20241209) (generator "openpack_symbols")\n{body}\n)\n')
