"""PK-1..PK-6, PK-9, PK-12 (#31): the SKiDL pack schematic builds, passes ERC, and the committed BOM is current."""
import builtins, csv, pathlib, sys
import pytest

pytest.importorskip("skidl")
PACK = pathlib.Path(__file__).resolve().parents[1] / "hw/pack"
sys.path.insert(0, str(PACK))


def test_pack_erc_and_bom(tmp_path, monkeypatch):
    import pack
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
