"""OpenPack body-pack schematic (SPEC PK-1..PK-6, PK-8, PK-9) in SKiDL.

Run:  python hw/pack/pack.py            -> ERC, then writes in hw/pack/out/:
        pack.net (KiCad netlist), bom.csv (PK-12, read by audit.py), erc.txt,
        sch/pack.kicad_sch (KiCad 9 schematic), svg/ (rendered pages)
      python hw/pack/pack.py --no-sch    -> netlist/BOM/ERC only (fast)

Design choices live in ADR-0006 (front end), ADR-0007 (module) and ADR-0012 (this board).
"""
import csv, pathlib, sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import symbols, prices  # noqa: E402

OUT = HERE / "out"
LIB = HERE / "openpack.kicad_sym"


def build():
    import builtins
    from skidl import KICAD9, Group, Net, Part, POWER, lib_search_paths, set_default_tool, reset
    reset()
    set_default_tool(KICAD9)
    NC = builtins.NC  # SKiDL no-connect net (rebound by reset())
    symbols.write_lib(LIB)
    if str(HERE) not in lib_search_paths[KICAD9]:
        lib_search_paths[KICAD9].append(str(HERE))

    def part(sym, ref, value, fp, mpn):
        p = Part("openpack", sym, ref=ref, value=value, footprint=fp, tag=ref)
        p.fields["MPN"] = mpn
        return p

    R0402, C0402 = "Resistor_SMD:R_0402_1005Metric", "Capacitor_SMD:C_0402_1005Metric"
    C0805, C1206 = "Capacitor_SMD:C_0805_2012Metric", "Capacitor_SMD:C_1206_3216Metric"
    AUD = (C1206, "C_10u_1206_X7R")  # audio-path coupling caps, 16 V 1206 (less DC-bias loss)

    def R(ref, val, a, b):
        r = part("R", ref, val, R0402, "R_0402_1%"); r[1] += a; r[2] += b; return r

    def C(ref, val, a, b, fp=C0402, mpn=None):
        mpn = mpn or {"100n": "C_100n_0402", "1u": "C_1u_0402", "100p": "C_100p_0402_C0G",
                      "10u": "C_10u_0603_X5R"}[val]
        if mpn == "C_10u_0603_X5R":
            fp = "Capacitor_SMD:C_0603_1608Metric"
        c = part("C", ref, val, fp, mpn); c[1] += a; c[2] += b; return c

    gnd = Net("GND"); gnd.drive = POWER
    v5, v5b, v3, v3a = Net("+5V"), Net("+5V_BIAS"), Net("+3V3"), Net("+3V3A")
    vbat, vbatf, vrp, vsys = Net("BAT+"), Net("BAT_F"), Net("VBAT_RP"), Net("VSYS")
    for n in (vbat, vsys, v5b):
        n.drive = POWER  # battery and switched/filtered rails are sources (PWR_FLAG equivalent)

    with Group("power"):  # one schematic sheet
        # ---- PK-6 power: 18650 -> PTC -> P-FET reverse-polarity -> slide switch -> VSYS ----
        bt = part("Battery_18650", "BT1", "18650 holder", "openpack:BH-18650-B1BA002", "BH-18650-B1BA002")
        bt["+"] += vbat; bt["-"] += gnd
        f1 = part("Polyfuse", "F1", "0.5A hold", "Fuse:Fuse_1206_3216Metric", "MF-PSMF050X-2"); f1[1] += vbat; f1[2] += vbatf
        q1 = part("PMOS", "Q1", "DMG2305UX", "Package_TO_SOT_SMD:SOT-23", "DMG2305UX-7")
        q1["D"] += vbatf; q1["S"] += vrp          # body diode conducts only with the cell the right way round
        qg = Net("Q1_G"); q1["G"] += qg; R("R1", "100k", qg, gnd)
        sw = part("SW_SPDT", "SW1", "recessed slide", "Button_Switch_SMD:SW_SPDT_CK_JS102011SAQN", "JS102011SAQN")
        sw["COM"] += vrp; sw["A"] += vsys; sw["B"] += NC
        C("C1", "10u", vsys, gnd)

        # 5 V boost (preamp + mic bias + analog LDO): TPS61023, Vout = 0.595 V * (1 + 732k/100k) = 4.95 V
        u4 = part("TPS61023", "U4", "TPS61023", "Package_TO_SOT_SMD:SOT-563", "TPS61023DRLR")
        swn, fb = Net("BOOST_SW"), Net("BOOST_FB")
        u4["VIN"] += vsys; u4["EN"] += vsys; u4["GND"] += gnd; u4["SW"] += swn; u4["VOUT"] += v5; u4["FB"] += fb
        l1 = part("L", "L1", "1uH 4.7A", "Inductor_SMD:L_1008_2520Metric", "DFE252012F-1R0M=P2"); l1[1] += vsys; l1[2] += swn
        R("R2", "732k", v5, fb); R("R3", "100k", fb, gnd)
        for ref in ("C2", "C3"):
            C(ref, "22u", v5, gnd, C0805, "GRM21BR61A226ME51L")

        # Digital 3.3 V from the cell (module + PCM1840 IOVDD); analog 3.3 V from the 5 V rail (PCM1840 AVDD)
        u5 = part("TLV75533P", "U5", "TLV75533P", "Package_TO_SOT_SMD:SOT-23-5", "TLV75533PDBVR")
        u5["IN"] += vsys; u5["EN"] += vsys; u5["GND"] += gnd; u5["OUT"] += v3; u5["NC"] += NC
        C("C4", "1u", vsys, gnd); C("C5", "10u", v3, gnd)
        u6 = part("TLV75533P", "U6", "TLV75533P", "Package_TO_SOT_SMD:SOT-23-5", "TLV75533PDBVR")
        u6["IN"] += v5; u6["EN"] += v5; u6["GND"] += gnd; u6["OUT"] += v3a; u6["NC"] += NC
        C("C6", "1u", v5, gnd); C("C7", "1u", v3a, gnd)

        # Mic bias rail: RC filter 100 R + 47 uF (fc 34 Hz, -29 dB at 1 kHz) on the boost output (#31 review)
        R("R4", "100", v5, v5b)
        C("C8", "47u", v5b, gnd, C1206, "GRM31CR61A476ME15L")

    with Group("front_end"):  # one schematic sheet
        # ---- PK-1/PK-2/PK-3 front end (hw/spice/preamp.cir is the same circuit) ----
        j1 = part("Jack_TRS_Locking", "J1", "3.5mm locking", "openpack:SameSky_SJ1-3543", "SJ1-3543")
        mic, np_, vcm, inm, cg = Net("MIC"), Net("PRE_NP"), Net("VCM_2V5"), Net("PRE_INM"), Net("PRE_CG")
        j1["TIP"] += mic; j1["RING"] += gnd; j1["SLEEVE"] += gnd   # Sennheiser SK mic plug: tip = mic+, ring+sleeve = gnd
        C("C9", "100p", mic, gnd)                                 # 2.4 GHz rejection at the jack, C0G
        R("R5", "2.2k", v5b, mic)                                 # PK-1 bias 5 V via 2.2 kOhm
        C("C10", "10u", mic, np_, *AUD)
        R("R6", "100k", np_, vcm)
        R("R7", "100k", v5, vcm); R("R8", "100k", vcm, gnd); C("C11", "10u", vcm, gnd)
        u3 = part("OPA1656", "U3", "OPA1656", "Package_SO:SOIC-8_3.9x4.9mm_P1.27mm", "OPA1656IDR")
        outa, outb = Net("PRE_OUTA"), Net("PRE_OUTB")
        u3["+INA"] += np_; u3["-INA"] += inm; u3["OUTA"] += outa          # path 1: x2 (+6 dB), ADR-0006
        R("R9", "330", outa, inm); R("R10", "330", inm, cg)
        C("C12", "100u", cg, gnd, C1206, "GRM31CR60J107ME39L")
        u3["+INB"] += np_; u3["-INB"] += outb; u3["OUTB"] += outb          # path 2: x1 (0 dB), Q7, unused in v1 fw
        u3["V+"] += v5; u3["V-"] += gnd
        C("C13", "100n", v5, gnd); C("C14", "10u", v5, gnd)

    with Group("adc"):  # one schematic sheet
        # ---- PCM1840: I2S slave (MSZ=0), I2S 2-ch (FMT1=FMT0=1), low-latency filter (MD0=1), DRE on (MD1=1) ----
        u2 = part("PCM1840", "U2", "PCM1840", "Package_DFN_QFN:WQFN-24-1EP_4x4mm_P0.5mm_EP2.6x2.6mm", "PCM1840IRTWR")
        in1p, in1m, in2p, in2m = Net("ADC_IN1P"), Net("ADC_IN1M"), Net("ADC_IN2P"), Net("ADC_IN2M")
        C("C15", "10u", outa, in1p, *AUD); C("C16", "10u", in1m, gnd, *AUD)   # pseudo-differential: INxM AC-grounded
        C("C17", "10u", outb, in2p, *AUD); C("C18", "10u", in2m, gnd, *AUD)
        u2["IN1P"] += in1p; u2["IN1M"] += in1m; u2["IN2P"] += in2p; u2["IN2M"] += in2m
        for p in ("IN3P", "IN3M", "IN4P", "IN4M", "MICBIAS"):
            u2[p] += NC                                       # unused; left open (no-connect flag in layout)
        u2["AVDD"] += v3a; u2["AVSS"] += gnd; u2["VSS(EP)"] += gnd; u2["IOVDD"] += v3
        areg, vref, dreg = Net("ADC_AREG"), Net("ADC_VREF"), Net("ADC_DREG")
        u2["AREG"] += areg; u2["VREF"] += vref; u2["DREG"] += dreg
        C("C19", "1u", v3a, gnd); C("C20", "100n", v3a, gnd)
        C("C21", "10u", areg, gnd); C("C22", "100n", areg, gnd)
        C("C23", "1u", vref, gnd)
        C("C24", "10u", dreg, gnd); C("C25", "100n", dreg, gnd)
        C("C26", "10u", v3, gnd); C("C27", "100n", v3, gnd)
        u2["MSZ"] += gnd
        for p in ("FMT1", "FMT0", "MD0", "MD1"):
            u2[p] += v3
        i2s_sck, i2s_lrck, i2s_sdin, shdnz = Net("I2S_BCLK"), Net("I2S_FSYNC"), Net("I2S_SDOUT"), Net("ADC_SHDNZ")
        u2["BCLK"] += i2s_sck; u2["FSYNC"] += i2s_lrck; u2["SDOUT"] += i2s_sdin; u2["SHDNZ"] += shdnz
        R("R11", "100k", shdnz, gnd)                              # ADC held in shutdown until firmware releases it

    with Group("mcu_usb"):  # one schematic sheet
        # ---- PK-4 module: BT40NE. VDD = VDDH = 3.3 V (nRF5340 normal-voltage mode) ----
        u1 = part("BT40NE", "U1", "BT40NE", "openpack:Fanstel_BT40NE", "BT40NE")
        u1["9"] += v3; u1["F4"] += v3
        for p in ("10", "A0", "B0", "C0", "D0", "H0", "H1", "H2", "H3"):
            u1[p] += gnd
        C("C28", "10u", v3, gnd); C("C29", "100n", v3, gnd)
        pins = {"C3": i2s_sck, "C4": i2s_lrck, "C5": i2s_sdin, "D5": shdnz}   # I2S on free GPIO (nRF5340 PSEL)
        vsense = Net("VBAT_SENSE")
        R("R12", "1M", vsys, vsense); R("R13", "1M", vsense, gnd); C("C30", "100n", vsense, gnd)
        pins["5"] = vsense                                        # P0.04/AIN0: battery voltage (PK-8, PK-10)
        leds = [("D1", "Z0", "green BAT", "LED_BAT_OK"), ("D2", "Z1", "red BAT LOW", "LED_BAT_LOW"),
                ("D3", "Z2", "amber PEAK", "LED_PEAK"), ("D4", "Z3", "red CLIP", "LED_CLIP")]
        for i, (ref, pad, val, name) in enumerate(leds):          # PK-8: GPIO -> 1k -> LED -> GND
            g, a = Net(name), Net(name + "_A")
            pins[pad] = g
            R(f"R{14 + i}", "1k", g, a)
            d = part("LED", ref, val, "LED_SMD:LED_0603_1608Metric", "LED_0603"); d["A"] += a; d["K"] += gnd
        # PK-9 USB-C: config + MCUboot serial DFU over the module's USB (not a charging port)
        j2 = part("USB_C_2.0", "J2", "USB-C", "Connector_USB:USB_C_Receptacle_GCT_USB4105-xx-A_16P_TopMnt_Horizontal", "USB4105-GF-A")
        vbus, dp, dn, cc1, cc2 = Net("USB_VBUS"), Net("USB_D+"), Net("USB_D-"), Net("USB_CC1"), Net("USB_CC2")
        vbus.drive = POWER
        j2["A4"] += vbus; j2["B4"] += vbus; j2["A6"] += dp; j2["B6"] += dp; j2["A7"] += dn; j2["B7"] += dn
        j2["A5"] += cc1; j2["B5"] += cc2; j2["A1"] += gnd; j2["B1"] += gnd; j2["S1"] += gnd
        j2["A8"] += NC; j2["B8"] += NC
        R("R18", "5.1k", cc1, gnd); R("R19", "5.1k", cc2, gnd)   # UFP Rd: host supplies 5 V, draws < 100 mA
        u7 = part("USBLC6-2SC6", "U7", "USBLC6-2SC6", "Package_TO_SOT_SMD:SOT-23-6", "USBLC6-2SC6")
        u7["1"] += dp; u7["6"] += dp; u7["3"] += dn; u7["4"] += dn; u7["5"] += vbus; u7["2"] += gnd
        u1["E4"] += dp; u1["E5"] += dn; u1["F6"] += vbus
        C("C31", "1u", vbus, gnd)
        # SWD (Tag-Connect pads) and UART test pads
        j3 = part("Tag_TC2030", "J3", "SWD", "Connector:Tag-Connect_TC2030-IDC-NL_2x03_P1.27mm_Vertical", "TC2030-pads")
        swdio, swclk, nrst = Net("SWDIO"), Net("SWDCLK"), Net("nRESET")
        j3["VTREF"] += v3; j3["SWDIO"] += swdio; j3["~{RESET}"] += nrst; j3["SWDCLK"] += swclk; j3["GND"] += gnd
        j3["SWO"] += NC
        u1["16"] += swdio; u1["15"] += swclk; u1["14"] += nrst
        for ref, pad, name in (("TP1", "B1", "UART_TX"), ("TP2", "C1", "UART_RX")):
            n = Net(name); pins[pad] = n
            tp = part("TestPoint", ref, name, "TestPoint:TestPoint_Pad_D1.0mm", "TP-pad"); tp[1] += n
        for pad, net in pins.items():
            u1[pad] += net
        # every other module pad (spare GPIO, NC, FEM-internal) gets its own unconnected net
        for p in u1.pins:
            if not p.net:
                p += NC


def bom_rows(circuit):
    groups = {}
    for p in circuit.parts:
        mpn = p.fields.get("MPN", "")
        key = (mpn, p.value)
        groups.setdefault(key, []).append(p.ref)
    rows = []
    for (mpn, val), refs in sorted(groups.items(), key=lambda kv: sorted(kv[1])[0]):
        unit, src = prices.PRICES[mpn]
        rows.append({"refs": " ".join(sorted(refs, key=lambda r: (r.rstrip("0123456789"), int("0" + r.lstrip("ABCDEFGHIJKLMNOPQRSTUVWXYZ"))))),
                     "qty": len(refs), "value": val, "mpn": mpn, "unit_usd": f"{unit:.2f}",
                     "ext_usd": f"{unit * len(refs):.2f}", "source": src})
    for item, qty, unit, src in prices.EXTRAS:
        rows.append({"refs": "-", "qty": qty, "value": item, "mpn": "-", "unit_usd": f"{unit:.2f}",
                     "ext_usd": f"{unit * qty:.2f}", "source": src})
    return rows


def main(argv):
    import builtins, os, skidl
    from skidl.logger import active_logger
    OUT.mkdir(exist_ok=True)
    os.chdir(OUT)  # SKiDL drops .log/.erc/_sklib.py files in the cwd
    build()
    seen, report = {}, active_logger.report_summary   # read ERC's own counters before it restores the logger
    active_logger.report_summary = lambda phase: (seen.setdefault(phase, (active_logger.error.count, active_logger.warning.count)), report(phase))
    skidl.ERC()
    active_logger.report_summary = report
    errs, warns = seen["running ERC"]
    (OUT / "erc.txt").write_text(f"SKiDL ERC: {errs} errors, {warns} warnings\n")
    print(f"ERC: {errs} errors, {warns} warnings")
    skidl.generate_netlist(file_=str(OUT / "pack.net"))
    rows = bom_rows(builtins.default_circuit)
    with open(OUT / "bom.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    print(f"BOM total ${sum(float(r['ext_usd']) for r in rows):.2f} ex. cell")
    if "--no-sch" not in argv:
        skidl.generate_schematic(filepath=str(OUT / "sch"), top_name="pack", title="OpenPack body-pack")
        skidl.generate_schematic(filepath=str(OUT / "svg"), top_name="pack", title="OpenPack body-pack", format="svg")
    return errs


if __name__ == "__main__":
    sys.exit(1 if main(sys.argv[1:]) else 0)
