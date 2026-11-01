"""#30 / G3: the FastAPI host against real bsim receiver firmware on UART ptys (skips without BSIM_OUT_PATH / FW_RX_EXE).

Slots 1, 3 and 6 are bsim receivers, the other five are absent. The bsim console also prints boot banners and log
lines, which the host must skip (fw/PROTOCOL.md). A receiver reboot is a kill + a new sim: the pty path changes.
"""
import os
import signal
import sys
import time

import pytest
from fastapi.testclient import TestClient

HERE = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(HERE, "..", "proto"))
from host.app import app  # noqa: E402
from test_proto import _boot, _stop  # noqa: E402

pytestmark = pytest.mark.timeout(240)
SLOTS = (1, 3, 6)
EXE = os.environ.get("FW_RX_EXE")


@pytest.fixture(scope="module")
def bench():
    sims = {}
    try:
        for n in SLOTS:
            sims[n] = _boot(EXE)  # {slot: (pty path, procs)}
        ports = ["/dev/openpack-absent"] * 8
        for n, (path, _) in sims.items():
            ports[n - 1] = path
        app.state.ports = ports
        yield sims
    finally:
        for _, procs in sims.values():
            _stop(procs)


@pytest.fixture
def c(bench):
    app.state.scan_cache = None
    return TestClient(app)


def test_packs_rx_present_and_absent(c):
    p = c.get("/packs").json()
    assert [e["status"] is not None for e in p] == [n in SLOTS for n in range(1, 9)]
    assert all(set(e["status"]) == {"locked", "rssi", "loss", "batt", "peak", "clip", "temp", "td"} for e in p if e["status"])
    assert all("error" in e for e in p if e["status"] is None)
    rx = c.get("/rx").json()
    assert [e.get("fw") for e in rx if "fw" in e] == ["0.1.0"] * 3


def test_commands(c):
    assert c.put("/packs/3/trim", json={"gain_db": -3.5}).status_code == 200
    assert c.put("/packs/2/trim", json={"gain_db": 0}).status_code == 504  # absent slot
    assert c.put("/rx/3/pair", json={"pack": 3, "fA": 2426, "fB": 2468}).status_code == 200
    assert c.put("/rx/1/pair", json={"pack": 1, "fA": 2414, "fB": 2482}).status_code == 200  # UK plan, ADR-0016
    assert c.post("/rx/1/firmware", content=b"abc").status_code == 502  # fw/PROTOCOL.md: `err dfu not implemented`
    assert c.get("/packs/1").json()["status"]  # the stray payload bytes did not wedge the receiver


def test_scan(c):
    r = c.get("/rf/scan")
    assert r.status_code in (200, 503)  # 503 when the stub receivers all report locked
    if r.status_code == 200:
        assert len(r.json()["rssi_dbm"]) == 42


def test_telemetry_10hz_three_receivers(c):
    with c.websocket_connect("/telemetry") as ws:
        for _ in range(3):
            ws.receive_json()
        t0, msgs = time.monotonic(), []
        while time.monotonic() - t0 < 2.0:
            msgs.append(ws.receive_json()["packs"])
    assert len(msgs) >= 15  # nominal 20 in 2 s
    live = [e for m in msgs for e in m if e["status"] is not None]
    assert {e["id"] for e in live} == set(SLOTS) and len(live) >= 0.8 * 3 * len(msgs)
    assert all(m[1]["status"] is None for m in msgs)


def test_receiver_reboot(bench, c):
    """Kill slot 3's sim mid-telemetry (module reset), start a fresh one on a new pty, service recovers with no restart."""
    path, procs = bench[3]
    with c.websocket_connect("/telemetry") as ws:
        ws.receive_json()
        for p in procs:
            try:
                os.killpg(p.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        t0, m = time.monotonic(), None
        while time.monotonic() - t0 < 3.0:
            m = ws.receive_json()["packs"]
            if m[2]["status"] is None:
                break
        assert m[2]["status"] is None and m[0]["status"] and m[5]["status"]  # only slot 3 blanked
        assert c.put("/packs/3/trim", json={"gain_db": 0}).status_code == 504
        assert c.get("/packs/3").json()["status"] is None
        newpath, newprocs = _boot(EXE)
        bench[3] = (newpath, newprocs)
        app.state.ports[2] = newpath
        t0, back = time.monotonic(), False
        while time.monotonic() - t0 < 5.0 and not back:
            back = ws.receive_json()["packs"][2]["status"] is not None
        assert back
    assert c.put("/packs/3/trim", json={"gain_db": 1}).status_code == 200
