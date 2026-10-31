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

# Backplane connector pinout: the table in docs/adr/0014-rx-backplane-connector.md (keep in sync; tests check it).
BACKPLANE = {
    1: "GND", 2: "GND", 3: "AUD_HOT", 4: "AUD_COLD", 5: "GND", 6: "GND",
    7: "+12V", 8: "+12V", 9: "+5V", 10: "+5V", 11: "GND", 12: "GND",
    13: "BP_I2S_BCK", 14: "GND", 15: "BP_I2S_LRCK", 16: "BP_I2S_SDOUT",
    17: "BP_UART_TX", 18: "BP_UART_RX", 19: "BP_nRESET", 20: "BP_BOOT",
    21: "BP_LED_LOCK", 22: "BP_LED_PEAK", 23: "BP_SLOT0", 24: "BP_SLOT1", 25: "BP_SLOT2", 26: "GND",
}

RX_SYMBOLS = {
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
    # BAV99 SOT-23 (Nexperia BAV99 datasheet, pinning): 1 = anode D1, 2 = cathode D2, 3 = cathode D1 / anode D2
    "BAV99": ("D", [("3", "COM", P, "L"), ("1", "A1", P, "R"), ("2", "K2", P, "R")], "Dual series switching diode"),
    # SMF-series TVS, SOD-123F: 1 = cathode (band), 2 = anode
    "TVS": ("D", two_pin("1", "2", "K", "A"), "Unidirectional TVS diode"),
    "CP": ("C", two_pin("1", "2", "+", "-"), "Polarised capacitor"),
    "Conn_Backplane": ("J", [(str(n), name, P, "L" if n % 2 else "R") for n, name in BACKPLANE.items()],
                       "Receiver backplane connector, 2x13 2.54 mm (ADR-0014)"),
}


def write_lib(path):
    syms = {**pack_symbols.SYMBOLS, **RX_SYMBOLS}
    body = "\n".join(pack_symbols._symbol(n, *v) for n, v in syms.items())
    pathlib.Path(path).write_text(f'(kicad_symbol_lib (version 20241209) (generator "openpack_symbols")\n{body}\n)\n')
