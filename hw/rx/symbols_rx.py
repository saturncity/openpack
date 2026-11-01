"""Receiver symbol library: the pack's datasheet-built symbols (hw/pack/symbols.py) plus the
receiver-only parts, written to hw/rx/openpack_rx.kicad_sym. Pin tables cite their datasheets.
"""
import importlib.util, pathlib

_PACK = pathlib.Path(__file__).resolve().parents[1] / "pack/symbols.py"
_spec = importlib.util.spec_from_file_location("hw_pack_symbols", _PACK)
pack_symbols = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(pack_symbols)

P, I, O, B, PI, PO, NC = (pack_symbols.P, pack_symbols.I, pack_symbols.O, pack_symbols.B,
                          pack_symbols.PI, pack_symbols.PO, pack_symbols.NC)
two_pin = pack_symbols.two_pin


# BT40E (ADR-0021): Fanstel "BLE 5.3, 802.15.4 Modules, BT40/F/E/N/NE Product Specifications" v1.09 (July 2024).
# p.11 BT40E mechanical drawing: 14x16x2.0 mm, 16 castellated pads (1-16), 45 LGA pads (Z0-F6), ground pads H0-H3,
# u.FL receptacle on the module (no PCB antenna). p.14 "Pin Assignments of BT40" (BT40 and BT40E share the 14x16
# drawing): every pad carries the same nRF5340 pin as in the BT40F table (pp.16-17, pack_symbols._BT40), F5 = NC.
# No nRF21540, so the nine pads the BT40N/NE use for the FEM are plain GPIO here; unused ones are left open.
def _bt40e_pins():
    pins = []
    for num, name in pack_symbols._BT40:
        if name in ("VDD", "VDDH", "VBUS", "VSS", "GND"):
            pins.append((num, name, PI, "L"))
        elif name == "NC":
            pins.append((num, name, NC, "L"))
        else:
            pins.append((num, name, B, "R"))
    return pins


# Backplane connector pinout: the table in docs/adr/0014-rx-backplane-connector.md (keep in sync; tests check it).
# Pin 14 is the key: pulled from the header, its hole plugged in the main-board socket (#81 review S3).
BACKPLANE = {
    1: "GND", 2: "GND", 3: "AUD_HOT", 4: "AUD_COLD", 5: "GND", 6: "GND",
    7: "+12V", 8: "+12V", 9: "+5V", 10: "+5V", 11: "GND", 12: "GND",
    13: "BP_I2S_BCK", 14: "KEY", 15: "BP_I2S_LRCK", 16: "BP_I2S_SDOUT",
    17: "BP_UART_TX", 18: "BP_UART_RX", 19: "BP_nRESET", 20: "BP_BOOT",
    21: "BP_LED_LOCK", 22: "BP_LED_PEAK", 23: "BP_SLOT0", 24: "BP_SLOT1", 25: "BP_SLOT2", 26: "GND",
}

RX_SYMBOLS = {
    "BT40E": ("U", _bt40e_pins(), "Fanstel BT40E nRF5340 module, u.FL, no FEM (14x16 mm)"),
    # PCM5102A TSSOP-20 (PW): TI SLAS859C (May 2015), section 7 "Pin Functions"
    "PCM5102A": ("U", [("1", "CPVDD", PI, "L"), ("2", "CAPP", P, "L"), ("3", "CPGND", PI, "L"), ("4", "CAPM", P, "L"),
                       ("5", "VNEG", PO, "L"), ("6", "OUTL", O, "L"), ("7", "OUTR", O, "L"), ("8", "AVDD", PI, "L"),
                       ("9", "AGND", PI, "L"), ("10", "DEMP", I, "L"),
                       ("11", "FLT", I, "R"), ("12", "SCK", I, "R"), ("13", "BCK", I, "R"), ("14", "DIN", I, "R"),
                       ("15", "LRCK", I, "R"), ("16", "FMT", I, "R"), ("17", "XSMT", I, "R"), ("18", "LDOO", PO, "R"),
                       ("19", "DGND", PI, "R"), ("20", "DVDD", PI, "R")],
                 "TI PCM5102A 112 dB 2.1 Vrms ground-centred stereo DAC, hardware control"),
    # PE4259 SC-70-6: pSemi DOC-03694-5.01 (07/2026), Table 7 "Pin descriptions"; single-pin mode,
    # Table 5: CTRL high -> RFC-RF1, CTRL low -> RFC-RF2. RF pins must be DC blocked.
    "PE4259": ("U", [("1", "RF1", P, "R"), ("3", "RF2", P, "R"), ("5", "RFC", P, "L"),
                     ("4", "CTRL", I, "L"), ("6", "VDD", PI, "L"), ("2", "GND", PI, "L")],
               "pSemi PE4259 SPDT RF switch 10-3000 MHz, single-pin CMOS control"),
    # Hirose U.FL-R-SMT-1: centre contact 1, ground 2 (Hirose U.FL series drawing)
    "UFL": ("J", [("1", "RF", P, "L"), ("2", "GND", P, "R")], "Hirose U.FL coaxial receptacle"),
    # SMF-series TVS, SOD-123F: 1 = cathode (band), 2 = anode
    "TVS": ("D", two_pin("1", "2", "K", "A"), "Unidirectional TVS diode"),
    "CP": ("C", two_pin("1", "2", "+", "-"), "Polarised capacitor"),
    # TLV76733 HVSSOP-8 (DGN), fixed output: TI SLVSE84D section 5, Pin Functions (OUT 1, SNS 2, NC 3, GND 4, EN 5,
    # GND 6, NC 7, IN 8, thermal pad to GND). VIN abs max 18 V (6.1), so the 5 V TVS clamp (9.2 V) cannot hurt it.
    "TLV76733": ("U", [("8", "IN", PI, "L"), ("5", "EN", I, "L"), ("4", "GND", PI, "L"), ("6", "GND", PI, "L"),
                       ("9", "PAD", PI, "L"), ("1", "OUT", PO, "R"), ("2", "SNS", I, "R"), ("3", "NC", NC, "R"),
                       ("7", "NC", NC, "R")], "TI TLV76733 1 A 3.3 V LDO, 16 V input"),
    # TPS3808 SOT-23-6 (DBV): TI SBVS050N Table 5-1 (RESET 1 open-drain, GND 2, MR 3, CT 4, SENSE 5, VDD 6)
    "TPS3808": ("U", [("6", "VDD", PI, "L"), ("5", "SENSE", I, "L"), ("3", "~{MR}", I, "L"), ("2", "GND", PI, "L"),
                      ("1", "~{RESET}", "open_collector", "R"), ("4", "CT", P, "R")], "TI TPS3808 supervisor, open-drain"),
    # Panasonic TQ2SA-12V DPDT signal relay, single side stable: TQ datasheet "Schematic (Top view)": coil 1 (+) /
    # 10 (-); pole 1 COM 3, NC 2, NO 4; pole 2 COM 8, NC 9, NO 7; pins 5, 6 not used
    "Relay_TQ2": ("K", [("1", "COIL+", P, "L"), ("10", "COIL-", P, "L"), ("5", "n.c.", NC, "L"), ("6", "n.c.", NC, "L"),
                        ("3", "COM1", P, "R"), ("2", "NC1", P, "R"), ("4", "NO1", P, "R"),
                        ("8", "COM2", P, "R"), ("9", "NC2", P, "R"), ("7", "NO2", P, "R")], "DPDT signal relay, 12 V coil"),
    # SOT-23 N-MOSFET (onsemi BSS138): 1 G, 2 S, 3 D
    "NMOS": ("Q", [("1", "G", I, "L"), ("2", "S", P, "R"), ("3", "D", P, "R")], "N-channel MOSFET"),
    # BAT54 SOT-23 single (Nexperia BAT54 pinning): 1 anode, 2 not connected, 3 cathode
    "BAT54": ("D", [("1", "A", P, "L"), ("3", "K", P, "R"), ("2", "n.c.", NC, "R")], "Schottky diode, SOT-23"),
    # S1J SMA: KiCad D_SMA pads 1 = cathode (band), 2 = anode (Vishay S1J: IFSM 30 A, 8.3 ms half sine)
    "Diode": ("D", two_pin("1", "2", "K", "A"), "Rectifier diode"),
    "Conn_Backplane": ("J", [(str(n), name, NC if name == "KEY" else P, "L" if n % 2 else "R") for n, name in BACKPLANE.items()],
                       "Receiver backplane connector, 2x13 2.54 mm (ADR-0014)"),
}


def write_lib(path):
    syms = {**pack_symbols.SYMBOLS, **RX_SYMBOLS}
    body = "\n".join(pack_symbols._symbol(n, *v) for n, v in syms.items())
    pathlib.Path(path).write_text(f'(kicad_symbol_lib (version 20241209) (generator "openpack_symbols")\n{body}\n)\n')
