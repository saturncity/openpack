"""OpenPack receiver sub-board schematic (SPEC RX-1, RX-8; ADR-0014) in SKiDL. One per pack, eight per rack.

Run:  python hw/rx/rx.py            -> ERC, then writes in hw/rx/out/:
        rx.net (KiCad netlist), bom.csv (read by audit.py), erc.txt,
        sch/rx.kicad_sch (KiCad 9 schematic), svg/ (rendered pages)
      python hw/rx/rx.py --no-sch    -> netlist/BOM/ERC only (fast)

Blocks: BT40NE module (ADR-0007), PE4259 antenna A/B switch into the module u.FL (RX-1, RX-5),
PCM5102A DAC (I2S), OPA1656 balanced line driver on +12 V (RX-8, hw/spice/rx_driver.cir is the
same circuit), backplane connector (power, UART, I2S, balanced audio; pinout in ADR-0014).
"""
import csv, importlib.util, pathlib, sys

HERE = pathlib.Path(__file__).resolve().parent


def _load(name, path):  # by path, under unique names: hw/pack/pack.py imports its own "prices"/"symbols"
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


symbols_rx = _load("hw_rx_symbols", HERE / "symbols_rx.py")
prices = _load("hw_rx_prices", HERE / "prices.py")

OUT = HERE / "out"
LIB = HERE / "openpack_rx.kicad_sym"

# Module pad -> nRF5340 GPIO used on this board (Fanstel BT40/F/E/N/NE spec v1.08, Pin Functions; see
# hw/pack/symbols.py). Firmware devicetree for the rx board must match (ADR-0014).
PADS = {
    "UART_TX": ("C5", "P0.20"),    # = nrf5340dk uart0 TX (zephyr,console), nrf5340_cpuapp_common-pinctrl.dtsi
    "UART_RX": ("D5", "P0.22"),    # = nrf5340dk uart0 RX; RTS/CTS unused (P0.21 is an nRF21540 pad in the BT40NE)
    "I2S_BCK": ("C3", "P0.24"),    # I2S SCK_M, same pad as the pack (ADR-0012)
    "I2S_LRCK": ("C4", "P0.23"),   # I2S LRCK_M, same pad as the pack
    "I2S_SDOUT": ("B6", "P0.13"),  # I2S SDOUT (pack uses C5 for SDIN; C5 is the console TX here)
    "ANT_SEL": ("D6", "P1.01"),    # net core GPIO: op_rx_ant_select(0) -> low -> antenna A (ADR-0011/0014)
    "DAC_XSMT": ("B5", "P0.12"),   # PCM5102A soft mute, pulled low: muted until firmware un-mutes
    "LED_LOCK": ("Z0", "P1.09"),   # RK-4 front-panel lock LED (LED + resistor on the front board)
    "LED_PEAK": ("Z1", "P1.10"),   # RK-4 front-panel peak LED
    "BOOT": ("1", "P1.02"),        # MCUboot serial-recovery pin (FW-6 UART DFU), active low
    "SLOT0": ("Z2", "P1.11"),      # backplane slot strap, bit 0 (GND = 0)
    "SLOT1": ("Z3", "P1.12"),
    "SLOT2": ("Z4", "P1.13"),
}


def build():
    import builtins
    from skidl import KICAD9, Group, Net, Part, POWER, lib_search_paths, set_default_tool, reset
    reset()
    set_default_tool(KICAD9)
    NC = builtins.NC
    symbols_rx.write_lib(LIB)
    if str(HERE) not in lib_search_paths[KICAD9]:
        lib_search_paths[KICAD9].append(str(HERE))

    def part(sym, ref, value, fp, mpn):
        p = Part("openpack_rx", sym, ref=ref, value=value, footprint=fp, tag=ref)
        p.fields["MPN"] = mpn
        return p

    R0402, C0402, C0603 = "Resistor_SMD:R_0402_1005Metric", "Capacitor_SMD:C_0402_1005Metric", "Capacitor_SMD:C_0603_1608Metric"
    C1206 = "Capacitor_SMD:C_1206_3216Metric"

    def R(ref, val, a, b, fp=R0402, mpn="R_0402_1%"):
        r = part("R", ref, val, fp, mpn); r[1] += a; r[2] += b; return r

    def C(ref, val, a, b, fp=None, mpn=None):
        mpn = mpn or {"100n": "C_100n_0402", "1u": "C_1u_0402", "10u": "C_10u_0603_X5R", "2u2": "C_2u2_0603_X7R",
                      "2n2": "C_2n2_0402_C0G", "100p": "C_100p_0402_C0G", "10p": "C_10p_0402_C0G"}[val]
        fp = fp or (C0603 if mpn in ("C_10u_0603_X5R", "C_2u2_0603_X7R") else C0402)
        c = part("C", ref, val, fp, mpn); c[1] += a; c[2] += b; return c

    def CP(ref, val, pos, neg, mpn, fp):
        c = part("CP", ref, val, fp, mpn); c["+"] += pos; c["-"] += neg; return c

    gnd = Net("GND"); gnd.drive = POWER
    v12, v5, v12a, v3, v3a = Net("+12V"), Net("+5V"), Net("+12VA"), Net("+3V3"), Net("+3V3A")
    for n in (v12, v5, v12a):
        n.drive = POWER   # backplane rails and the RC-filtered driver rail are sources (PWR_FLAG equivalent)
    bp = {name: Net(name) for name in set(symbols_rx.BACKPLANE.values()) if not name.startswith(("GND", "+"))}

    with Group("power"):
        # ---- backplane connector (ADR-0014) + rail protection ----
        j1 = part("Conn_Backplane", "J1", "backplane 2x13", "Connector_PinHeader_2.54mm:PinHeader_2x13_P2.54mm_Vertical_SMD",
                  "HDR_2x13_2.54_SMD")
        rails = {"GND": gnd, "+12V": v12, "+5V": v5}
        for num, name in symbols_rx.BACKPLANE.items():
            j1[str(num)] += rails.get(name) or bp[name]
        # live insertion / backplane transients: TVS on each rail at the connector (SMF15A 15 V, SMF5.0A 5 V standoff)
        t1 = part("TVS", "D1", "SMF15A", "Diode_SMD:D_SOD-123F", "SMF15A"); t1["K"] += v12; t1["A"] += gnd
        t2 = part("TVS", "D2", "SMF5.0A", "Diode_SMD:D_SOD-123F", "SMF5.0A"); t2["K"] += v5; t2["A"] += gnd
        C("C1", "10u", v5, gnd); C("C2", "100n", v5, gnd)
        # 3.3 V digital (module, DAC DVDD, switch) and 3.3 V analog (DAC AVDD + CPVDD) from +5 V: TLV75533P, TI SBVS320
        for ref, out, cin, cout in (("U4", v3, "C3", "C4"), ("U5", v3a, "C5", "C6")):
            u = part("TLV75533P", ref, "TLV75533P", "Package_TO_SOT_SMD:SOT-23-5", "TLV75533PDBVR")
            u["IN"] += v5; u["EN"] += v5; u["GND"] += gnd; u["OUT"] += out; u["NC"] += NC
            C(cin, "1u", v5, gnd); C(cout, "10u", out, gnd)
        # driver rail: 10 R + 100 uF off the backplane 12 V (fc 160 Hz; op-amp PSRR does the rest)
        R("R1", "10", v12, v12a, "Resistor_SMD:R_0603_1608Metric", "R_0603_1%")
        CP("C7", "100u 25V", v12a, gnd, "ALU_100u_25V", "Capacitor_SMD:CP_Elec_6.3x5.4")
        C("C8", "100n", v12a, gnd)

    with Group("mcu"):
        # ---- BT40NE: VDD = VDDH = 3.3 V. USB unused on the receiver (UART DFU, FW-6) ----
        u1 = part("BT40NE", "U1", "BT40NE", "openpack:Fanstel_BT40NE", "BT40NE")
        u1["9"] += v3; u1["F4"] += v3
        for p in ("10", "A0", "B0", "C0", "D0", "H0", "H1", "H2", "H3"):
            u1[p] += gnd
        C("C10", "10u", v3, gnd); C("C11", "100n", v3, gnd); C("C12", "100n", v3, gnd)   # C12 at pad F4 (VDDH)
        sig = {name: Net(name) for name in PADS}
        for name, (pad, _gpio) in PADS.items():
            u1[pad] += sig[name]
        # Backplane side of every off-board signal goes through a series resistor: 1k on lines the host drives
        # (limits back-powering through the GPIO ESD diodes into an unpowered module, and ESD current), 100 R on
        # lines the module drives (I2S, UART TX, LEDs: source damping + current limit into a shorted backplane line).
        R("R20", "100", sig["UART_TX"], bp["BP_UART_TX"])
        R("R21", "1k", bp["BP_UART_RX"], sig["UART_RX"])
        nrst = Net("nRESET"); u1["14"] += nrst
        R("R22", "1k", bp["BP_nRESET"], nrst)             # host can reset the module (RX-10); nRF5340 has its own pull-up
        R("R23", "1k", bp["BP_BOOT"], sig["BOOT"]); R("R24", "10k", v3, sig["BOOT"])
        for i in range(3):
            R(f"R{25 + i}", "1k", bp[f"BP_SLOT{i}"], sig[f"SLOT{i}"]); R(f"R{28 + i}", "10k", v3, sig[f"SLOT{i}"])
        R("R31", "100", sig["LED_LOCK"], bp["BP_LED_LOCK"]); R("R32", "100", sig["LED_PEAK"], bp["BP_LED_PEAK"])
        for i, s in enumerate(("I2S_BCK", "I2S_LRCK", "I2S_SDOUT")):
            R(f"R{33 + i}", "100", sig[s], bp["BP_" + s])     # I2S kept on the backplane (QUESTIONS.md nice-to-know)
        # SWD on Tag-Connect pads
        j2 = part("Tag_TC2030", "J2", "SWD", "Connector:Tag-Connect_TC2030-IDC-NL_2x03_P1.27mm_Vertical", "TC2030-pads")
        swdio, swclk = Net("SWDIO"), Net("SWDCLK")
        j2["VTREF"] += v3; j2["SWDIO"] += swdio; j2["~{RESET}"] += nrst; j2["SWDCLK"] += swclk; j2["GND"] += gnd
        j2["SWO"] += NC
        u1["16"] += swdio; u1["15"] += swclk
        for p in u1.pins:
            if not p.net:
                p += NC      # spare GPIO, NC, USB, and the nine nRF21540-internal pads

    with Group("rf"):
        # ---- RX-1 antenna A/B: two u.FL from the rack splitters -> PE4259 -> u.FL -> jumper -> module u.FL ----
        # PE4259 Table 5 (single-pin mode): CTRL low = RFC-RF2, high = RFC-RF1. So ANT_SEL 0 = antenna A on RF2.
        u2 = part("PE4259", "U2", "PE4259", "Package_TO_SOT_SMD:SOT-363_SC-70-6", "PE4259-63")
        ja, jb, jo = (part("UFL", r, v, "Connector_Coaxial:U.FL_Hirose_U.FL-R-SMT-1_Vertical", "U.FL-R-SMT-1(10)")
                      for r, v in (("J3", "ANT_A"), ("J4", "ANT_B"), ("J5", "TO_MODULE")))
        for j in (ja, jb, jo):
            j["GND"] += gnd
        a_in, b_in, out = Net("RF_A"), Net("RF_B"), Net("RF_OUT")
        ja["RF"] += a_in; jb["RF"] += b_in; jo["RF"] += out
        rf1, rf2, rfc = Net("SW_RF1"), Net("SW_RF2"), Net("SW_RFC")
        u2["RF1"] += rf1; u2["RF2"] += rf2; u2["RFC"] += rfc
        # all three RF ports DC blocked (DOC-03694 Table 7 note): 10 pF C0G 0402, near series resonance at 2.4 GHz
        C("C20", "10p", a_in, rf2); C("C21", "10p", b_in, rf1); C("C22", "10p", rfc, out)
        u2["CTRL"] += sig["ANT_SEL"]; u2["VDD"] += v3; u2["GND"] += gnd
        C("C23", "100n", v3, gnd)
        R("R36", "100k", sig["ANT_SEL"], gnd)       # antenna A while the net core is in reset

    with Group("dac"):
        # ---- PCM5102A (SLAS859C): I2S (FMT=0), BCK PLL (SCK=GND, 3-wire), low-latency filter (FLT=1, R3), DEMP off ----
        u3 = part("PCM5102A", "U3", "PCM5102A", "Package_SO:TSSOP-20_4.4x6.5mm_P0.65mm", "PCM5102APWR")
        u3["BCK"] += sig["I2S_BCK"]; u3["LRCK"] += sig["I2S_LRCK"]; u3["DIN"] += sig["I2S_SDOUT"]
        u3["SCK"] += gnd; u3["FMT"] += gnd; u3["DEMP"] += gnd; u3["FLT"] += v3
        u3["XSMT"] += sig["DAC_XSMT"]; R("R37", "100k", sig["DAC_XSMT"], gnd)   # muted at power-up and on reset
        u3["AVDD"] += v3a; u3["CPVDD"] += v3a; u3["DVDD"] += v3
        for p in ("AGND", "CPGND", "DGND"):
            u3[p] += gnd
        C("C30", "10u", v3a, gnd); C("C31", "100n", v3a, gnd)     # AVDD (SLAS859C Figure 33)
        C("C32", "10u", v3a, gnd); C("C33", "100n", v3a, gnd)     # CPVDD
        C("C34", "10u", v3, gnd); C("C35", "100n", v3, gnd)       # DVDD
        ldoo, capp, capm, vneg = Net("DAC_LDOO"), Net("DAC_CAPP"), Net("DAC_CAPM"), Net("DAC_VNEG")
        u3["LDOO"] += ldoo; u3["CAPP"] += capp; u3["CAPM"] += capm; u3["VNEG"] += vneg
        C("C36", "100n", ldoo, gnd)                                # LDOO 0.1 uF (SLAS859C Table 12)
        C("C37", "2u2", capp, capm); C("C38", "2u2", vneg, gnd)    # charge pump flying + VNEG
        outl = Net("DAC_OUTL"); u3["OUTL"] += outl; u3["OUTR"] += NC   # mono: one pack per receiver
        dacf = Net("DAC_OUTF")
        R("R40", "470", outl, dacf); C("C39", "2n2", dacf, gnd)    # recommended output filter (Figure 33)

    with Group("driver"):
        # ---- RX-8 balanced driver, +12 V single supply, both op-amp + inputs at VCM = 6 V ----
        # Two inverting stages, so the input common mode never moves: OPA1656 VCM range is (V-)..(V+)-2.25 V
        # (SBOS901C 6.6); 6 V is 3.75 V inside it (3.45 V at 11.4 V). Leg A = -1.478 x DAC = COLD (XLR 3);
        # leg B = -1 x leg A = HOT (XLR 2), so XLR pin 2 is in phase with the DAC. 0 dBFS = 2.1 Vrms (SLAS859C)
        # -> 6.21 Vrms balanced = +18.1 dBu; -20 dBFS -> -1.9 dBu (hw/spice/rx_driver.cir).
        u6 = part("OPA1656", "U6", "OPA1656", "Package_SO:SOIC-8_3.9x4.9mm_P1.27mm", "OPA1656IDR")
        vcm = Net("VCM")
        R("R45", "100k", v12a, vcm); R("R46", "100k", vcm, gnd)   # fc 0.07 Hz with C43
        CP("C43", "47u 25V", vcm, gnd, "ALU_47u_25V", "Capacitor_SMD:CP_Elec_5x5.4"); C("C44", "100n", vcm, gnd)
        u6["+INA"] += vcm; u6["+INB"] += vcm
        u6["V+"] += v12a; u6["V-"] += gnd
        C("C45", "100n", v12a, gnd); C("C46", "10u", v12a, gnd, C1206, "C_10u_1206_25V_X7R")
        # leg A: DAC_OUTF -> 47 uF (+ at the op-amp side, which sits at VCM) -> 2.0k -> -INA; Rf 3.65k || 100 pF
        cin, ina, oa = Net("DRV_CIN"), Net("DRV_INA"), Net("DRV_OUTA")
        CP("C40", "47u 25V", cin, dacf, "ALU_47u_25V", "Capacitor_SMD:CP_Elec_5x5.4")
        R("R41", "2.0k", cin, ina); R("R42", "3.65k", ina, oa); C("C41", "100p", ina, oa)
        u6["-INA"] += ina; u6["OUTA"] += oa
        # leg B: unity inverting from leg A
        inb, ob = Net("DRV_INB"), Net("DRV_OUTB")
        R("R43", "4.99k", oa, inb); R("R44", "4.99k", inb, ob); C("C42", "100p", inb, ob)
        u6["-INB"] += inb; u6["OUTB"] += ob
        # outputs: 22 R build-out -> clamp to the rails (BAV99) -> 47 uF 63 V bipolar (phantom: XLR side may sit
        # at +48 V through 6.8k) -> 22 R (limits clamp current if a charged cable is shorted) -> backplane -> XLR.
        # 100k bleeds the XLR side to 0 V. Zout = 2 x (22 + 22 + Xc) = 89 ohm balanced at 1 kHz (RX-8 <= 100).
        for leg, o, r0, d, cc, r1, rb, aud in (("COLD", oa, "R47", "D3", "C47", "R48", "R49", bp["AUD_COLD"]),
                                                 ("HOT", ob, "R50", "D4", "C48", "R51", "R52", bp["AUD_HOT"])):
            pnode, xnode = Net(f"DRV_{leg}_P"), Net(f"DRV_{leg}_X")
            R(r0, "22", o, pnode, "Resistor_SMD:R_0603_1608Metric", "R_0603_1%")
            dd = part("BAV99", d, "BAV99", "Package_TO_SOT_SMD:SOT-23", "BAV99,215")
            dd["A1"] += gnd; dd["K2"] += v12a; dd["COM"] += pnode
            c = part("C", cc, "47u 63V BP", "Capacitor_THT:CP_Radial_D10.0mm_P5.00mm", "ALU_BP_47u_63V")
            c[1] += pnode; c[2] += xnode
            R(r1, "22", xnode, aud, "Resistor_SMD:R_0603_1608Metric", "R_0603_1%")
            R(rb, "100k", xnode, gnd)


def bom_rows(circuit):
    groups = {}
    for p in circuit.parts:
        groups.setdefault((p.fields.get("MPN", ""), p.value), []).append(p.ref)

    def key(r):
        return (r.rstrip("0123456789"), int("0" + r.lstrip("ABCDEFGHIJKLMNOPQRSTUVWXYZ")))

    def row(refs, qty, val, mpn, unit, src, uk):
        gbp = unit * prices.GBP_PER_USD
        return {"refs": refs, "qty": qty, "value": val, "mpn": mpn, "unit_usd": f"{unit:.2f}",
                "ext_usd": f"{unit * qty:.2f}", "unit_gbp": f"{gbp:.2f}", "ext_gbp": f"{gbp * qty:.2f}",
                "uk_distributor": uk, "source": src}

    rows = []
    for (mpn, val), refs in sorted(groups.items(), key=lambda kv: key(sorted(kv[1], key=key)[0])):
        rows.append(row(" ".join(sorted(refs, key=key)), len(refs), val, mpn, *prices.PRICES[mpn]))
    for item, qty, unit, src, uk in prices.EXTRAS:
        rows.append(row("-", qty, item, "-", unit, src, uk))
    return rows


def erc():
    """Run SKiDL ERC on the built circuit; return (errors, warnings) counted by ERC alone (as hw/pack/pack.py)."""
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
    skidl.generate_netlist(file_=str(OUT / "rx.net"))
    rows = bom_rows(builtins.default_circuit)
    with open(OUT / "bom.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    print(f"BOM total ${sum(float(r['ext_usd']) for r in rows):.2f} / GBP {sum(float(r['ext_gbp']) for r in rows):.2f} per receiver sub-board")
    if "--no-sch" not in argv:
        opts = dict(top_name="rx", title="OpenPack receiver sub-board", flatness=0, auto_stub=True)
        skidl.generate_schematic(filepath=str(OUT / "sch"), **opts)
        skidl.generate_schematic(filepath=str(OUT / "svg"), format="svg", **opts)
    return errs + warns


if __name__ == "__main__":
    sys.exit(1 if main(sys.argv[1:]) else 0)
