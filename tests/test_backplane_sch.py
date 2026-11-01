"""RK-1..RK-3 (#33, ADR-0018): the SKiDL rack main board builds, passes ERC, the committed BOM is current, and the
nets the sub-boards (ADR-0014), the host and the rear panel depend on are where ADR-0018 says."""
import builtins, collections, csv, importlib.util, io, os, pathlib, re, tokenize
import pytest

if os.environ.get("CI"):
    import skidl  # noqa: F401  (CI must have it: a skip there would hide a broken schematic)
else:
    pytest.importorskip("skidl")
ROOT = pathlib.Path(__file__).resolve().parents[1]
RACK = ROOT / "hw/rack"


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    bp = _load("hw_rack_backplane", RACK / "backplane.py")
    cwd = os.getcwd()
    os.chdir(tmp_path_factory.mktemp("rack"))  # SKiDL writes log files into the cwd
    try:
        bp.build()
        errs = bp.erc()
    finally:
        os.chdir(cwd)
    c = builtins.default_circuit
    net = {(p.ref, str(pin.num)): (pin.net.name if pin.net else None) for p in c.parts for pin in p.pins}
    parts = {p.ref: p for p in c.parts}
    return bp, errs, c, net, parts


def pair(net, ref):
    return {net[ref, "1"], net[ref, "2"]}


def on_net(net, name):
    """{(ref, pin)} on a net."""
    return {k for k, v in net.items() if v == name}


def test_erc_and_bom(built):
    bp, errs, c, _, _ = built
    assert errs == (0, 0)
    rows = bp.bom_rows(c)
    with open(RACK / "out/bom.csv") as f:
        committed = list(csv.DictReader(f))
    assert [{k: str(v) for k, v in r.items()} for r in rows] == committed, "run python hw/rack/backplane.py --no-sch"
    for r in rows:                      # UK owner: every line has a UK distributor, a GBP price and a labelled source
        assert r["uk_distributor"] and float(r["unit_gbp"]) >= 0
        assert r["source"].startswith(("est.", "DigiKey UK", "copper", "The Pi Hut", "RS UK", "Rapid Online", "LCSC")), r


def test_no_skidl_calls_in_comments():
    """#81 review: no part or connection may hide after a '#'."""
    src = (RACK / "backplane.py").read_text()
    for tok in tokenize.generate_tokens(io.StringIO(src).readline):
        if tok.type == tokenize.COMMENT:
            assert not re.search(r"\b(R|C|CP|part|efuse|ufl|uvlo12)\(|\+=", tok.string), tok


def test_slot_sockets_follow_adr0014(built):
    bp, _, _, net, parts = built
    table = bp.symbols_rack.BACKPLANE
    adr = (ROOT / "docs/adr/0014-rx-backplane-connector.md").read_text()
    for n, name in table.items():                              # the symbol is the ADR-0014 table
        assert re.search(rf"\|\s*{n}\s*\|\s*`{re.escape(name)}`\s*\|", adr), (n, name)
    for k in range(bp.N_SLOTS):
        j = f"J{10 + k}"
        assert parts[j].fields["MPN"] == "2.54-2*13PFemale"
        got = {n: net[j, str(n)] for n in table}
        assert got[14] == "__NOCONNECT"                        # key: position 14 plugged
        for n, name in table.items():
            if name == "GND":
                assert got[n] == "GND", (k, n)
            elif name in ("+12V", "+5V"):
                assert got[n] == f"{name}_S{k}", (k, n)        # per-slot fused rail
            elif name.startswith("BP_I2S"):
                assert got[n] == "__NOCONNECT"                 # no I2S stubs beside the splitters
            elif name.startswith("BP_SLOT"):
                bit = (k >> int(name[-1])) & 1
                assert got[n] == ("__NOCONNECT" if bit else "GND"), (k, name)   # slot ID straps encode k
            elif name != "KEY":
                assert got[n] == f"S{k}_{name}", (k, n)


def test_slot_power_protection(built):
    bp, _, _, net, parts = built
    for k in range(bp.N_SLOTS):
        for u, rail, mpn, vin in ((f"U{20 + k}", f"+12V_S{k}", "TPS259541DSGR", "+12V_BUS"),
                                  (f"U{30 + k}", f"+5V_S{k}", "TPS259531DSGR", "+5V")):
            assert parts[u].fields["MPN"] == mpn
            assert (net[u, "3"], net[u, "4"], net[u, "5"]) == (vin, vin, rail)
            assert net[u, "6"] == "HOST_GPIO6"                 # fault wire-OR to the host
            r = next(p for p in parts.values() if p.ref.startswith("R") and net[p.ref, "1"] == net[u, "7"])
            assert net[r.ref, "2"] == "GND" and 0.45 <= bp.i_lim(float(r.value.rstrip("k")) * 1e3) <= 0.55
    # TPS2595 EN/UVLO (SLVSE57C): 1.2 V rising, 6 V max. 12 V feeds start at ~10 V and survive the 13.7 V clamp
    top, bot = bp.UVLO_12
    assert 9.5 <= 1.2 * (top + bot) / bot <= 10.5 and 20.0 * bot / (top + bot) <= 6.0
    # the sub-board supervisor trips at 10.78 V (ADR-0014): the slot eFuse keeps the rail on above 9.15 V
    assert 1.1 * (top + bot) / bot < 10.78
    assert 3.4 <= bp.i_lim(bp.R_ILM["input"]) <= 3.6 and all(487 <= v <= 5000 for v in bp.R_ILM.values())


def test_power_entry(built):
    bp, _, _, net, parts = built
    assert (net["J1", "1"], net["J1", "2"]) == ("+12V_IN", "GND")
    assert pair(net, "F1") == {"+12V_IN", "+12V_RAW"} and parts["F1"].fields["MPN"] == "0451004.MRL"   # fuse ahead of TVS
    # P-FET: drain at the jack, source to the load (body diode blocks a reversed brick), gate to GND, Vgs clamp
    assert {net["Q1", p] for p in "5678"} == {"+12V_RAW"} and {net["Q1", p] for p in "123"} == {"+12V_PROT"}
    assert (net["D1", "1"], net["D1", "2"]) == ("+12V_PROT", "Q1_G")
    assert (net["D2", "1"], net["D2", "2"]) == ("+12V_PROT", "GND") and parts["D2"].value == "SMBJ12A"
    assert (net["U1", "3"], net["U1", "5"]) == ("+12V_PROT", "+12V_BUS") and parts["U1"].value == "TPS259541DSGR"
    # TPS62933 5 V: FB divider 53.6k / 10.2k on 0.8 V (SLUSEA4D)
    assert (net["U2", "3"], net["U2", "8"], net["L1", "2"]) == ("+12V_BUS", "BUCK_FB", "+5V")
    assert abs(0.8 * (1 + 53.6 / 10.2) - 5.0) < 0.05
    assert pair(net, "NT1") == {"GND", "CHASSIS"}


def test_rf_chain(built):
    bp, _, _, net, parts = built
    for ant, bnc, lna, flt in (("A", "J3", "U6", "U8"), ("B", "J4", "U7", "U9")):
        assert (net[bnc, "1"], net[bnc, "2"]) == (f"ANT_{ant}", "GND")
        on = on_net(net, f"ANT_{ant}")
        vals = {parts[r].value for r, _ in on}
        assert {"ESD103-B1-02EL", "39n", "100p"} <= vals            # ESD, bias-T choke, DC block at the BNC
        # the LNA input is DC blocked and has its own 0 V ESD (the antenna side carries the 12 V bias)
        assert {parts[r].value for r, _ in on_net(net, f"LNA_{ant}_IN")} >= {"ESD101-B1-02EL", "100p"}
        assert net[lna, "2"] == f"LNA_{ant}_RFIN" and net[lna, "6"] == "GND"     # SD low = on
        assert {net[lna, p] for p in ("3", "4", "5", "8", "9")} == {"GND"}
        assert net[lna, "7"] == f"LNA_{ant}_RFOUT" and net[lna, "1"] == f"LNA_{ant}_VBIAS"
        choke = next(r for r, _ in on_net(net, f"LNA_{ant}_RFOUT") if parts[r].value == "18n")
        assert pair(net, choke) == {f"LNA_{ant}_RFOUT", f"+5V_LNA_{ant}"}
        # QPQ1907 Data Sheet 040820: 1 INPUT, 2/3/5 GND, 4 OUTPUT
        assert (net[flt, "1"], net[flt, "4"]) == (f"LNA_{ant}_OUT", f"SPL_{ant}_IN")
        assert {net[flt, p] for p in "235"} == {"GND"}
        # bias-T eFuse: host enable with pull-down (off by default), 0.49 A limit, fault to the host
        efb = "U10" if ant == "A" else "U11"
        assert net[efb, "5"] == f"BIAS_{ant}_DC" and net[efb, "2"] == f"HOST_{bp.HOST[f'BIAS_{ant}_EN']}"
        assert net[efb, "6"] == f"HOST_{bp.HOST[f'BIAS_{ant}_FLT']}"


def test_wilkinson_trees(built):
    bp, _, _, net, parts = built
    for ant in "AB":
        # walk the copper from the filter output: TL parts only, resistors bridge arm pairs
        adj = collections.defaultdict(set)
        for p in parts.values():
            if p.ref.startswith("TL"):
                a, b = net[p.ref, "1"], net[p.ref, "2"]
                adj[a].add(b); adj[b].add(a)
        seen, todo = {f"SPL_{ant}_IN"}, [f"SPL_{ant}_IN"]
        while todo:
            for m in adj[todo.pop()] - seen:
                seen.add(m); todo.append(m)
        ports = sorted(n for n in seen if re.fullmatch(rf"RF_{ant}\d", n))
        assert ports == [f"RF_{ant}{k}" for k in range(8)]          # 1:8, one port per slot
        iso = [p for p in parts.values() if p.ref.startswith("R") and p.value == "100"
               and p.fields["MPN"] == "R_0402_100R_TF" and net[p.ref, "1"].startswith(f"WK_{ant}_")]
        assert len(iso) == 7                                          # 1 + 2 + 4 dividers
        for r in iso:                                                 # each across the two arms of one divider
            a, b = net[r.ref, "1"], net[r.ref, "2"]
            assert a[:-1] == b[:-1] and {a[-1], b[-1]} == {"a", "b"}
        for k in range(8):
            j = f"J{30 + k}" if ant == "A" else f"J{40 + k}"
            assert net[j, "1"] == f"RF_{ant}{k}" and net[j, "2"] == "GND"


def test_host_interface(built):
    bp, _, _, net, parts = built
    hdr = bp.symbols_rack.HOST_HEADER
    # standard Raspberry Pi 40-way header (CM4IO J8): spot-check the BCM numbering
    assert (hdr[8], hdr[10], hdr[12], hdr[35], hdr[38], hdr[40], hdr[27], hdr[28]) == (
        "GPIO14", "GPIO15", "GPIO18", "GPIO19", "GPIO20", "GPIO21", "GPIO0", "GPIO1")
    for n, name in hdr.items():
        got = net["J2", str(n)]
        if name == "GND":
            assert got == "GND", n
        if name in ("3V3", "5V", "GPIO0", "GPIO1"):
            assert got == "__NOCONNECT", n                            # no rail tie, HAT ID pins left alone
    for k, (tx, rx) in bp.SLOT_UART.items():
        if tx.startswith("GPIO"):
            assert any(pair(net, r) == {f"HOST_{tx}", f"S{k}_BP_UART_RX"} for r in parts if r.startswith("R"))
            assert any(pair(net, r) == {f"S{k}_BP_UART_TX", f"HOST_{rx}"} for r in parts if r.startswith("R"))
        else:
            pins = {"A": ("3", "4"), "B": ("23", "24")}[rx]          # SC16IS752 TSSOP-28 TXA/RXA, TXB/RXB
            assert (net[tx, pins[0]], net[tx, pins[1]]) == (f"S{k}_BP_UART_RX", f"S{k}_BP_UART_TX")
        u, g_rst, g_boot = bp.SLOT_CTRL[k]
        gpio_pin = {0: "18", 1: "19", 2: "20", 3: "21", 4: "25", 5: "26", 6: "27", 7: "28"}
        assert (net[u, gpio_pin[g_rst]], net[u, gpio_pin[g_boot]]) == (f"S{k}_BP_nRESET", f"S{k}_BP_BOOT")
    for u, ce in (("U4", "GPIO18"), ("U5", "GPIO17")):               # SPI mode, SPI1 CE0/CE1
        assert net[u, "9"] == "GND" and net[u, "10"] == f"HOST_{ce}" and net[u, "14"] == "GND"
        assert (net[u, "11"], net[u, "12"], net[u, "13"]) == ("HOST_GPIO20", "HOST_GPIO19", "HOST_GPIO21")


def test_rear_panel_and_esd(built):
    bp, _, _, net, parts = built
    xlr = [p for p in parts.values() if p.fields.get("MPN") == "NC3MAH"]
    bnc = [p for p in parts.values() if p.fields.get("MPN") == "5415025-1"]
    dc = [p for p in parts.values() if p.fields.get("MPN") == "PJ-063AH"]
    assert (len(xlr), len(bnc), len(dc)) == (8, 2, 1)                 # RK-1 rear panel (+ etherCON, USB in EXTRAS)
    extras = " ".join(e[0] for e in bp.prices.EXTRAS)
    assert "NE8FDP" in extras and "USB-C" in extras and "no wireless" in extras
    for k in range(bp.N_SLOTS):
        j = f"J{20 + k}"
        assert (net[j, "2"], net[j, "3"], net[j, "1"], net[j, "G"]) == (
            f"S{k}_AUD_HOT", f"S{k}_AUD_COLD", "CHASSIS", "CHASSIS")
        for leg in ("AUD_HOT", "AUD_COLD"):                           # >= 58 V standoff TVS (ADR-0014 item 1)
            tvs = [r for r, _ in on_net(net, f"S{k}_{leg}") if parts[r].value == "SMAJ58CA"]
            assert len(tvs) == 1 and "CHASSIS" in pair(net, tvs[0])


def test_rf_path_is_continuous(built):
    """#95 M1: walk BNC -> DC block -> LNA -> output block -> BAW -> Wilkinson -> slot u.FL through series elements
    only. A pin swapped onto ground (as the first QPQ1907 pinout did) breaks the walk or puts GND on the path."""
    bp, _, _, net, parts = built
    through = {"U6": ("2", "7"), "U7": ("2", "7"), "U8": ("1", "4"), "U9": ("1", "4")}   # LNA in/out, BAW in/out
    edges = collections.defaultdict(set)
    for p in parts.values():
        series = (p.ref.startswith("TL") or (p.ref.startswith("C") and p.value == "100p")
                  or (p.ref.startswith("R") and p.value == "0"))
        pins = through.get(p.ref) or (("1", "2") if series else None)
        if pins:
            a, b = net[p.ref, pins[0]], net[p.ref, pins[1]]
            edges[a].add(b); edges[b].add(a)
    for ant in "AB":
        seen, todo = {f"ANT_{ant}"}, [f"ANT_{ant}"]
        while todo:
            for m in edges[todo.pop()] - seen - {"GND"}:
                seen.add(m); todo.append(m)
        order = [f"ANT_{ant}", f"LNA_{ant}_IN", f"LNA_{ant}_RFIN", f"LNA_{ant}_RFOUT", f"LNA_{ant}_OUT", f"SPL_{ant}_IN"]
        assert set(order) <= seen, (ant, set(order) - seen)
        assert {f"RF_{ant}{k}" for k in range(8)} <= seen
        assert not any(n.startswith("+") for n in seen)          # the walk never lands on a supply rail
        for n in order:                                          # and no RF node is shorted to ground
            assert n != "GND"


def test_bias_t_resistor_dissipation(built):
    """#95 M4: the bias-T series resistor survives the eFuse's worst-case current limit at <= 50 % of its rating."""
    bp, _, _, net, parts = built
    for ant in "AB":
        r = next(p for p in parts.values()
                 if p.ref.startswith("R") and pair(net, p.ref) == {f"BIAS_{ant}_RF", f"BIAS_{ant}_DC"})
        watts = bp.I_LIM_MAX_4420 ** 2 * float(r.value)
        assert watts <= 0.5 * float(r.fields["P_W"]), (r.ref, watts, r.fields["P_W"])
    for p in parts.values():                                     # every resistor carries a rating
        if p.ref.startswith("R"):
            assert float(p.fields["P_W"]) > 0


def test_slot_key_plugs():
    """#95 S3 / #116 S1: position 14 is physically blocked in every slot socket: the footprint has no hole at 14 (the
    socket cannot be soldered with its contact 14 in place) and the price line carries the pull-and-plug step."""
    pr = _load("hw_rack_prices_t", RACK / "prices.py")
    assert "cavity plugged" in pr.PRICES["2.54-2*13PFemale"][2]
    src = (RACK / "backplane.py").read_text()
    assert '"openpack:PinSocket_2x13_P2.54mm_Key14", "2.54-2*13PFemale"' in src
