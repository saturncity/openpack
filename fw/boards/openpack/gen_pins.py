#!/usr/bin/env python3
"""Generate the openpack_pack / openpack_rx pin devicetree from the SKiDL netlists (#118).

Every nRF5340 pin number in fw/boards/openpack/ comes from here, never by hand:
  hw/pack/out/pack.net, hw/rx/out/rx.net   (KiCad netlists written by hw/pack/pack.py, hw/rx/rx.py)
  hw/pack/openpack.kicad_sym, hw/rx/openpack_rx.kicad_sym   (module pad -> nRF5340 pin names)

  python3 fw/boards/openpack/gen_pins.py            rewrite the *-pins.dtsi files
  python3 fw/boards/openpack/gen_pins.py --check    exit 1 if they are stale (CI, tests/test_fw_board_pins.py)
  python3 fw/boards/openpack/gen_pins.py --check-dts BUILD_DIR...   check every openpack zephyr.dts below them against the netlist

The generator refuses (exit 2) a pin choice the nRF5340 cannot take: a role net missing from the module, a signal net on
the module with no firmware role (so a schematic change can't slip past), two roles on one pin, the battery sense off an
AIN pin, a pin on the LFXO (P0.00/P0.01) or NFC (P0.02/P0.03) pads, USB off the dedicated pads, or an nRF21540 pad
(module-internal wiring, ADR-0012) wired on the board.
"""
import argparse, pathlib, re, sys

ROOT = pathlib.Path(__file__).resolve().parents[3]
HERE = pathlib.Path(__file__).resolve().parent

# ---- inputs -----------------------------------------------------------------------------------------------------------

def parse_netlist(path):
    """KiCad netlist -> (nets {name: [(ref, pin)]}, comps {ref: (value, libpart)})."""
    text = pathlib.Path(path).read_text()
    comps = {}
    for m in re.finditer(r'\(comp\s+\(ref "([^"]+)"\)\s+\(value "([^"]*)"\).*?\(libsource\s+\(lib "[^"]*"\)\s+'
                         r'\(part "([^"]+)"\)', text, re.S):
        comps[m.group(1)] = (m.group(2), m.group(3))
    nets = {}
    for chunk in re.split(r"\(net\s+(?=\(code)", text[text.index("(nets"):])[1:]:
        name = re.search(r'\(name "([^"]*)"\)', chunk).group(1)
        nets[name] = re.findall(r'\(ref "([^"]+)"\)\s+\(pin "([^"]+)"\)', chunk)
    return nets, comps


def parse_symbol_pins(path, symbol):
    """KiCad symbol library -> {pad number: pin name} for one symbol."""
    text = pathlib.Path(path).read_text()
    start = text.index(f'(symbol "{symbol}"')
    nxt = text.find('\n(symbol "', start + 1)
    body = text[start:nxt if nxt > 0 else len(text)]
    return {num: name for name, num in re.findall(r'\(name "([^"]*)".*?\(number "([^"]+)"', body)}


def gpio(pin_name):
    """'P0.04/AIN0' -> (0, 4, 0); 'P1.09' -> (1, 9, None); else None."""
    m = re.match(r"P([01])\.(\d+)(?:/AIN(\d))?", pin_name)
    return (int(m.group(1)), int(m.group(2)), None if m.group(3) is None else int(m.group(3))) if m else None


def ohms(value):
    m = re.fullmatch(r"([\d.]+)\s*([kKM]?)", value.strip())
    if not m:
        raise ValueError(f"not a resistor value: {value!r}")
    return round(float(m.group(1)) * {"": 1, "k": 1e3, "K": 1e3, "M": 1e6}[m.group(2)])


# ---- what each schematic net is for (the only hand-written mapping) -----------------------------------------------------
# kind: psel (pinctrl, app core), led, user (zephyr,user <prop>-gpios), key (gpio-keys), fwd (net-core GPIO, forwarded),
#       ain (SAADC), usb (dedicated pad), ignore (board net the firmware does not touch).
BOARDS = {
    "pack": {
        "net": "hw/pack/out/pack.net", "sym": "hw/pack/openpack.kicad_sym", "module": "U1",
        "source": "hw/pack/pack.py, ADR-0012",
        "roles": {
            "I2S_BCLK":   ("psel", "i2s0", "I2S_SCK_M"),     # PCM1840 BCLK (I2S slave)
            "I2S_FSYNC":  ("psel", "i2s0", "I2S_LRCK_M"),    # PCM1840 FSYNC
            "I2S_SDOUT":  ("psel", "i2s0", "I2S_SDIN"),      # PCM1840 SDOUT -> nRF SDIN
            "UART_TX":    ("psel", "uart0", "UART_TX"),      # test pad TP1, console
            "UART_RX":    ("psel", "uart0", "UART_RX"),      # test pad TP2
            "ADC_SHDNZ":  ("user", "shdnz", "GPIO_ACTIVE_HIGH"),  # PCM1840 out of shutdown when high (R11 pull-down)
            "LED_BAT_OK": ("led", "led_bat_ok", "PK-8 green: battery OK"),
            "LED_BAT_LOW": ("led", "led_bat_low", "PK-8 red: battery low"),
            "LED_PEAK":   ("led", "led_peak", "PK-8 amber: peak >= -10 dBFS"),
            "LED_CLIP":   ("led", "led_clip", "PK-8 red: clip >= -7 dBFS"),
            "VBAT_SENSE": ("ain", "vbat", "BAT+"),            # cell divider, tapped at the cell
            "USB_D+": ("usb", "D+"), "USB_D-": ("usb", "D-"), "USB_VBUS": ("usb", "VBUS"),
        },
        # BT40NE module-internal nRF21540 wiring (Fanstel v1.09 p.21, ADR-0012): pads must be NC on the board.
        "fem": {"tx-en-gpios": "C2", "rx-en-gpios": "D2", "pdn-gpios": "D1", "mode-gpios": "E0", "ant-sel-gpios": "E1"},
        "fem_spi": ("Z6", "A6", "C6", "E2"),   # SCK, MOSI, MISO, CSN: SPI mode only, unused but must stay NC
    },
    "rx": {
        "net": "hw/rx/out/rx.net", "sym": "hw/rx/openpack_rx.kicad_sym", "module": "U1",
        "source": "hw/rx/rx.py, ADR-0014",
        "roles": {
            "I2S_BCK":   ("psel", "i2s0", "I2S_SCK_M"),      # PCM5102A BCK (3-wire, BCK PLL)
            "I2S_LRCK":  ("psel", "i2s0", "I2S_LRCK_M"),
            "I2S_SDOUT": ("psel", "i2s0", "I2S_SDOUT"),
            "UART_TX":   ("psel", "uart0", "UART_TX"),       # backplane to host, console + protocol
            "UART_RX":   ("psel", "uart0", "UART_RX"),
            "XSMT_EN":   ("user", "xsmt", "GPIO_ACTIVE_HIGH"),    # PCM5102A soft un-mute (100k pull-down)
            "OUT_EN":    ("user", "out-en", "GPIO_ACTIVE_HIGH"),  # relay K1 closed when high (100k pull-down)
            "SLOT0":     ("user", "slot", "GPIO_ACTIVE_HIGH"),    # slot strap bits, 10k pull-ups: GND = 0
            "SLOT1":     ("user", "slot", "GPIO_ACTIVE_HIGH"),
            "SLOT2":     ("user", "slot", "GPIO_ACTIVE_HIGH"),
            "LED_LOCK":  ("led", "led_lock", "RK-4 front panel: lock"),
            "LED_PEAK":  ("led", "led_peak", "RK-4 front panel: peak"),
            "BOOT":      ("key", "boot_btn", "BOOT strap: MCUboot serial recovery (low at reset)"),
            "ANT_SEL":   ("fwd", "ant-sel", "GPIO_ACTIVE_HIGH"),  # PE4259 CTRL, net core; low = antenna A
        },
        "fem": {}, "fem_spi": (),
    },
}
IGNORE = {"GND", "+3V3", "SWDIO", "SWDCLK", "nRESET"}   # power, SWD, reset: not firmware pins
BAD_PINS = {(0, 0): "LFXO XL1", (0, 1): "LFXO XL2", (0, 2): "NFC1", (0, 3): "NFC2"}
USB_PADS = {"D+", "D-", "VBUS"}


class PinError(Exception):
    pass


def resolve(board):
    """Netlist + symbol -> list of (net, pad, pin_name, role). Raises PinError on an impossible choice."""
    cfg = BOARDS[board]
    nets, comps = parse_netlist(ROOT / cfg["net"])
    mod = cfg["module"]
    pads = parse_symbol_pins(ROOT / cfg["sym"], comps[mod][1])
    on_module = {}
    for net, nodes in nets.items():
        for ref, pad in nodes:
            if ref == mod:
                on_module.setdefault(net, []).append(pad)
    errs, out, used = [], [], {}
    for net, padlist in sorted(on_module.items()):
        if net in IGNORE or net.startswith("+"):
            continue
        role = cfg["roles"].get(net)
        if role is None:
            errs.append(f"{board}: net {net} on module pad(s) {padlist} has no firmware role (add it to gen_pins.py)")
            continue
        if len(padlist) != 1:
            errs.append(f"{board}: net {net} on several module pads {padlist}")
            continue
        pad = padlist[0]
        name = pads[pad]
        if role[0] == "usb":
            if name != role[1]:
                errs.append(f"{board}: {net} on pad {pad} ({name}), USB needs the dedicated {role[1]} pad")
            continue
        g = gpio(name)
        if g is None:
            errs.append(f"{board}: {net} on pad {pad} ({name}) is not a GPIO")
            continue
        if (g[0], g[1]) in BAD_PINS:
            errs.append(f"{board}: {net} on P{g[0]}.{g[1]:02d}, the {BAD_PINS[g[0], g[1]]} pin")
        if role[0] == "ain" and g[2] is None:
            errs.append(f"{board}: {net} (ADC) on P{g[0]}.{g[1]:02d}, which has no SAADC input")
        if (g[0], g[1]) in used:
            errs.append(f"{board}: P{g[0]}.{g[1]:02d} carries {used[g[0], g[1]]} and {net}")
        used[g[0], g[1]] = net
        out.append((net, pad, name, role))
    for net in cfg["roles"]:
        if net not in on_module:
            errs.append(f"{board}: firmware role net {net} is not on the module")
    for prop, pad in list(cfg["fem"].items()) + [("spi", p) for p in cfg["fem_spi"]]:
        if any(net for net, pl in on_module.items() if pad in pl):
            errs.append(f"{board}: nRF21540 pad {pad} ({prop}) is wired on the board; it is module-internal")
        g = gpio(pads[pad])
        if (g[0], g[1]) in used:
            errs.append(f"{board}: FEM pin P{g[0]}.{g[1]:02d} also carries {used[g[0], g[1]]}")
    if errs:
        raise PinError("\n".join(errs))
    return out, pads, nets, comps


def divider(board, sense_net, top_net, nets, comps):
    """(full_ohms, output_ohms) of the resistor divider on sense_net between top_net and GND."""
    def other(ref, net):
        return next(n for n, nodes in nets.items() if n != net and any(r == ref for r, _ in nodes))
    rs = [ref for ref, _ in nets[sense_net] if ref.startswith("R")]
    top = [r for r in rs if other(r, sense_net) == top_net]
    bot = [r for r in rs if other(r, sense_net) == "GND"]
    if len(top) != 1 or len(bot) != 1:
        raise PinError(f"{board}: {sense_net} is not one resistor to {top_net} and one to GND ({rs})")
    rt, rb = ohms(comps[top[0]][0]), ohms(comps[bot[0]][0])
    return rt + rb, rb, top[0], bot[0]


# ---- output -----------------------------------------------------------------------------------------------------------

def pinstr(name):
    p, n, _ = gpio(name)
    return p, n


def header(board, core):
    cfg = BOARDS[board]
    return (f"/* GENERATED by fw/boards/openpack/gen_pins.py from {cfg['net']} ({cfg['source']}). Do not edit:\n"
            f" * change the schematic, rerun hw/{board}/{'pack' if board == 'pack' else 'rx'}.py, then gen_pins.py.\n"
            f" * openpack_{board}/nrf5340/{core}. tests/test_fw_board_pins.py checks it against the netlist. */\n\n")


def render_app(board):
    cfg = BOARDS[board]
    pins, pads, nets, comps = resolve(board)
    by = {}
    for net, pad, name, role in pins:
        by.setdefault(role[0], []).append((net, pad, name, role))
    s = [header(board, "cpuapp")]
    # pinctrl
    groups = {}
    for net, pad, name, role in by.get("psel", []):
        groups.setdefault(role[1], []).append((role[2], net, pad, name))
    s.append("&pinctrl {\n")
    for dev in sorted(groups):
        items = sorted(groups[dev])
        pulled = [i for i in items if i[0] == "UART_RX"]
        driven = [i for i in items if i[0] != "UART_RX"]

        def psels(lst, ind="\t\t\t"):
            return (",\n" + ind + "\t").join(
                f"<NRF_PSEL({fn}, {pinstr(nm)[0]}, {pinstr(nm)[1]})>" for fn, _, _, nm in lst) + ";"

        def comment(lst):
            return ", ".join(f"{fn}={net}@{pad}" for fn, net, pad, _ in lst)
        s.append(f"\t/* {dev}: {comment(items)} */\n")
        for state in ("default", "sleep"):
            s.append(f"\t{dev}_{state}: {dev}_{state} {{\n")
            gi = 1
            for lst, pull in ((driven, False), (pulled, True)):
                if not lst:
                    continue
                s.append(f"\t\tgroup{gi} {{\n\t\t\tpsels = {psels(lst)}\n")
                if state == "sleep":
                    s.append("\t\t\tlow-power-enable;\n")
                if pull:
                    s.append("\t\t\tbias-pull-up;\n")
                s.append("\t\t};\n")
                gi += 1
            s.append("\t};\n")
    s.append("};\n\n")
    for dev in sorted(groups):
        s.append(f"&{dev} {{\n\tpinctrl-0 = <&{dev}_default>;\n\tpinctrl-1 = <&{dev}_sleep>;\n"
                 f"\tpinctrl-names = \"default\", \"sleep\";\n}};\n\n")
    s.append("/ {\n")
    if by.get("led"):
        s.append("\tleds {\n\t\tcompatible = \"gpio-leds\";\n")
        for net, pad, name, role in by["led"]:
            p, n = pinstr(name)
            s.append(f"\t\t{role[1]}: {role[1]} {{\n\t\t\tgpios = <&gpio{p} {n} GPIO_ACTIVE_HIGH>; /* {net}@{pad} */\n"
                     f"\t\t\tlabel = \"{role[2]}\";\n\t\t}};\n")
        s.append("\t};\n\n")
    if by.get("key"):
        s.append("\tbuttons {\n\t\tcompatible = \"gpio-keys\";\n")
        for net, pad, name, role in by["key"]:
            p, n = pinstr(name)
            s.append(f"\t\t{role[1]}: {role[1]} {{\n\t\t\tgpios = <&gpio{p} {n} GPIO_ACTIVE_LOW>; /* {net}@{pad}, "
                     f"external pull-up */\n\t\t\tlabel = \"{role[2]}\";\n\t\t\tzephyr,code = <INPUT_KEY_0>;\n\t\t}};\n")
        s.append("\t};\n\n\taliases {\n")
        for net, pad, name, role in by["key"]:
            s.append(f"\t\tmcuboot-button0 = &{role[1]};\n")
        s.append("\t};\n\n")
    users = {}
    for net, pad, name, role in by.get("user", []):
        users.setdefault(role[1], []).append((net, pad, name, role[2]))
    if users:
        s.append("\tzephyr,user {\n")
        for prop in sorted(users):
            lst = sorted(users[prop])
            cells = ", ".join(f"<&gpio{pinstr(nm)[0]} {pinstr(nm)[1]} {fl}>" for _, _, nm, fl in lst)
            s.append(f"\t\t{prop}-gpios = {cells}; /* {', '.join(f'{n}@{p}' for n, p, _, _ in lst)} */\n")
        s.append("\t};\n\n")
    for net, pad, name, role in by.get("ain", []):
        full, out, rt, rb = divider(board, net, role[2], nets, comps)
        s.append(f"\t{role[1]}: {role[1]} {{\n\t\tcompatible = \"voltage-divider\";\n\t\tio-channels = <&adc 0>;\n"
                 f"\t\t/* {net}@{pad} ({name}): {rt} {comps[rt][0]} from {role[2]}, {rb} {comps[rb][0]} to GND */\n"
                 f"\t\toutput-ohms = <{out}>;\n\t\tfull-ohms = <{full}>;\n\t}};\n\n")
    fwd = [(prop, pads[pad], f"nRF21540 {prop}@{pad}") for prop, pad in cfg["fem"].items()]
    fwd += [(role[1], name, f"{net}@{pad}") for net, pad, name, role in by.get("fwd", [])]
    if fwd:
        s.append("\t/* net-core pins, handed over at net-core boot (SOC_NRF_GPIO_FORWARDER_FOR_NRF5340) */\n"
                 "\tgpio_fwd: nrf-gpio-forwarder {\n\t\tcompatible = \"nordic,nrf-gpio-forwarder\";\n"
                 "\t\tstatus = \"okay\";\n\n\t\tnet {\n\t\t\tgpios = ")
        s.append(",\n\t\t\t\t".join(f"<&gpio{pinstr(nm)[0]} {pinstr(nm)[1]} 0>" for _, nm, _ in fwd))
        s.append(f";\n\t\t\t/* {', '.join(c for _, _, c in fwd)} */\n\t\t}};\n\t}};\n")
    s.append("};\n")
    for net, pad, name, role in by.get("ain", []):
        ain = gpio(name)[2]
        s.append(f"\n&adc {{\n\t#address-cells = <1>;\n\t#size-cells = <0>;\n\n\tchannel@0 {{\n\t\treg = <0>;\n"
                 f"\t\tzephyr,gain = \"ADC_GAIN_1_6\"; /* 3.6 V full scale vs. 2.1 V at 4.2 V cell */\n"
                 f"\t\tzephyr,reference = \"ADC_REF_INTERNAL\";\n"
                 f"\t\tzephyr,acquisition-time = <ADC_ACQ_TIME(ADC_ACQ_TIME_MICROSECONDS, 40)>; /* high-Z divider */\n"
                 f"\t\tzephyr,input-positive = <NRF_SAADC_AIN{ain}>; /* {net}@{pad} {name} */\n"
                 f"\t\tzephyr,resolution = <12>;\n\t\tzephyr,oversampling = <4>;\n\t}};\n}};\n")
    return "".join(s)


def render_net(board):
    cfg = BOARDS[board]
    pins, pads, _, _ = resolve(board)
    s = [header(board, "cpunet")]
    if cfg["fem"]:
        s.append("/* BT40NE nRF21540 front-end (#107), GPIO mode. Module-internal wiring, Fanstel v1.09 p.21; the pads are\n"
                 " * NC on the board (checked). ANT_SEL level for the u.FL is CONFIG_OP_FEM_ANT_SEL_UFL (unverified). */\n"
                 "/ {\n\tnrf_radio_fem: nrf21540_fem {\n\t\tcompatible = \"nordic,nrf21540-fem\";\n")
        for prop, pad in cfg["fem"].items():
            p, n = pinstr(pads[pad])
            s.append(f"\t\t{prop} = <&gpio{p} {n} GPIO_ACTIVE_HIGH>; /* pad {pad} */\n")
        s.append("\t};\n};\n\n&radio {\n\tfem = <&nrf_radio_fem>;\n};\n")
    fwd = [(net, pad, name, role) for net, pad, name, role in pins if role[0] == "fwd"]
    if fwd:
        s.append("/ {\n\tzephyr,user {\n")
        for net, pad, name, role in fwd:
            p, n = pinstr(name)
            s.append(f"\t\t{role[1]}-gpios = <&gpio{p} {n} {role[2]}>; /* {net}@{pad} */\n")
        s.append("\t};\n};\n")
    return "".join(s)


def outputs():
    for board in BOARDS:
        d = HERE / f"openpack_{board}"
        yield d / f"openpack_{board}_nrf5340_cpuapp-pins.dtsi", render_app(board)
        yield d / f"openpack_{board}_nrf5340_cpunet-pins.dtsi", render_net(board)


# ---- compiled devicetree check ------------------------------------------------------------------------------------------
# A build's zephyr.dts is the merged devicetree the firmware really gets (board dts + common dtsi + app overlays), so a
# hand-written overlay that moves a pin, or a stray SoC/DK node on a board pin, shows up here even if the -pins.dtsi
# files are current.
FUN = {"UART_TX": 0, "UART_RX": 1, "I2S_SCK_M": 13, "I2S_LRCK_M": 15, "I2S_SDIN": 17, "I2S_SDOUT": 18}
_TOK = re.compile(r'"(?:\\.|[^"\\])*"|<[^>]*>|\[[^\]]*\]|[{};=]|[^\s{};=<"\[]+')  # names keep commas


class Node:
    def __init__(self, name, labels):
        self.name, self.labels, self.props, self.children = name, labels, {}, []

    def walk(self):
        yield self
        for c in self.children:
            yield from c.walk()


def parse_dts(text):
    """Merged zephyr.dts text -> root Node. Property values are kept as token lists ('<...>' cells, '"str"')."""
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    text = re.sub(r"//[^\n]*", "", text)
    toks = _TOK.findall(text)
    root, stack, stmt = Node("", []), [], []
    cur = root
    for tok in toks:
        if tok == "{":
            labels = [s[:-1] for s in stmt if s.endswith(":")]
            names = [s for s in stmt if not s.endswith(":")]
            name = names[-1] if names else ""
            if name == "/" and not stack:
                node = root
            else:
                node = Node(name, labels)
                cur.children.append(node)
            stack.append(cur)
            cur, stmt = node, []
        elif tok == "}":
            cur, stmt = stack.pop(), []
        elif tok == ";":
            if stmt and not stmt[0].startswith("/"):
                name = stmt[0]
                cur.props[name] = [v for v in stmt[2:] if v != ","] if len(stmt) > 1 and stmt[1] == "=" else []
            stmt = []
        else:
            stmt.append(tok)
    return root


def _cells(vals):
    return [c for v in vals if v.startswith("<") for c in v[1:-1].split()]


def _int(s):
    return int(s, 0)


def _gpio_specs(vals):
    """['< &gpio1 0x5 0x0 >', ...] -> [(port, pin, flags)]."""
    cells, out = _cells(vals), []
    i = 0
    while i < len(cells):
        m = re.fullmatch(r"&gpio([01])", cells[i])
        if m and i + 2 < len(cells):
            out.append((int(m.group(1)), _int(cells[i + 1]), _int(cells[i + 2])))
            i += 3
        else:
            i += 1
    return out


def expectations(board, core):
    """What the netlist says the compiled devicetree must contain, for one board and core."""
    cfg = BOARDS[board]
    pins, pads, nets, comps = resolve(board)
    e = {"psel": {}, "led": {}, "key": {}, "user": {}, "ain": [], "fwd": [], "fem": {}, "netuser": {}}
    for net, pad, name, role in pins:
        p, n, ain = gpio(name)
        kind = role[0]
        if kind == "psel":
            e["psel"].setdefault(role[1], {})[role[2]] = (p, n, net)
        elif kind in ("led", "key"):
            e[kind][role[1]] = (p, n, net)
        elif kind == "user":
            e["user"].setdefault(role[1], []).append((net, p, n))
        elif kind == "ain":
            full, out, _, _ = divider(board, net, role[2], nets, comps)
            e["ain"].append((role[1], ain, out, full, p, n, net))
        elif kind == "fwd":
            e["fwd"].append((p, n, net))
            e["netuser"][role[1]] = (p, n, net)
    for prop, pad in cfg["fem"].items():
        p, n, _ = gpio(pads[pad])
        e["fem"][prop] = (p, n, f"nRF21540 {prop}")
    e["fwd"] = [(p, n, c) for p, n, c in ([(*v[:2], v[2]) for v in e["fem"].values()] + e["fwd"])]
    for k in e["user"]:
        e["user"][k] = [(p, n, net) for net, p, n in sorted(e["user"][k])]
    allowed = {(p, n) for kind in ("led", "key") for p, n, _ in e[kind].values()}
    allowed |= {(p, n) for d in e["psel"].values() for p, n, _ in d.values()}
    allowed |= {(p, n) for v in e["user"].values() for p, n, _ in v}
    allowed |= {(p, n) for _, _, _, _, p, n, _ in e["ain"]}
    allowed |= {(p, n) for p, n, _ in e["fwd"]}
    e["allowed"] = allowed
    return e


def check_compiled(text):
    """Errors in one merged zephyr.dts against the netlist, or None if it is not an openpack board."""
    root = parse_dts(text)
    compat = " ".join(root.props.get("compatible", []))
    m = re.search(r"openpack,openpack-(pack|rx)-nrf5340-(cpuapp|cpunet)", compat)
    if not m:
        return None
    board, core = m.groups()
    e = expectations(board, core)
    errs = []
    by_label = {lab: nd for nd in root.walk() for lab in nd.labels}
    tag = f"openpack_{board}/{core}"

    def want(what, got, exp):
        if got != exp:
            errs.append(f"{tag}: {what}: devicetree {got}, netlist {exp}")

    used = set()
    for nd in root.walk():  # every GPIO and pinctrl pin the firmware can touch
        for prop, vals in nd.props.items():
            if prop.endswith("gpios") or prop == "gpios":
                used |= {(p, n) for p, n, _ in _gpio_specs(vals)}
            if prop == "psels":
                for c in _cells(vals):
                    pin = _int(c) & 0x1FF
                    used.add((pin // 32, pin % 32))
    for p, n in sorted(used - e["allowed"]):
        errs.append(f"{tag}: P{p}.{n:02d} is used in the devicetree but the netlist gives it no firmware role")

    if core == "cpuapp":
        for dev, fns in e["psel"].items():
            nd = by_label.get(dev)
            if nd is None:
                errs.append(f"{tag}: no {dev} node")
                continue
            want(f"{dev} status", nd.props.get("status"), ['"okay"'])
            for i, state in enumerate(("default", "sleep")):
                ref = _cells(nd.props.get(f"pinctrl-{i}", []))
                st = by_label.get(ref[0][1:]) if ref else None
                if st is None:
                    errs.append(f"{tag}: {dev} has no pinctrl-{i} ({state})")
                    continue
                got = {}
                for g in st.children:
                    for c in _cells(g.props.get("psels", [])):
                        x = _int(c)
                        got[x >> 24] = ((x & 0x1FF) // 32, (x & 0x1FF) % 32)
                exp = {FUN[fn]: (p, n) for fn, (p, n, _) in fns.items()}
                want(f"{dev} {state} psels (function: (port, pin))", got, exp)
        for kind, flag in (("led", 0), ("key", 1)):
            for lab, (p, n, net) in e[kind].items():
                nd = by_label.get(lab)
                got = _gpio_specs(nd.props.get("gpios", [])) if nd else None
                want(f"{lab} ({net})", got, [(p, n, flag)])
        user = next((nd for nd in root.children if nd.name == "zephyr,user"), None)
        for prop, lst in e["user"].items():
            got = [(p, n) for p, n, _ in _gpio_specs(user.props.get(f"{prop}-gpios", []))] if user else None
            want(f"zephyr,user {prop}-gpios ({', '.join(c for *_, c in lst)})", got, [(p, n) for p, n, _ in lst])
        for lab, ain, out, full, p, n, net in e["ain"]:
            nd = by_label.get(lab)
            if nd is None:
                errs.append(f"{tag}: no {lab} voltage-divider node")
                continue
            want(f"{lab} output/full ohms", (_int(_cells(nd.props["output-ohms"])[0]),
                                             _int(_cells(nd.props["full-ohms"])[0])), (out, full))
            ch = _cells(nd.props.get("io-channels", []))
            adc = by_label.get("adc")
            chan = next((c for c in adc.children if _cells(c.props.get("reg", []))[:1] == [ch[1]]), None) \
                if adc and len(ch) == 2 else None
            got = _int(_cells(chan.props["zephyr,input-positive"])[0]) if chan else None
            want(f"{lab} SAADC input ({net}, P{p}.{n:02d})", got, ain)
            want("adc status", adc.props.get("status") if adc else None, ['"okay"'])
        fwd = by_label.get("gpio_fwd")
        if e["fwd"]:
            got = sorted((p, n) for c in (fwd.children if fwd else []) for p, n, _ in _gpio_specs(c.props["gpios"]))
            want("gpio forwarder (net-core pins)", got, sorted((p, n) for p, n, _ in e["fwd"]))
    else:
        fem = by_label.get("nrf_radio_fem")
        if e["fem"]:
            got = {k: _gpio_specs(fem.props.get(k, []))[0][:2] for k in e["fem"]} if fem else None
            want("nRF21540 FEM pins", got, {k: (p, n) for k, (p, n, _) in e["fem"].items()})
        elif fem is not None and fem.props.get("status") != ['"disabled"']:
            errs.append(f"{tag}: nRF21540 node present on a board without the FEM")
        user = next((nd for nd in root.children if nd.name == "zephyr,user"), None)
        for prop, (p, n, net) in e["netuser"].items():
            got = [s[:2] for s in _gpio_specs(user.props.get(f"{prop}-gpios", []))] if user else None
            want(f"net zephyr,user {prop}-gpios ({net})", got, [(p, n)])
    return errs


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--check", action="store_true", help="exit 1 if the generated files are stale")
    ap.add_argument("--check-dts", nargs="+", metavar="DIR", help="build dirs: check every zephyr.dts below them")
    a = ap.parse_args(argv)
    try:
        outs = list(outputs())
    except PinError as e:
        print(f"gen_pins: impossible or unmapped pin choice:\n{e}", file=sys.stderr)
        return 2
    if a.check_dts:
        bad, files = 0, []
        for f in (f for d in a.check_dts for f in sorted(pathlib.Path(d).rglob("zephyr/zephyr.dts"))):
            errs = check_compiled(f.read_text())
            if errs is None:
                continue  # not an openpack board (native_sim, bsim, DK)
            files.append(f)
            print(f"{f}: {'OK' if not errs else 'FAIL'}" + "".join(f"\n  {e}" for e in errs))
            bad += bool(errs)
        if not files:
            print("gen_pins: no openpack zephyr.dts found", file=sys.stderr)
            return 1
        return 1 if bad else 0
    stale = []
    for path, text in outs:
        if not path.exists() or path.read_text() != text:
            stale.append(path)
            if not a.check:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(text)
    for p in stale:
        print(f"{'stale' if a.check else 'wrote'} {p.relative_to(ROOT)}")
    return 1 if (a.check and stale) else 0


if __name__ == "__main__":
    sys.exit(main())
