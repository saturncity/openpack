"""PK-1..PK-6, PK-9, PK-12 (#31): the SKiDL pack schematic builds, passes ERC, and the committed BOM is current."""
import builtins, csv, importlib.util, os, pathlib
import pytest

if os.environ.get("CI"):
    import skidl  # noqa: F401  (CI must have it: a skip there would hide a broken schematic)
else:
    pytest.importorskip("skidl")
PACK = pathlib.Path(__file__).resolve().parents[1] / "hw/pack"


def _load_pack():  # by path: mech/pack.py is also importable as "pack"
    spec = importlib.util.spec_from_file_location("hw_pack_sch", PACK / "pack.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_pack_erc_and_bom(tmp_path, monkeypatch):
    pack = _load_pack()
    monkeypatch.chdir(tmp_path)  # SKiDL writes log files into the cwd
    pack.build()
    assert pack.erc() == (0, 0)
    rows = pack.bom_rows(builtins.default_circuit)
    with open(PACK / "out/bom.csv") as f:
        committed = list(csv.DictReader(f))
    assert [{k: str(v) for k, v in r.items()} for r in rows] == committed, "run python hw/pack/pack.py --no-sch"
    assert sum(float(r["ext_usd"]) for r in rows) <= 35.0  # PK-12
    net = {(p.ref, str(pin.num)): (pin.net.name if pin.net else None) for p in builtins.default_circuit.parts for pin in p.pins}
    assert [net["J1", n] for n in "TRS"] == ["MIC", "GND", "GND"]          # Sennheiser SK mic pinout (ADR-0012)
    assert {net["R5", "1"], net["R5", "2"]} == {"+5V_BIAS", "MIC"}           # PK-1: 2.2k bias from the filtered rail
    assert {net["R4", "1"], net["R4", "2"]} == {"+5V", "+5V_BIAS"}           # 100R + 47u filter (#31)
    fem = ("Z6", "A6", "C2", "C6", "D1", "D2", "E0", "E1", "E2")              # nRF21540 control inside the module
    assert {net["U1", n] for n in fem} == {"__NOCONNECT"}
    assert [net["U1", n] for n in ("C3", "C4", "C5", "E4", "E5")] == ["I2S_BCLK", "I2S_FSYNC", "I2S_SDOUT", "USB_D+", "USB_D-"]
    # PCM1840 straps: MSZ=0 (slave), FMT1=FMT0=1 (I2S), MD0=1 (low latency), MD1=1 (DRE); SHDNZ pulled low
    assert [net["U2", n] for n in ("17", "15", "16", "18", "20")] == ["GND", "+3V3", "+3V3", "+3V3", "+3V3"]
    assert {net["R11", "1"], net["R11", "2"]} == {"ADC_SHDNZ", "GND"}
    # supplies: ADC AVDD analog 3.3 V, IOVDD digital 3.3 V; op-amp 5 V; module VDD = VDDH = 3.3 V, VBUS from USB
    assert (net["U2", "1"], net["U2", "19"], net["U3", "8"], net["U3", "4"]) == ("+3V3A", "+3V3", "+5V", "GND")
    assert (net["U1", "9"], net["U1", "F4"], net["U1", "F6"]) == ("+3V3", "+3V3", "USB_VBUS")
    assert (net["U5", "1"], net["U5", "5"], net["U6", "1"], net["U6", "5"]) == ("VSYS", "+3V3", "+5V", "+3V3A")
    # reverse-polarity FET: drain at the cell, source to the switch; cell sensed ahead of FET and switch
    assert (net["Q1", "3"], net["Q1", "2"], net["R12", "1"]) == ("BAT+", "VBAT_RP", "BAT+")
    # front end: VCM from 180k/100k (OPA1656 CM range); hot-plug clamp + 100R ahead of both + inputs
    assert (net["R7", "1"], net["R7", "2"], net["U3", "3"], net["U3", "5"]) == ("+5V", "VCM", "PRE_INP", "PRE_INP")
    assert [net["D6", n] for n in "123"] == ["GND", "+5V", "PRE_NP"]
    assert {net["D5", "1"], net["D5", "2"]} == {"MIC", "GND"}
