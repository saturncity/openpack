"""#118: the openpack_pack / openpack_rx devicetree pins come from the schematic netlists, and nothing else.

Source: the committed *-pins.dtsi files are exactly what fw/boards/openpack/gen_pins.py renders from hw/*/out/*.net,
and every pin they name is the module pad the netlist puts that net on. Compiled: a build's merged zephyr.dts (board +
overlays) still matches the netlist. CI runs the compiled check on the twister builds (fw.yml); locally, point
OPENPACK_FW_BUILDS at sysbuild build dirs (colon-separated) to run it here.
"""
import copy, importlib.util, os, pathlib, re
import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("gen_pins", ROOT / "fw/boards/openpack/gen_pins.py")
gp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gp)


def test_generated_files_current():
    assert gp.main(["--check"]) == 0, "rerun python3 fw/boards/openpack/gen_pins.py"


@pytest.mark.parametrize("board", sorted(gp.BOARDS))
def test_source_pins_match_netlist(board):
    """Each '<&gpioP N ...>; /* NET@PAD */' and NRF_PSEL in the committed dtsi is the netlist's pad for that net."""
    pins, pads, nets, comps = gp.resolve(board)
    by_net = {net: gp.gpio(name)[:2] for net, pad, name, _ in pins}
    text = (gp.HERE / f"openpack_{board}/openpack_{board}_nrf5340_cpuapp-pins.dtsi").read_text()
    seen = set()
    for m in re.finditer(r"gpios = <&gpio([01]) (\d+) \w+>; /\* (\w+)@", text):
        assert by_net[m.group(3)] == (int(m.group(1)), int(m.group(2))), m.group(0)
        seen.add(m.group(3))
    for m in re.finditer(r"/\* (\w+): ([^*]*) \*/", text):  # pinctrl group comment: FN=NET@PAD
        for fn, net in re.findall(r"(\w+)=(\S+?)@", m.group(2)):
            got = re.search(rf"NRF_PSEL\({fn}, (\d), (\d+)\)", text)
            assert (int(got.group(1)), int(got.group(2))) == by_net[net], (fn, net)
            seen.add(net)
    leds_keys_psel = {net for net, _, _, role in pins if role[0] in ("led", "key", "psel")}
    assert leds_keys_psel <= seen


@pytest.mark.parametrize("board", sorted(gp.BOARDS))
def test_generator_refuses_unmapped_net(board, monkeypatch):
    cfg = copy.deepcopy(gp.BOARDS)
    net = next(n for n, r in cfg[board]["roles"].items() if r[0] == "psel")
    del cfg[board]["roles"][net]
    monkeypatch.setattr(gp, "BOARDS", cfg)
    with pytest.raises(gp.PinError, match=f"net {net} .* has no firmware role"):
        gp.resolve(board)


def test_generator_refuses_two_roles_one_pin(monkeypatch):
    cfg = copy.deepcopy(gp.BOARDS)
    cfg["pack"]["fem"]["mode-gpios"] = "C3"  # Fanstel p.22 sample: MODE on P0.24, the pack's I2S BCLK
    monkeypatch.setattr(gp, "BOARDS", cfg)
    with pytest.raises(gp.PinError, match="FEM pin P0.24 also carries I2S_BCLK"):
        gp.resolve("pack")


def _builds():
    dirs = [pathlib.Path(d) for d in os.environ.get("OPENPACK_FW_BUILDS", "").split(":") if d]
    return [f for d in dirs for f in sorted(d.rglob("zephyr/zephyr.dts"))
            if gp.check_compiled(f.read_text()) is not None]


@pytest.mark.skipif(not _builds(), reason="set OPENPACK_FW_BUILDS to openpack build dirs (CI: fw.yml twister step)")
def test_compiled_dts_matches_netlist_and_catches_a_moved_pin():
    for f in _builds():
        text = f.read_text()
        assert gp.check_compiled(text) == [], f
        # negative control: move the first GPIO the board uses by one pin; the check must notice
        m = re.search(r"(<\s*&gpio[01] )(0x[0-9a-f]+)", text)
        bad = text[:m.start(2)] + hex(int(m.group(2), 16) ^ 1) + text[m.end(2):]
        assert gp.check_compiled(bad), f"moved pin not caught in {f}"
