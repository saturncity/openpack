"""Rack main-board symbol library: the pack and receiver symbols (hw/pack/symbols.py, hw/rx/symbols_rx.py) plus the
rack-only parts, written to hw/rack/openpack_rack.kicad_sym. Every pin table cites its datasheet; the one pin table
that could not be read from a datasheet (QPQ1907) says so.
"""
import importlib.util, pathlib

_HW = pathlib.Path(__file__).resolve().parents[1]


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


symbols_rx = _load("hw_rack_symbols_rx", _HW / "rx/symbols_rx.py")
pack_symbols = symbols_rx.pack_symbols
P, I, O, B, PI, PO, NC = (pack_symbols.P, pack_symbols.I, pack_symbols.O, pack_symbols.B,
                          pack_symbols.PI, pack_symbols.PO, pack_symbols.NC)
OD = "open_collector"
two_pin = pack_symbols.two_pin
BACKPLANE = symbols_rx.BACKPLANE   # ADR-0014 slot pinout, the socket side mirrors it pin for pin

# Raspberry Pi 40-way header (CM4IO J8, cm4io-datasheet "40Way GPIO Header", standard Raspberry Pi pinout).
# Only the pins the rack uses are named for their job; the BCM GPIO number is kept in the name.
HOST_HEADER = {
    1: "3V3", 2: "5V", 3: "GPIO2", 4: "5V", 5: "GPIO3", 6: "GND", 7: "GPIO4", 8: "GPIO14", 9: "GND", 10: "GPIO15",
    11: "GPIO17", 12: "GPIO18", 13: "GPIO27", 14: "GND", 15: "GPIO22", 16: "GPIO23", 17: "3V3", 18: "GPIO24",
    19: "GPIO10", 20: "GND", 21: "GPIO9", 22: "GPIO25", 23: "GPIO11", 24: "GPIO8", 25: "GND", 26: "GPIO7",
    27: "GPIO0", 28: "GPIO1", 29: "GPIO5", 30: "GND", 31: "GPIO6", 32: "GPIO12", 33: "GPIO13", 34: "GND",
    35: "GPIO19", 36: "GPIO16", 37: "GPIO26", 38: "GPIO20", 39: "GND", 40: "GPIO21",
}

RACK_SYMBOLS = {
    # Qorvo QPL9057 DFN-8 2x2: datasheet Rev. F (2020-09-20) "Pin Configuration and Description": 1 Vbias, 2 RF In
    # (DC block required), 6 Shut Down (<= 0.63 V = on), 7 RF Out / DC bias (via RF choke), 3/4/5/8 NC with grounded
    # land pads, backside paddle RF/DC ground.
    "QPL9057": ("U", [("2", "RF_IN", P, "L"), ("1", "VBIAS", P, "L"), ("6", "SD", I, "L"), ("3", "NC3", P, "L"),
                      ("4", "NC4", P, "L"), ("7", "RF_OUT", P, "R"), ("5", "NC5", P, "R"), ("8", "NC8", P, "R"),
                      ("9", "GND", PI, "R")], "Qorvo QPL9057 0.6-4.2 GHz ultra-low-noise LNA"),
    # Qorvo QPQ1907 BAW band-pass (2402.5-2481.5 MHz), 1.4 x 1.2 mm 5-pad laminate. PIN TABLE NOT READ FROM THE
    # DATASHEET (qorvo.com rate-limited, 2026-11-01): the usual Qorvo 5-pad single-ended layout is assumed (1 in,
    # 3 out, 2/4/5 ground). ADR-0018 open item: confirm before layout (#34).
    "QPQ1907": ("U", [("1", "RF_IN", P, "L"), ("2", "GND2", P, "L"), ("4", "GND4", P, "R"), ("3", "RF_OUT", P, "R"),
                      ("5", "GND5", P, "R")], "Qorvo QPQ1907 2.4 GHz ISM BAW band-pass filter (pinout est.)"),
    # TI TPS2595x0/1 WSON-8 (DSG): SLVSE57C section 6, Pin Functions: 1 dVdt, 2 EN/UVLO, 3/4 IN, 5 OUT, 6 FLT (open
    # drain), 7 ILM, 8 GND, PAD GND.
    "TPS2595": ("U", [("3", "IN", PI, "L"), ("4", "IN", PI, "L"), ("2", "EN/UVLO", I, "L"), ("1", "dVdt", P, "L"),
                      ("7", "ILM", P, "L"), ("5", "OUT", PO, "R"), ("6", "~{FLT}", OD, "R"), ("8", "GND", PI, "R"),
                      ("9", "PAD", PI, "R")], "TI TPS2595 2.7-18 V 4 A eFuse"),
    # TI TPS62933 SOT-583 (DRL): SLUSEA4D Table 7-1: 1 RT, 2 EN, 3 VIN, 4 GND, 5 SW, 6 BST, 7 SS/PG, 8 FB.
    "TPS62933": ("U", [("3", "VIN", PI, "L"), ("2", "EN", I, "L"), ("1", "RT", P, "L"), ("7", "SS", P, "L"),
                       ("4", "GND", PI, "L"), ("5", "SW", PO, "R"), ("6", "BST", P, "R"), ("8", "FB", I, "R")],
                 "TI TPS62933 3.8-30 V 3 A synchronous buck"),
    # NXP SC16IS752 TSSOP-28 (IPW): datasheet Rev. 9.1 Table 2 (TSSOP28 column).
    "SC16IS752": ("U", [("8", "VDD", PI, "L"), ("22", "VSS", PI, "L"), ("9", "I2C/~{SPI}", I, "L"),
                        ("10", "~{CS}/A0", I, "L"), ("11", "SI/A1", I, "L"), ("12", "SO", "tri_state", "L"),
                        ("13", "SCL/SCLK", I, "L"), ("14", "SDA", B, "L"), ("15", "~{IRQ}", OD, "L"),
                        ("5", "~{RESET}", I, "L"), ("6", "XTAL1", I, "L"), ("7", "XTAL2", O, "L"),
                        ("3", "TXA", O, "R"), ("4", "RXA", I, "R"), ("1", "~{RTSA}", O, "R"), ("2", "~{CTSA}", I, "R"),
                        ("23", "TXB", O, "R"), ("24", "RXB", I, "R"), ("17", "~{RTSB}", O, "R"), ("16", "~{CTSB}", I, "R"),
                        ("18", "GPIO0", B, "R"), ("19", "GPIO1", B, "R"), ("20", "GPIO2", B, "R"), ("21", "GPIO3", B, "R"),
                        ("25", "GPIO4", B, "R"), ("26", "GPIO5", B, "R"), ("27", "GPIO6", B, "R"), ("28", "GPIO7", B, "R")],
                  "NXP SC16IS752 dual UART, SPI/I2C, 8 GPIO"),
    "Crystal": ("Y", two_pin("1", "2", "1", "2"), "Quartz crystal"),
    # Amphenol RF 112487 right-angle bulkhead BNC jack: centre contact 1, body 2 (footprint pegs on the body net)
    "BNC": ("J", [("1", "IN", P, "L"), ("2", "SHIELD", P, "R")], "BNC 50 ohm jack"),
    # Neutrik NC3MAH male XLR, horizontal PCB: contacts 1 (shield), 2 (hot), 3 (cold), G = housing/ground tab
    "XLR3_Male": ("J", [("1", "PIN1", P, "L"), ("2", "HOT", P, "L"), ("3", "COLD", P, "L"), ("G", "SHELL", P, "R")],
                  "3-pin XLR male, PCB"),
    # Same Sky (CUI) PJ-063AH 2.1 mm DC jack: 1 centre pin (+), 2 sleeve, 3 switch
    "DC_Jack": ("J", [("1", "+", P, "R"), ("2", "SLEEVE", P, "R"), ("3", "SW", P, "R")], "2.1 mm DC power jack"),
    # Alpha & Omega AO4407A SO-8 P-MOSFET: 1-3 S, 4 G, 5-8 D (standard SO-8 single-FET pinout)
    "PMOS_SO8": ("Q", [("4", "G", I, "L"), ("1", "S", P, "R"), ("2", "S", P, "R"), ("3", "S", P, "R"),
                       ("5", "D", P, "R"), ("6", "D", P, "R"), ("7", "D", P, "R"), ("8", "D", P, "R")], "P-MOSFET SO-8"),
    "Conn_Slot": ("J", [(str(n), name, NC if name == "KEY" else P, "L" if n % 2 else "R") for n, name in BACKPLANE.items()],
                  "Receiver slot socket 2x13 2.54 mm, position 14 plugged (ADR-0014 key)"),
    "Conn_Host40": ("J", [(str(n), name, P, "L" if n % 2 else "R") for n, name in HOST_HEADER.items()],
                    "2x20 2.54 mm box header to the CM4IO 40-way GPIO header (ribbon, pin n to pin n)"),
    "Conn_01x02": ("J", [("1", "1", P, "L"), ("2", "2", P, "L")], "2-pin connector"),
    "NetTie": ("NT", two_pin(), "Net tie (GND to chassis bond)"),
    # Wilkinson arm: a copper microstrip, drawn as a 2-terminal part so the netlist keeps its two ends apart
    # (footprint = net-tie copper; width and length from hw/rack/wilkinson.py)
    "TL": ("TL", two_pin(), "Microstrip transmission line (PCB copper)"),
}


def write_lib(path):
    syms = {**pack_symbols.SYMBOLS, **symbols_rx.RX_SYMBOLS, **RACK_SYMBOLS}
    body = "\n".join(pack_symbols._symbol(n, *v) for n, v in syms.items())
    pathlib.Path(path).write_text(f'(kicad_symbol_lib (version 20241209) (generator "openpack_symbols")\n{body}\n)\n')
