"""RX-1, RX-8 (#32): the SKiDL receiver sub-board builds, passes ERC, the committed BOM is current, and the
nets the firmware and the backplane depend on are where ADR-0014 says."""
import builtins, csv, importlib.util, os, pathlib, re
import pytest

if os.environ.get("CI"):
    import skidl  # noqa: F401  (CI must have it: a skip there would hide a broken schematic)
else:
    pytest.importorskip("skidl")
ROOT = pathlib.Path(__file__).resolve().parents[1]
RX = ROOT / "hw/rx"


def _load_rx():
    spec = importlib.util.spec_from_file_location("hw_rx_sch", RX / "rx.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    rx = _load_rx()
    cwd = os.getcwd()
    os.chdir(tmp_path_factory.mktemp("rx"))  # SKiDL writes log files into the cwd
    try:
        rx.build()
        errs = rx.erc()
    finally:
        os.chdir(cwd)
    c = builtins.default_circuit
    net = {(p.ref, str(pin.num)): (pin.net.name if pin.net else None) for p in c.parts for pin in p.pins}
    return rx, errs, c, net


def pair(net, ref):
    return {net[ref, "1"], net[ref, "2"]}


def test_erc_and_bom(built):
    rx, errs, c, _ = built
    assert errs == (0, 0)
    rows = rx.bom_rows(c)
    with open(RX / "out/bom.csv") as f:
        committed = list(csv.DictReader(f))
    assert [{k: str(v) for k, v in r.items()} for r in rows] == committed, "run python hw/rx/rx.py --no-sch"
    for r in rows:                      # UK owner: every line has a UK-reachable distributor and a GBP figure
        assert r["uk_distributor"] and r["source"] and float(r["unit_gbp"]) >= 0


def test_module_pads(built):
    rx, _, _, net = built
    # UART = the firmware console: zephyr,console is uart0, whose nrf5340dk pinctrl is TX P0.20 / RX P0.22
    # (zephyr boards/nordic/nrf5340dk/nrf5340_cpuapp_common-pinctrl.dtsi, uart0_default).
    assert rx.PADS["UART_TX"] == ("C5", "P0.20") and rx.PADS["UART_RX"] == ("D5", "P0.22")
    assert (net["U1", "C5"], net["U1", "D5"]) == ("UART_TX", "UART_RX")
    assert pair(net, "R20") == {"UART_TX", "BP_UART_TX"} and pair(net, "R21") == {"UART_RX", "BP_UART_RX"}
    # I2S: module (master) -> PCM5102A BCK 13 / LRCK 15 / DIN 14 (SLAS859C pin functions)
    assert [net["U1", p] for p in ("C3", "C4", "B6")] == ["I2S_BCK", "I2S_LRCK", "I2S_SDOUT"]
    assert [net["U3", p] for p in ("13", "15", "14")] == ["I2S_BCK", "I2S_LRCK", "I2S_SDOUT"]
    fem = ("Z6", "A6", "C2", "C6", "D1", "D2", "E0", "E1", "E2")   # nRF21540 control inside the module
    assert {net["U1", n] for n in fem} == {"__NOCONNECT"}
    assert {pad for pad, _ in rx.PADS.values()}.isdisjoint(fem)
    assert (net["U1", "9"], net["U1", "F4"]) == ("+3V3", "+3V3")


def test_antenna_switch(built):
    rx, _, _, net = built
    # Firmware stub: op_rx_ant_select(uint8_t ant), antenna 0/1 (fw/src/rx/op_rx.h, ADR-0011). Board: ANT_SEL
    # GPIO -> PE4259 CTRL (pin 4); CTRL low = RFC-RF2 (pSemi DOC-03694 Table 5) = J3 ANT_A, so ant 0 = A.
    hdr = (ROOT / "fw/src/rx/op_rx.h").read_text()
    assert re.search(r"void\s+op_rx_ant_select\s*\(\s*uint8_t\s+\w+\s*\)", hdr)
    assert rx.PADS["ANT_SEL"] == ("D6", "P1.01")
    assert net["U1", "D6"] == net["U2", "4"] == "ANT_SEL"
    assert pair(net, "R36") == {"ANT_SEL", "GND"}            # pulled low: antenna A until firmware drives it
    assert net["J3", "1"] == "RF_A" and pair(net, "C20") == {"RF_A", "SW_RF2"} and net["U2", "3"] == "SW_RF2"
    assert net["J4", "1"] == "RF_B" and pair(net, "C21") == {"RF_B", "SW_RF1"} and net["U2", "1"] == "SW_RF1"
    assert pair(net, "C22") == {"SW_RFC", "RF_OUT"} and net["J5", "1"] == "RF_OUT"   # all RF ports DC blocked
    assert (net["U2", "6"], net["U2", "2"]) == ("+3V3", "GND")


def test_dac_and_driver(built):
    rx, _, _, net = built
    # PCM5102A straps: SCK=GND (BCK PLL), FMT=0 (I2S), DEMP=0, FLT=1 (low latency); XSMT pulled low (muted)
    assert [net["U3", p] for p in ("12", "16", "10", "11")] == ["GND", "GND", "GND", "+3V3"]
    assert net["U3", "17"] == "DAC_XSMT" and pair(net, "R37") == {"DAC_XSMT", "GND"}
    assert rx.PADS["XSMT_EN"] == ("B5", "P0.12") and pair(net, "R38") == {"XSMT_EN", "DAC_XSMT"}
    assert (net["U3", "8"], net["U3", "1"], net["U3", "20"]) == ("+3V3A", "+3V3A", "+3V3")
    # OPA1656 on the filtered 12 V rail; both + inputs at VCM (the CM never moves: inverting stages)
    assert (net["U6", "8"], net["U6", "4"], net["U6", "3"], net["U6", "5"]) == ("+12VA", "GND", "VCM", "VCM")
    assert pair(net, "R1") == {"+12V", "+12V_R"} and (net["D9", "1"], net["D9", "3"]) == ("+12V_R", "+12VA")  # hold-up
    # VCM: two poles, and D8 dumps it into +12VA at power-down (op-amp input current limit, #81 M3)
    assert pair(net, "R53") == {"VCM1", "VCM"} and (net["D8", "1"], net["D8", "3"]) == ("VCM", "+12VA")
    # polarity: leg A (OUTA, inverted) -> XLR 3 COLD, leg B (OUTB, re-inverted) -> XLR 2 HOT, each through K1 (NO)
    assert pair(net, "R47") == {"DRV_OUTA", "DRV_COLD_P"} and pair(net, "R48") == {"DRV_COLD_O", "AUD_COLD"}
    assert pair(net, "R50") == {"DRV_OUTB", "DRV_HOT_P"} and pair(net, "R51") == {"DRV_HOT_O", "AUD_HOT"}
    assert [net["K1", n] for n in ("3", "4", "8", "7")] == ["DRV_COLD_X", "DRV_COLD_O", "DRV_HOT_X", "DRV_HOT_O"]
    assert {net["K1", "2"], net["K1", "9"]} == {"__NOCONNECT"}         # NC contacts unused: open = muted
    # S1J clamps (IFSM 30 A) from each output node to both rails (phantom short, #81 M2); D pad 1 = K, 2 = A
    for lo, hi, node in (("D3", "D5", "DRV_COLD_P"), ("D4", "D6", "DRV_HOT_P")):
        assert (net[lo, "2"], net[lo, "1"]) == ("GND", node) and (net[hi, "2"], net[hi, "1"]) == (node, "+12VA")
    # mute: coil from +12V, BSS138 low side, flyback; gate = OUT_EN via 10k AND supervisor RESET (open drain)
    assert (net["K1", "1"], net["K1", "10"], net["Q1", "3"], net["Q1", "1"]) == ("+12V", "RLY_COIL", "RLY_COIL", "RLY_G")
    assert (net["D7", "1"], net["D7", "2"]) == ("+12V", "RLY_COIL")
    assert rx.PADS["OUT_EN"] == ("12", "P0.11") and pair(net, "R62") == {"OUT_EN", "RLY_G"}
    assert pair(net, "R63") == {"RLY_G", "GND"} and net["U7", "1"] == "RLY_G"
    assert (net["U7", "5"], net["U7", "6"]) == ("SUP_SENSE", "+3V3") and pair(net, "R60") == {"+12V", "SUP_SENSE"}
    assert (net["D10", "1"], net["D10", "3"]) == ("DAC_XSMT", "RLY_G")   # supervisor also mutes the DAC
    # TPS3808G01 threshold 0.405 V (SBVS050N Table 4-1) -> trip on raw +12 V between 10.5 and 11 V
    assert 10.5 <= 0.405 * (249e3 + 9.76e3) / 9.76e3 <= 11.0
    # LDOs: TLV76733 (VIN abs max 18 V > SMF5.0A clamp 9.2 V), IN/EN on +5V, OUT = SNS
    for u, out in (("U4", "+3V3"), ("U5", "+3V3A")):
        assert (net[u, "8"], net[u, "5"], net[u, "1"], net[u, "2"]) == ("+5V", "+5V", out, out)
    # coupling cap polarity: + at the op-amp side (VCM), - at the ground-centred DAC side
    assert (net["C40", "1"], net["C40", "2"]) == ("DRV_CIN", "DAC_OUTF")


def test_backplane_pinout(built):
    rx, _, _, net = built
    table = rx.symbols_rx.BACKPLANE
    assert table[14] == "KEY" and net["J1", "14"] == "__NOCONNECT"     # key pin (pulled), #81 review S3
    assert {n: net["J1", str(n)] for n in table if n != 14} == {n: v for n, v in table.items() if n != 14}
    # I2S to the backplane: not fitted (#81 review S4); the DAC taps the lines on the module side
    for r in ("R33", "R34", "R35"):
        part = next(p for p in built[2].parts if p.ref == r)
        assert part.fields.get("DNP") == "yes" and part.fields["MPN"] == "DNP"
    adr = next((ROOT / "docs/adr").glob("*-rx-backplane-connector.md")).read_text()
    for n, name in table.items():                              # the ADR table is the same pinout
        assert re.search(rf"\|\s*{n}\s*\|\s*`{re.escape(name)}`\s*\|", adr), (n, name)
    for d, rail in (("D1", "+12V"), ("D2", "+5V")):            # rail TVS at the connector
        assert (net[d, "1"], net[d, "2"]) == (rail, "GND")
