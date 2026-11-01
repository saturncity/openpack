"""OpenPack rack main board ("backplane": SPEC RK-1..RK-3, ADR-0018) in SKiDL. One per rack.

Run:  python hw/rack/backplane.py           -> ERC, then writes in hw/rack/out/:
        backplane.net (KiCad netlist), bom.csv (read by audit.py), erc.txt,
        sch/backplane.kicad_sch (KiCad 9 schematic), svg/ (rendered pages)
      python hw/rack/backplane.py --no-sch   -> netlist/BOM/ERC only (fast)

Blocks:
  rf_a, rf_b   rear BNC -> RF ESD -> switchable 12 V bias-T -> DC block -> 2nd ESD -> QPL9057 LNA -> QPQ1907 BAW
               band-pass -> 1:8 Wilkinson tree (copper; hw/rack/wilkinson.py) -> 8 u.FL, one per receiver slot
  power        12 V brick jack -> reverse-polarity P-FET -> TVS -> input eFuse (13.7 V clamp, 3.5 A) -> +12V_BUS;
               5 V 3 A buck; 3.3 V LDO; eFuse feed to the CM4 IO board
  host         2x20 header -> ribbon -> CM4IO 40-way header: 4 CM4 UARTs, SPI1 to two SC16IS752 (4 more UARTs and
               16 GPIO for the slots' nRESET/BOOT), bias-T enables and faults, a wire-OR power fault line
  slot0..7     ADR-0014 socket (key 14 plugged), per-slot eFuses on +12 V and +5 V, slot-ID straps, front LEDs,
               XLR male with >= 58 V TVS on pins 2/3 (phantom), two u.FL from the splitters
"""
import csv, importlib.util, math, pathlib, re, sys

HERE = pathlib.Path(__file__).resolve().parent


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


symbols_rack = _load("hw_rack_symbols", HERE / "symbols_rack.py")
prices = _load("hw_rack_prices", HERE / "prices.py")
wilkinson = _load("hw_rack_wilkinson", HERE / "wilkinson.py")

OUT = HERE / "out"
LIB = HERE / "openpack_rack.kicad_sym"
N_SLOTS = 8

# Host side of each slot's UART (ADR-0018). CM4 UARTs: BCM2711 ALT4 (TXD3/RXD3 GPIO4/5, TXD4/RXD4 GPIO8/9,
# TXD5/RXD5 GPIO12/13) and ALT0 (TXD0/RXD0 GPIO14/15), CM4 datasheet Table 1. Slots 4-7: SC16IS752 channels.
SLOT_UART = {0: ("GPIO14", "GPIO15"), 1: ("GPIO4", "GPIO5"), 2: ("GPIO8", "GPIO9"), 3: ("GPIO12", "GPIO13"),
             4: ("U4", "A"), 5: ("U4", "B"), 6: ("U5", "A"), 7: ("U5", "B")}
# nRESET / BOOT per slot: SC16IS752 GPIOs (U4 for slots 0-3, U5 for 4-7); GPIO 2k = nRESET, 2k+1 = BOOT.
# Firmware (host) drives them as open drain: output-low to assert, input (hi-Z) to release; GPIOs reset to inputs.
SLOT_CTRL = {k: ("U4" if k < 4 else "U5", 2 * (k % 4), 2 * (k % 4) + 1) for k in range(N_SLOTS)}
# Other host pins (BCM numbers on the CM4IO header): SPI1 (ALT4: CE0 18, CE1 17, MISO 19, MOSI 20, SCLK 21)
HOST = {"SPI1_CE0": "GPIO18", "SPI1_CE1": "GPIO17", "SPI1_MISO": "GPIO19", "SPI1_MOSI": "GPIO20",
        "SPI1_SCLK": "GPIO21", "IRQ_U4": "GPIO24", "IRQ_U5": "GPIO25", "BIAS_A_EN": "GPIO22", "BIAS_B_EN": "GPIO23",
        "BIAS_A_FLT": "GPIO26", "BIAS_B_FLT": "GPIO27", "PWR_FLT": "GPIO6"}

# eFuse settings (TPS2595 SLVSE57C): R_ILM = 2000 / (I_LIM - 0.04) (Equation 4, 487..5000 ohm);
# EN/UVLO rises at 1.2 V typ (1.13-1.27), falls at 1.1 V, max 6 V.
R_ILM = {"input": 576, "cm4": 1370, "slot": 4420, "bias": 4420}
UVLO_12 = (73.2e3, 10e3)   # +12 V eFuses turn on at 1.2 x 8.32 = 9.98 V, off at 9.15 V
I_LIM_MAX_4420 = 0.52      # SLVSE57C 7.5: R_ILM = 4420 ohm -> 0.46 / 0.49 / 0.52 A (min / typ / max)
# Package power ratings (W, 70 C; Yageo RC / Vishay CRCW class values) for the resistor footprints used here
R_POWER_W = {"Resistor_SMD:R_0402_1005Metric": 0.0625, "Resistor_SMD:R_0603_1608Metric": 0.1,
             "Resistor_SMD:R_1206_3216Metric": 0.25, "Resistor_SMD:R_2512_6332Metric": 1.0}


# Front-panel status LEDs: side-looking SMD, Lite-On LTST-S270 (LCSC C125113 green / C125114 red, #34)
LED_MPN = {"green": "LTST-S270KGKT", "red": "LTST-S270KRKT"}


def i_lim(r):
    return 2000 / r + 0.04


def build():
    import builtins
    from skidl import KICAD9, Group, Net, Part, POWER, lib_search_paths, set_default_tool, reset
    reset()
    set_default_tool(KICAD9)
    NC = builtins.NC
    symbols_rack.write_lib(LIB)
    if str(HERE) not in lib_search_paths[KICAD9]:
        lib_search_paths[KICAD9].append(str(HERE))
    # D1/D2 (power entry) and L1 (buck) are named explicitly; automatic numbering starts after them, so SKiDL never
    # has to rename a clash (it made D1_1 / D2_1 / L1_1 before #34)
    count = {"D": 2, "L": 1}

    def ref(prefix):
        count[prefix] = count.get(prefix, 0) + 1
        return f"{prefix}{count[prefix]}"

    def part(sym, rf, value, fp, mpn):
        p = Part("openpack_rack", sym, ref=rf, value=value, footprint=fp, tag=rf)
        p.fields["MPN"] = mpn
        return p

    R0402, C0402, C0603, C1206 = ("Resistor_SMD:R_0402_1005Metric", "Capacitor_SMD:C_0402_1005Metric",
                                  "Capacitor_SMD:C_0603_1608Metric", "Capacitor_SMD:C_1206_3216Metric")
    CMPN = {"100n": "C_100n_0402", "1u": "C_1u_0402", "10u": "C_10u_0603_X5R", "22n": "C_22n_0402",
            "33n": "C_33n_0402", "10n": "C_10n_0402", "100p": "C_100p_0402_C0G", "22p": "C_22p_0402_C0G",
            "10u 25V": "C_10u_1206_25V_X7R", "22u 25V": "C_22u_1206_25V_X5R"}

    def R(val, a, b, mpn="R_0402_1%", rf=None, fp=R0402):
        """Every resistor carries its package power rating (R_POWER_W) so tests can check dissipation."""
        r = part("R", rf or ref("R"), val, fp, mpn); r[1] += a; r[2] += b
        r.fields["P_W"] = str(R_POWER_W[fp])
        return r

    def C(val, a, b, rf=None):
        mpn = CMPN[val]
        fp = C1206 if "1206" in mpn else C0603 if "0603" in mpn else C0402
        c = part("C", rf or ref("C"), val, fp, mpn); c[1] += a; c[2] += b; return c

    def CP(val, pos, neg, mpn, fp):
        c = part("CP", ref("C"), val, fp, mpn); c["+"] += pos; c["-"] += neg; return c

    def power(name):
        n = Net(name); n.drive = POWER; return n

    def tp(n):
        """bring-up test pad (#104 review M2: every rail and bus gets one)"""
        t = part("TestPoint", ref("TP"), n.name, "TestPoint:TestPoint_Pad_D1.0mm", "TP-pad"); t[1] += n
        return t

    gnd, chassis = power("GND"), Net("CHASSIS")
    v12raw, v12p, v12, v5, v3 = power("+12V_RAW"), power("+12V_PROT"), power("+12V_BUS"), power("+5V"), power("+3V3")
    hnet = {}

    def host(gpio):                      # a CM4 GPIO as it arrives on the ribbon header
        if gpio not in hnet:
            hnet[gpio] = Net(f"HOST_{gpio}")
        return hnet[gpio]

    def efuse(rf, mpn, vin, vout, r_ilm, en, flt, c_dvdt="22n"):
        """TPS2595: IN/OUT, ILM to GND, dVdt cap, EN as given (net), FLT open drain to the given net."""
        u = part("TPS2595", rf, mpn, "Package_SON:Texas_DSG0008A_WSON-8-1EP_2x2mm_P0.5mm_EP0.9x1.6mm", mpn)
        u["IN"] += vin; u["OUT"] += vout; u["GND"] += gnd; u["PAD"] += gnd
        ilm, dvdt = Net(f"{rf}_ILM"), Net(f"{rf}_DVDT")
        u["ILM"] += ilm; u["dVdt"] += dvdt; u["EN/UVLO"] += en
        R(f"{r_ilm / 1e3:g}k" if r_ilm >= 1000 else str(r_ilm), ilm, gnd)
        C(c_dvdt, dvdt, gnd)
        C("100n", vin, gnd); C("1u", vout, gnd)
        u["~{FLT}"] += flt if flt is not None else NC
        return u

    def uvlo12(rf):                      # EN/UVLO divider from +12V_BUS
        en = Net(f"{rf}_EN")
        R(f"{UVLO_12[0] / 1e3:g}k", v12, en); R(f"{UVLO_12[1] / 1e3:g}k", en, gnd)
        return en

    pwr_flt = host(HOST["PWR_FLT"])      # wire-OR of every power eFuse fault (open drain), to the host

    with Group("power"):
        # ---- 12 V entry: brick jack -> 4 A fast fuse -> P-FET reverse polarity -> SMBJ12A -> TPS259541 ----
        # The fuse sits ahead of the TVS: a wrong (15-24 V) brick makes the SMBJ12A conduct and the fuse open,
        # instead of the TVS failing or 24 V reaching the TPS2595 (20 V abs max). Load ~1.6-2.6 A (ADR-0018).
        j1 = part("DC_Jack", "J1", "12V IN", "Connector_BarrelJack:BarrelJack_CUI_PJ-063AH_Horizontal", "PJ-063AH")
        v12in = power("+12V_IN")
        j1["+"] += v12in; j1["SLEEVE"] += gnd; j1["SW"] += NC
        f1 = part("Fuse", "F1", "4A fast", "Fuse:Fuse_Littelfuse-NANO2-451_453", "0451004.MRL")
        f1[1] += v12in; f1[2] += v12raw
        # AO4407A: drain at the fuse, source to the load, gate to GND via 10k; the body diode conducts first, then
        # Vgs = -12 V turns it on. Reversed brick: body diode blocks, Vgs = 0. BZT52C12 clamps Vgs (AO4407A +-25 V).
        q1 = part("PMOS_SO8", "Q1", "AO4407A", "Package_SO:SOIC-8_3.9x4.9mm_P1.27mm", "AO4407A")
        q1["D"] += v12raw; q1["S"] += v12p
        qg = Net("Q1_G"); q1["G"] += qg
        R("10k", qg, gnd)
        dz = part("Diode", "D1", "BZT52C12", "Diode_SMD:D_SOD-123", "BZT52C12"); dz["K"] += v12p; dz["A"] += qg
        # SMBJ12A: VRWM 12 V, VBR >= 13.3 V, VC 19.9 V at IPP, inside the TPS2595 20 V absolute maximum
        dt = part("TVS", "D2", "SMBJ12A", "Diode_SMD:D_SMB", "SMBJ12A"); dt["K"] += v12p; dt["A"] += gnd
        CP("100u 25V", v12p, gnd, "ALU_100u_25V", "Capacitor_SMD:CP_Elec_6.3x5.4")
        efuse("U1", "TPS259541DSGR", v12p, v12, R_ILM["input"], uvlo12("U1"), pwr_flt)
        C("10u 25V", v12, gnd); CP("100u 25V", v12, gnd, "ALU_100u_25V", "Capacitor_SMD:CP_Elec_6.3x5.4")
        R("10k", v3, pwr_flt)
        # chassis (XLR pin 1 and shells, rear panel) bonds to GND once, here at the power entry
        nt = part("NetTie", "NT1", "GND-CHASSIS", "NetTie:NetTie-2_SMD_Pad2.0mm", "R_0402_0R")
        nt[1] += gnd; nt[2] += chassis

        # ---- +5 V: TPS62933 per its 5 V / 3 A reference design (SLUSEA4D Figure 10-1) ----
        u2 = part("TPS62933", "U2", "TPS62933DRLR", "Package_TO_SOT_SMD:SOT-583-8", "TPS62933DRLR")
        sw, bst, fb, ss, en2 = Net("BUCK_SW"), Net("BUCK_BST"), Net("BUCK_FB"), Net("BUCK_SS"), Net("BUCK_EN")
        u2["VIN"] += v12; u2["GND"] += gnd; u2["SW"] += sw; u2["BST"] += bst; u2["FB"] += fb; u2["SS"] += ss
        u2["EN"] += en2; u2["RT"] += NC                       # RT floating = 500 kHz
        R("511k", v12, en2); R("88.7k", en2, gnd)             # start ~8 V (reference design R1/R2)
        C("33n", ss, gnd)                                     # 5 ms soft start (>= 6.8 nF required)
        C("100n", bst, sw)
        for _ in range(2):
            C("10u 25V", v12, gnd)
        C("100n", v12, gnd)
        lb = part("L", "L1", "6.8u", "Inductor_SMD:L_Bourns_SRP5030T", "IND_6u8_4A"); lb[1] += sw; lb[2] += v5
        R("53.6k", v5, fb); R("10.2k", fb, gnd)               # 0.8 x (1 + 53.6/10.2) = 5.00 V
        for _ in range(2):
            C("22u 25V", v5, gnd)
        C("100n", v5, gnd)
        # ---- +3V3 for the SC16IS752s and the pull-ups (TLV76733, as hw/rx) ----
        u3 = part("TLV76733", "U3", "TLV76733", "Package_SO:HVSSOP-8-1EP_3x3mm_P0.65mm_EP1.57x1.89mm", "TLV76733DGNR")
        u3["IN"] += v5; u3["EN"] += v5; u3["GND"] += gnd; u3["PAD"] += gnd; u3["OUT"] += v3; u3["SNS"] += v3
        u3["NC"] += NC
        C("1u", v5, gnd); C("10u", v3, gnd)
        # ---- CM4 IO board feed: its own eFuse (1.5 A; CM4IO datasheet budgets 9 W for the CM4) to a JST VH ----
        v12h = Net("+12V_HOST")
        efuse("U12", "TPS259541DSGR", v12, v12h, R_ILM["cm4"], uvlo12("U12"), pwr_flt)
        j5 = part("Conn_01x02", "J5", "CM4IO 12V", "Connector_JST:JST_VH_B2P-VH_1x02_P3.96mm_Vertical", "B2P-VH")
        j5[1] += v12h; j5[2] += gnd
        for n in (v12p, v12, v5, v3, v12h, pwr_flt, gnd, gnd):
            tp(n)

    with Group("host"):
        # ---- ribbon header to the CM4IO J8 (pin n to pin n). The CM4IO's own 3V3/5V pins stay unconnected here ----
        j2 = part("Conn_Host40", "J2", "CM4IO J8", "Connector_IDC:IDC-Header_2x20_P2.54mm_Vertical", "SBH11-PBPC-D20-ST-BK")
        used = set(HOST.values()) | {g for v in SLOT_UART.values() for g in v if g.startswith("GPIO")}
        for n, name in symbols_rack.HOST_HEADER.items():
            # spare CM4 GPIOs (0/1 = HAT ID EEPROM, 2/3, 7, 10, 11, 16) and the CM4IO's own 3V3/5V: no connection
            j2[str(n)] += gnd if name == "GND" else host(name) if name in used else NC
        spi = {k: host(v) for k, v in HOST.items() if k.startswith("SPI1")}
        # ---- two SC16IS752 on SPI1 (CE0 -> U4, CE1 -> U5), 14.7456 MHz crystal each ----
        uart = {}
        for rf, ce, irq in (("U4", "SPI1_CE0", "IRQ_U4"), ("U5", "SPI1_CE1", "IRQ_U5")):
            u = part("SC16IS752", rf, "SC16IS752IPW", "Package_SO:TSSOP-28_4.4x9.7mm_P0.65mm", "SC16IS752IPW,128")
            uart[rf] = u
            u["VDD"] += v3; u["VSS"] += gnd; u["I2C/~{SPI}"] += gnd          # SPI mode
            u["~{CS}/A0"] += spi[ce]; u["SI/A1"] += spi["SPI1_MOSI"]; u["SO"] += spi["SPI1_MISO"]
            u["SCL/SCLK"] += spi["SPI1_SCLK"]; u["SDA"] += gnd                # SDA to VSS in SPI mode (Table 2)
            u["~{IRQ}"] += host(HOST[irq]); R("1k", v3, host(HOST[irq]))   # Table 2: 1 kOhm pull-up at 3.3 V
            rst = Net(f"{rf}_RST"); u["~{RESET}"] += rst; R("10k", v3, rst); C("100n", rst, gnd)
            x1, x2 = Net(f"{rf}_XTAL1"), Net(f"{rf}_XTAL2"); u["XTAL1"] += x1; u["XTAL2"] += x2
            y = part("Crystal", "Y1" if rf == "U4" else "Y2", "14.7456M", "Crystal:Crystal_SMD_3225-4Pin_3.2x2.5mm",
                     "CX3225GB14745P0HPQCC")
            y[1] += x1; y[2] += x2; C("22p", x1, gnd); C("22p", x2, gnd)
            u["~{CTSA}"] += gnd; u["~{CTSB}"] += gnd; u["~{RTSA}"] += NC; u["~{RTSB}"] += NC
            C("100n", v3, gnd)
        for k in ("SPI1_SCLK", "SPI1_MOSI", "SPI1_MISO", "SPI1_CE0", "SPI1_CE1", "IRQ_U4", "IRQ_U5"):
            tp(host(HOST[k]))
        tp(gnd)

    def ufl(rf, value, sig):
        j = part("UFL", rf, value, "Connector_Coaxial:U.FL_Hirose_U.FL-R-SMT-1_Vertical", "U.FL-R-SMT-1(10)")
        j["RF"] += sig; j["GND"] += gnd
        return j

    tree = wilkinson.build_tree()[2]
    w70, lq = tree["w70_m"] * 1e3, tree["lq_m"] * 1e3
    rf_out = {}
    for ant, bnc, lna, flt, efb in (("A", "J3", "U6", "U8", "U10"), ("B", "J4", "U7", "U9", "U11")):
        with Group(f"rf_{ant.lower()}"):
            # ---- antenna input: BNC -> ESD103 (+-15 V, 0.09 pF: survives the 12 V bias) -> bias-T -> DC block ----
            ant_n, bias_rf, bias_dc = Net(f"ANT_{ant}"), Net(f"BIAS_{ant}_RF"), Net(f"BIAS_{ant}_DC")
            # TE 5415025-1: right-angle PCB BNC, 50 ohm 4 GHz, 1/2-28 bulkhead thread (#34: replaces Amphenol 112487,
            # whose drawing could not be read; TE drawing C-5415025 rev A2, panel up to 4.6 mm, so the 3.18 mm panel fits)
            j = part("BNC", bnc, f"ANT {ant}", "openpack:BNC_TE_5415025-1_RA", "5415025-1")
            j["IN"] += ant_n; j["SHIELD"] += gnd
            e1 = part("ESD_Bidir", ref("D"), "ESD103-B1-02EL", "Diode_SMD:D_0402_1005Metric", "ESD103-B1-02EL")
            e1[1] += ant_n; e1[2] += gnd
            lc = part("L", ref("L"), "39n", "Inductor_SMD:L_0603_1608Metric", "LQW18AN39NG80D")   # choke, SRF 3.28 GHz
            lc[1] += ant_n; lc[2] += bias_rf
            C("100p", bias_rf, gnd); C("10n", bias_rf, gnd)
            # 1 ohm 2512 (1 W): damps the choke and limits surge into the clamp; at the 0.52 A worst-case eFuse limit
            # (shorted antenna or cable) it dissipates 0.27 W, 27 % of its rating (an 0402 would open at 79 mA)
            R("1", bias_rf, bias_dc, "R_2512_1R_1W", fp="Resistor_SMD:R_2512_6332Metric")
            tv = part("TVS", ref("D"), "SMF12A", "Diode_SMD:D_SOD-123F", "SMF12A"); tv["K"] += bias_dc; tv["A"] += gnd
            # bias eFuse: off unless the host sets BIAS_x_EN (100k pull-down); 0.49 A limit protects a shorted
            # (DC-grounded) passive antenna or cable; FLT to the host
            en = host(HOST[f"BIAS_{ant}_EN"]); R("100k", en, gnd)
            fl = host(HOST[f"BIAS_{ant}_FLT"]); R("10k", v3, fl)
            efuse(efb, "TPS259541DSGR", v12, bias_dc, R_ILM["bias"], en, fl)
            tp(bias_dc)
            # ---- LNA: QPL9057 per its EVB (datasheet Rev. F): 100 pF blocks, 18 nH choke on RF out, R4 5.1k bias ----
            lna_in, rf_in, rf_o, lna_out = Net(f"LNA_{ant}_IN"), Net(f"LNA_{ant}_RFIN"), Net(f"LNA_{ant}_RFOUT"), Net(f"LNA_{ant}_OUT")
            C("100p", ant_n, lna_in)                          # DC block (EVB C1): the LNA input never sees the bias
            e2 = part("ESD_Bidir", ref("D"), "ESD101-B1-02EL", "Diode_SMD:D_0402_1005Metric", "ESD101-B1-02EL")
            e2[1] += lna_in; e2[2] += gnd                     # 2nd stage at 0 V DC, 0.1 pF (HBM class 1B LNA)
            R("0", lna_in, rf_in, "R_0402_0R")                # EVB R3 position: input-match pad for #34 tuning
            v5l, vb = power(f"+5V_LNA_{ant}"), Net(f"LNA_{ant}_VBIAS")
            fbd = part("L", ref("FB"), "600R@100M", "Inductor_SMD:L_0603_1608Metric", "FB_0603_600R")
            fbd[1] += v5; fbd[2] += v5l
            C("10u", v5l, gnd); C("1u", v5l, gnd); C("100p", v5l, gnd)
            tp(v5l)
            u = part("QPL9057", lna, "QPL9057", "Package_DFN_QFN:DFN-8-1EP_2x2mm_P0.5mm_EP0.9x1.6mm", "QPL9057TR7")
            u["RF_IN"] += rf_in; u["RF_OUT"] += rf_o; u["GND"] += gnd
            u["SD"] += gnd                                    # always on (datasheet note 5, FDD)
            for p in ("NC3", "NC4", "NC5", "NC8"):
                u[p] += gnd                                   # "provide grounded land pads"
            u["VBIAS"] += vb; R("5.1k", v5l, vb); C("100p", vb, gnd)   # EVB R4 / C7: 50 mA at 5 V
            lch = part("L", ref("L"), "18n", "Inductor_SMD:L_0402_1005Metric", "0402CS-18NXG")
            lch[1] += v5l; lch[2] += rf_o
            C("100p", rf_o, lna_out)                          # EVB C2
            # ---- band-pass: QPQ1907 BAW (2402.5-2481.5 MHz), after the LNA so its loss barely touches NF ----
            spl = Net(f"SPL_{ant}_IN")
            f = part("QPQ1907", flt, "QPQ1907", "openpack:Qorvo_QPQ1907_LGA5_1.4x1.2mm_datasheet_land_pattern", "QPQ1907SR")
            f["RF_IN"] += lna_out; f["RF_OUT"] += spl
            for p in ("GND2", "GND3", "GND5"):
                f[p] += gnd
            # ---- 1:8 Wilkinson (3 stages, 7 dividers): 70.7 ohm lambda/4 arms + 100 ohm thin-film resistor ----
            heads = [spl]
            for stage in range(3):
                nxt = []
                for i, h in enumerate(heads):
                    arms = []
                    for side in "ab":
                        e = Net(f"WK_{ant}_{stage + 1}{i}{side}")
                        tl = part("TL", ref("TL"), f"70R7 L/4 {lq:.2f}mm w{w70:.3f}", "openpack:Microstrip_NetTie",
                                  "PCB_TRACE")
                        tl[1] += h; tl[2] += e
                        arms.append(e)
                    R("100", arms[0], arms[1], "R_0402_100R_TF")
                    nxt += arms
                heads = nxt
            rf_out[ant] = heads                               # 8 arm ends, 50 ohm onwards to the u.FL ports

    with Group("slots"):
        for k in range(N_SLOTS):
            # ---- ADR-0014 socket: BOOMELE 2x13 2.54 mm female, 8.5 mm (LCSC C64320, coordinator pick on #34; the
            # factory-keyed Samtec SSW-113-01-G-D-14 is the drop-in alternative). The footprint has NO hole at 14, so the
            # socket cannot be soldered until its contact 14 is pulled, and the empty cavity is then plugged (a cut header
            # pin, glued) so a receiver turned 180 deg cannot go in (#116 review S1, hw/REVIEW.md assembly step) ----
            js = part("Conn_Slot", f"J{10 + k}", f"SLOT {k}", "openpack:PinSocket_2x13_P2.54mm_Key14", "2.54-2*13PFemale")
            v12s, v5s = power(f"+12V_S{k}"), power(f"+5V_S{k}")
            s = {name: Net(f"S{k}_{name}") for name in set(symbols_rack.BACKPLANE.values())
                 if name not in ("GND", "+12V", "+5V", "KEY") and not name.startswith(("BP_I2S", "BP_SLOT"))}
            fixed = {"GND": gnd, "+12V": v12s, "+5V": v5s, "KEY": NC,
                     # I2S: not driven (sub-board R33-R35 DNP), no main-board stub next to the splitters
                     "BP_I2S_BCK": NC, "BP_I2S_LRCK": NC, "BP_I2S_SDOUT": NC}
            for b in range(3):                                # slot ID: bit 0 -> GND, 1 -> open (sub-board 10k up)
                fixed[f"BP_SLOT{b}"] = NC if (k >> b) & 1 else gnd
            for num, name in symbols_rack.BACKPLANE.items():
                js[str(num)] += fixed[name] if name in fixed else s[name]
            # ---- per-slot current limit: a shorted sub-board trips its own eFuses, the other seven keep running ----
            efuse(f"U{20 + k}", "TPS259541DSGR", v12, v12s, R_ILM["slot"], uvlo12(f"U{20 + k}"), pwr_flt)
            efuse(f"U{30 + k}", "TPS259531DSGR", v5, v5s, R_ILM["slot"], v5, pwr_flt)   # EN to IN: < 6 V allowed
            for n in (v12s, v5s, s["BP_UART_TX"], s["BP_UART_RX"], s["BP_nRESET"]):
                tp(n)
            # ---- UART + control to the host ----
            tx, rx = SLOT_UART[k]
            if tx.startswith("GPIO"):
                R("100", host(tx), s["BP_UART_RX"])           # CM4 TXD -> module RX (+ sub-board 1k): damping
                R("1k", s["BP_UART_TX"], host(rx))            # module TX -> CM4 RXD: limits back-feed into an off CM4
            else:
                u = uart[tx]
                u[f"TX{rx}"] += s["BP_UART_RX"]; u[f"RX{rx}"] += s["BP_UART_TX"]
            uc, g_rst, g_boot = SLOT_CTRL[k]
            uart[uc][f"GPIO{g_rst}"] += s["BP_nRESET"]; uart[uc][f"GPIO{g_boot}"] += s["BP_BOOT"]
            # ---- front LEDs (RK-4): module GPIO (100 R on the sub-board) -> 560 R -> LED -> GND, ~2 mA. Side-view
            # (right-angle) LEDs at the main board's front edge shine straight through the front-panel holes (#34) ----
            for sig, col in (("BP_LED_LOCK", "GREEN"), ("BP_LED_PEAK", "RED")):
                a = Net(f"S{k}_{sig}_A")
                R("560", s[sig], a)
                d = part("LED", ref("D"), col.lower(), "openpack:LED_LiteOn_LTST-S270",
                         {"GREEN": LED_MPN["green"], "RED": LED_MPN["red"]}[col])
                d["A"] += a; d["K"] += gnd
            # ---- XLR male (RX-8): pin 2 hot, 3 cold, 1 + shell to chassis; SMAJ58CA (VRWM 58 V >= P48 52 V max) ----
            jx = part("XLR3_Male", f"J{20 + k}", f"OUT {k + 1}", "openpack:Neutrik_NC3MAH", "NC3MAH")
            jx["HOT"] += s["AUD_HOT"]; jx["COLD"] += s["AUD_COLD"]; jx["PIN1"] += chassis; jx["SHELL"] += chassis
            for leg in ("AUD_HOT", "AUD_COLD"):
                t = part("ESD_Bidir", ref("D"), "SMAJ58CA", "Diode_SMD:D_SMA", "SMAJ58CA")
                t[1] += s[leg]; t[2] += chassis
            # ---- RF to the sub-board: one u.FL per tree; U.FL cables to the sub-board's J3 (A) and J4 (B) ----
            for ant, base in (("A", 30), ("B", 40)):
                o = Net(f"RF_{ant}{k}")
                tl = part("TL", ref("TL"), "50R feed", "openpack:Microstrip_NetTie", "PCB_TRACE")
                tl[1] += rf_out[ant][k]; tl[2] += o
                ufl(f"J{base + k}", f"RF {ant}{k}", o)


def bom_rows(circuit):
    groups, vals = {}, {}
    for p in circuit.parts:   # passives: one row per value; others one row per MPN (connector values are labels)
        mpn = p.fields.get("MPN", "")
        passive = p.ref.rstrip("0123456789") in ("R", "C", "L", "TL")
        groups.setdefault((mpn, p.value if passive else vals.setdefault(mpn, p.value)), []).append(p.ref)

    def key(r):
        return (r.rstrip("0123456789"), int("0" + r.lstrip("ABCDEFGHIJKLMNOPQRSTUVWXYZ")))

    def row(refs, qty, val, mpn, gbp, brk, src, uk):
        return {"refs": refs, "qty": qty, "value": val, "mpn": mpn, "unit_gbp": f"{gbp:.3f}",
                "ext_gbp": f"{gbp * qty:.2f}", "qty_break": brk, "uk_distributor": uk, "source": src}

    rows = []
    for (mpn, val), refs in sorted(groups.items(), key=lambda kv: key(sorted(kv[1], key=key)[0])):
        rows.append(row(" ".join(sorted(refs, key=key)), len(refs), val, mpn, *prices.PRICES[mpn]))
    for item, qty, gbp, src, uk in prices.EXTRAS:
        rows.append(row("-", qty, item, "-", gbp, 1, src, uk))
    return rows


def normalise_netlist(text):
    """SKiDL stamps the build date and lists the hierarchy sheets in an order that varies between Python builds
    (CI 3.12 vs local 3.13). Blank the date and sort the sheet entries by name, renumbering them."""
    text = re.sub(r'\(date "[^"]*"\)', '(date "")', text)
    head, rest = text.split("\n    (sheet\n", 1)
    sheets_txt, tail = rest.split("\n  (components", 1)
    sheets = sheets_txt.split("\n    (sheet\n")
    sheets[-1] = sheets[-1][:-1]                     # the last sheet carries the ")" closing (design ...)
    sheets.sort(key=lambda s: re.search(r'\(name "([^"]*)"\)', s).group(1))
    sheets = [re.sub(r"\(number \d+\)", f"(number {i + 1})", s, count=1) for i, s in enumerate(sheets)]
    return head + "\n    (sheet\n" + "\n    (sheet\n".join(sheets) + ")" + "\n  (components" + tail


def erc():
    """Run SKiDL ERC on the built circuit; return (errors, warnings) counted by ERC alone (as hw/rx/rx.py)."""
    import skidl
    from skidl.logger import active_logger
    seen, report = {}, active_logger.report_summary
    active_logger.report_summary = lambda phase: (
        seen.setdefault(phase, (active_logger.error.count, active_logger.warning.count)), report(phase))
    try:
        skidl.ERC()
    finally:
        active_logger.report_summary = report
    return seen["running ERC"]


def main(argv):
    import builtins, os, skidl
    OUT.mkdir(exist_ok=True)
    os.chdir(OUT)  # SKiDL drops .log/.erc/_sklib.py files in the cwd
    build()
    errs, warns = erc()
    (OUT / "erc.txt").write_text(f"SKiDL ERC: {errs} errors, {warns} warnings\n")
    print(f"ERC: {errs} errors, {warns} warnings")
    skidl.generate_netlist(file_=str(OUT / "backplane.net"))
    net = OUT / "backplane.net"   # make it reproducible so CI's stale-output diff is meaningful:
    net.write_text(normalise_netlist(net.read_text()))
    rows = bom_rows(builtins.default_circuit)
    with open(OUT / "bom.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    print(f"BOM total GBP {sum(float(r['ext_gbp']) for r in rows):.2f} per rack main board + host + cables")
    if "--no-sch" not in argv:
        opts = dict(top_name="backplane", title="OpenPack rack main board", flatness=0, auto_stub=True)
        skidl.generate_schematic(filepath=str(OUT / "sch"), **opts)
        skidl.generate_schematic(filepath=str(OUT / "svg"), format="svg", **opts)
    return errs + warns


if __name__ == "__main__":
    sys.exit(1 if main(sys.argv[1:]) else 0)
