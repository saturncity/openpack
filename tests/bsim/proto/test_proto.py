"""#25: drive the bsim firmware's UART pty with the host's own client (host/modules.py request()).
Needs BSIM_OUT_PATH plus FW_RX_EXE (rx role) and/or FW_PACK_EXE (pack role); skipped otherwise.
-uart_pty_wait spins and ignores SIGTERM, so everything runs under timeout -s KILL.
The sim is not paced to wall time (it runs flat out), so sim_length is long and the processes are killed at teardown.
"""
import os
import re
import signal
import subprocess
import sys
import tempfile
import time

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))
from host import modules

BSIM = os.environ.get("BSIM_OUT_PATH")


def _boot(exe):
    if not (BSIM and exe and os.path.exists(exe)):
        pytest.skip("BSIM_OUT_PATH / firmware exe not set")
    sim = f"proto_{os.getpid()}_{int(time.time() * 1000) % 100000}"
    d = tempfile.mkdtemp()
    log = os.path.join(d, "dev.log")
    bindir = os.path.join(BSIM, "bin")
    procs = [
        subprocess.Popen(["timeout", "-s", "KILL", "120", "./bs_2G4_phy_v1", f"-s={sim}", "-D=1",
                          "-sim_length=100000000000"], cwd=bindir, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT, start_new_session=True),
        subprocess.Popen(["timeout", "-s", "KILL", "120", os.path.realpath(exe), f"-s={sim}", "-d=0", "-uart0_pty",
                          "-uart_pty_wait"], cwd=bindir, stdout=open(log, "w"), stderr=subprocess.STDOUT, start_new_session=True),
    ]
    path = None
    end = time.time() + 30
    while time.time() < end and not path:
        m = re.search(r"/dev/pts/\d+", open(log, errors="replace").read())
        path = m.group(0) if m else None
        time.sleep(0.2)
    if not path:
        for p in procs:
            os.killpg(p.pid, signal.SIGKILL)
        pytest.fail("no pty announced")
    # first reply proves the firmware is up (boot banner printk is flushed by request())
    end = time.time() + 30
    while True:
        try:
            modules.request(path, "info", timeout=1.0)
            break
        except modules.ModuleError:
            assert time.time() < end, "firmware never answered"
    return path, procs


def _stop(procs):
    for p in procs:  # kill the whole group: `timeout` would otherwise orphan its child
        try:
            os.killpg(p.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        p.wait()


@pytest.fixture(scope="module")
def rx():
    path, procs = _boot(os.environ.get("FW_RX_EXE"))
    yield path
    _stop(procs)


@pytest.fixture(scope="module")
def pack():
    path, procs = _boot(os.environ.get("FW_PACK_EXE"))
    yield path
    _stop(procs)


def kv(text):
    return dict(p.split("=", 1) for p in text.split())


def test_rx_info(rx):
    assert re.fullmatch(r"fw=\S+", modules.request(rx, "info"))


def test_rx_status_10hz(rx):
    """RX-9 / PK-10: telemetry reply parses and carries every host/PROTOCOL.md field; 10 Hz poll keeps up."""
    t0 = time.time()
    for _ in range(20):
        f = kv(modules.request(rx, "status", timeout=0.5))
        assert set(f) == {"locked", "rssi", "loss", "batt", "peak", "clip", "temp", "td"}
        assert f["td"] == "0"  # no pack on air: nothing seen in time-diversity mode (ADR-0017)
        assert f["locked"] in ("0", "1") and f["clip"] in ("0", "1") and f["temp"] in ("0", "1")
        assert -127 <= int(f["rssi"]) <= 0
        assert 0 <= float(f["loss"]) <= 1
        assert 0 <= int(f["batt"]) <= 100
        assert -63 <= int(f["peak"]) <= 0
        time.sleep(0.1 - ((time.time() - t0) % 0.1))
    assert time.time() - t0 < 4.0


def test_rx_stats_real_counters(rx):
    """#25 item 1: status/stats come from the app core's counters (#24), not a stub. No pack on air: nothing locked, all zero."""
    f = kv(modules.request(rx, "status"))
    assert f["locked"] == "0" and f["rssi"] == "0" and f["loss"] == "0.000" and f["batt"] == "0"
    s = kv(modules.request(rx, "stats"))
    assert set(s) == {"frames", "valid", "lost", "plc", "a_ok", "b_ok", "skips", "td_rec", "under", "over",
                      "fill_milli", "ppb"}
    assert all(v == "0" for v in s.values())


def test_dfu_refused_without_mcuboot(rx):
    """#25 `dfu`: bsim has no MCUboot, so both forms are refused with an early err (the host never streams a payload)."""
    for cmd in ("dfu", "dfu 1024"):
        with pytest.raises(modules.ModuleError, match="^err dfu"):
            modules.request(rx, cmd)


def test_rx_commands(rx):
    assert modules.request(rx, "pair 3 2424 2473") == ""
    assert modules.request(rx, "trim -3.5") == ""
    assert modules.request(rx, "td on") == "" and modules.request(rx, "td") == "td=on"
    scan = modules.request(rx, "scan").split()
    assert len(scan) == 42 and scan[0] == "2400:-100" and scan[-1] == "2482:-100"
    with pytest.raises(modules.ModuleError, match="^err "):
        modules.request(rx, "pair 3 2424 2450")
    with pytest.raises(modules.ModuleError, match="^err "):
        modules.request(rx, "nonsense")


def test_pack_cdc_commands(pack):
    """PK-9 on the console (UART pty on bsim)."""
    assert kv(modules.request(pack, "info"))["role"] == "pack"
    assert modules.request(pack, "id 4") == ""
    assert modules.request(pack, "id") == "id=4"
    assert modules.request(pack, "chan 2410 2460") == ""
    assert modules.request(pack, "chan") == "chan=2410,2460"
    assert modules.request(pack, "power -8") == ""
    assert modules.request(pack, "region eu") == ""
    assert modules.request(pack, "td") == "td=off"  # ADR-0017: off by default
    assert modules.request(pack, "td on") == ""
    assert modules.request(pack, "save") == ""
    f = kv(modules.request(pack, "info"))
    assert (f["id"], f["chan"], f["power"], f["region"], f["td"]) == ("4", "2410,2460", "-8", "eu", "on")
    for bad in ("id 9", "chan 2410 2420", "power 20", "region zz", "td yes"):
        with pytest.raises(modules.ModuleError, match="^err "):
            modules.request(pack, bad)
