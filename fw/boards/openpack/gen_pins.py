#!/usr/bin/env python3
"""Generate the openpack_pack / openpack_rx pin devicetree from the SKiDL netlists (#118).

Every nRF5340 pin number in fw/boards/openpack/ comes from here, never by hand:
  hw/pack/out/pack.net, hw/rx/out/rx.net   (KiCad netlists written by hw/pack/pack.py, hw/rx/rx.py)
  hw/pack/openpack.kicad_sym, hw/rx/openpack_rx.kicad_sym   (module pad -> nRF5340 pin names)

  python3 fw/boards/openpack/gen_pins.py            rewrite the *-pins.dtsi files
  python3 fw/boards/openpack/gen_pins.py --check    exit 1 if they are stale (CI, tests/test_fw_board_pins.py)
  python3 fw/boards/openpack/gen_pins.py --check-dts BUILD_DIR...   check compiled zephyr.dts files against the netlist

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
FUN = {0: "UART_TX", 1: "UART_RX", 13: "I2S_SCK_M", 15: "I2S_LRCK_M", 17: "I2S_SDIN", 18: "I2S_SDOUT"}


def compiled_pins(dts_text):
    """zephyr.dts -> {(kind, name): [(port, pin)]}: pinctrl functions per device, and every <&gpioN pin flags>."""
    found = {}
    for m in re.finditer(r"(\w+): (\w+)_default \{(.*?)\n\t\t\};", dts_text, re.S):
        dev = m.group(2)
        for v in re.findall(r"psels = <([^>]*)>", m.group(3)):
            for word in v.split():
                x = int(word, 0)
                fn, pin = x >> 24, x & 0x1FF
                found.setdefault(("psel", f"{dev}.{FUN.get(fn, fn)}"), []).append((pin // 32, pin % 32))
    for m in re.finditer(r"([\w-]+)-gpios = ((?:<&gpio[01] 0x[0-9a-f]+ 0x[0-9a-f]+>(?:, )?)+);", dts_text):
        for p, n in re.findall(r"<&gpio([01]) (0x[0-9a-f]+) 0x[0-9a-f]+>", m.group(2)):
            found.setdefault(("gpio", m.group(1)), []).append((int(p), int(n, 16)))
    for m in re.finditer(r"(\w+) \{\n\t+gpios = <&gpio([01]) (0x[0-9a-f]+) 0x[0-9a-f]+>;", dts_text):
        found.setdefault(("gpio", m.group(1)), []).append((int(m.group(2)), int(m.group(3), 16)))
    for m in re.finditer(r"zephyr,input-positive = <(0x[0-9a-f]+)>", dts_text):
        found.setdefault(("ain", "adc"), []).append(int(m.group(1), 16))
    return found


def net_pins(board):
    """{net: (port, pin, ain)} for every module pad on a net, plus the FEM props."""
    cfg = BOARDS[board]
    nets, comps = parse_netlist(ROOT / cfg["net"])
    pads = parse_symbol_pins(ROOT / cfg["sym"], comps[cfg["module"]][1])
    out = {}
    for net, nodes in nets.items():
        for ref, pad in nodes:
            if ref == cfg["module"] and gpio(pads[pad]):
                out[net] = gpio(pads[pad])
    for prop, pad in cfg["fem"].items():
        out["FEM:" + prop] = gpio(pads[pad])
    return out


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
        sys.path.insert(0, str(ROOT / "tests"))
        from test_fw_board_pins import check_compiled  # one expectation table, in the test
        bad = 0
        files = [f for d in a.check_dts for f in sorted(pathlib.Path(d).rglob("zephyr/zephyr.dts"))]
        for f in files:
            errs = check_compiled(f.read_text())
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
