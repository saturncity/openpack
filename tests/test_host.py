import os
import sys
import threading
import time

import pytest
import yaml
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from host import channel_plan, modules
from host.app import app


def fake_module(replies):
    """Pty with a fake module on the master end; returns (slave path, received requests, fds)."""
    master, slave = os.openpty()
    seen = []

    def run():
        buf = b""
        while True:
            try:
                buf += os.read(master, 4096)
            except OSError:
                return
            while b"\n" in buf:
                line, buf = buf.split(b"\n", 1)
                seen.append(line.decode())
                cmd = line.decode().split()[0]
                if cmd == "dfu":
                    n = int(line.split()[1])
                    while len(buf) < n:
                        buf += os.read(master, 4096)
                    seen.append(buf[:n])
                    buf = buf[n:]
                r = replies.get(cmd)
                if r:
                    os.write(master, r.encode() + b"\n")

    threading.Thread(target=run, daemon=True).start()
    return os.ttyname(slave), seen, (master, slave)


REPLIES = {"info": "ok fw=0.1", "status": "ok locked=1 rssi=-60 loss=0.0 batt=90 peak=-12 clip=0 temp=0", "trim": "ok", "pair": "ok",
           "scan": "ok 2400:-90 2402:-88", "dfu": "ok"}


@pytest.fixture
def client():
    app.state.scan_cache = None
    mods = [fake_module(REPLIES) for _ in range(8)]
    app.state.ports = [m[0] for m in mods]
    yield TestClient(app), mods  # fds left open: closing a pty with a blocked reader hangs on macOS


def test_plan_file_valid():
    assert len(channel_plan.load()) == 8
    assert channel_plan.region() == "UK"
    assert channel_plan.gap_lost_to_wifi13(channel_plan.load()) == [6, 7, 8]  # ADR-0015: UK Wi-Fi 13 caveat


@pytest.mark.parametrize("edit", [
    lambda p: p.pop(8),                                  # missing pack
    lambda p: p[1].update(fA=2445),                      # fA > 2440
    lambda p: p[1].update(fB=p[1]["fA"] + 20),           # fB too close
    lambda p: p[3].update(fB=p[4]["fB"]),                # duplicate carrier
    lambda p: p[4].update(fB=2460),                      # a second pack without a gap carrier
    lambda p: p[1].update(fB=2448),                      # pack 1 takes pack 4's gap carrier (duplicate)
    lambda p: p[7].update(fA=2437),                      # 2 MHz from pack 8's 2439: collides at 2 Mbit (#76)
    lambda p: p[7].update(fA=2432),                      # pack 6 near: pack 7 loses 2432 and 2476 (near-far)
    lambda p: p[1].update(fB=2459),                      # no-gap pack 1 within 5 MHz of pack 2's 2463
    lambda p: p[3].update(fB=2466),                      # pack 2 near: pack 3 loses 2426 and 2466 (near-far)
    lambda p: [p[i].update(fA=a) for i, a in ((6, 2417), (7, 2420))],   # 5 in-band carriers under Wi-Fi 1
])
def test_bad_plans_rejected(edit):
    plan = yaml.safe_load(channel_plan.PATH.read_text())
    edit(plan["packs"])
    with pytest.raises(ValueError):
        channel_plan.validate(plan)


def test_bad_region_rejected():
    plan = yaml.safe_load(channel_plan.PATH.read_text())
    plan["region"] = "EU"
    with pytest.raises(ValueError):
        channel_plan.validate(plan)


def test_api(client):
    c, mods = client
    assert c.get("/health").json() == {"ok": True}
    p = c.get("/packs").json()
    assert len(p) == 8 and p[0]["fA"] == 2414 and p[0]["status"]["locked"] == "1"
    assert c.get("/packs/3").json()["fB"] == 2468
    assert c.get("/packs/9").status_code == 404
    assert c.put("/packs/2/trim", json={"gain_db": 3.5}).status_code == 200
    assert "trim 3.5" in mods[1][1]
    assert c.put("/packs/2/trim", json={"gain_db": 99}).status_code == 422
    assert c.get("/rx").json()[0] == {"n": 1, "fw": "0.1"}
    assert c.put("/rx/3/pair", json={"pack": 3, "fA": 2426, "fB": 2468}).status_code == 200
    assert "pair 3 2426 2468" in mods[2][1]
    assert c.put("/rx/3/pair", json={"pack": 3, "fA": 2426, "fB": 2463}).status_code == 422
    assert c.post("/rx/4/firmware", content=b"\x00\x01\x02\n\x03").status_code == 200
    assert mods[3][1][-1] == b"\x00\x01\x02\n\x03"
    assert c.get("/openapi.json").json()["openapi"].startswith("3.1")


def test_module_down_and_reset(client):
    c, mods = client
    app.state.ports[0] = "/dev/does-not-exist"
    p = c.get("/packs").json()
    assert p[0]["status"] is None and p[1]["status"]  # other packs unaffected
    assert c.put("/packs/1/trim", json={"gain_db": 0}).status_code == 504
    app.state.ports[0] = mods[0][0]  # module back after reset
    assert c.get("/packs/1").json()["status"]


def test_silent_module():
    master, slave = os.openpty()
    with pytest.raises(modules.ModuleError):
        modules.request(os.ttyname(slave), "info", timeout=0.2)


def test_telemetry_rate_age_and_dead_module(client):
    c, mods = client
    app.state.ports[0] = "/dev/does-not-exist"  # one dead module
    with c.websocket_connect("/telemetry") as ws:
        ws.receive_json()
        t0, msgs = time.monotonic(), []
        while time.monotonic() - t0 < 1.0:
            msgs.append(ws.receive_json())
    assert 7 <= len(msgs) <= 13  # ~10 Hz
    last = msgs[-1]["packs"]
    assert len(last) == 8 and last[0]["status"] is None  # dead one blank...
    assert all(p["status"]["batt"] == "90" and p["age_ms"] <= 200 for p in last[1:])  # ...others live, fresh


def test_scan_cache(client):
    c, mods = client
    assert c.get("/rf/scan").status_code == 503  # all fake receivers report locked=1
    mods2 = fake_module({**REPLIES, "status": "ok locked=0 rssi=0 loss=0 batt=90"})
    app.state.ports[2] = mods2[0]
    first = c.get("/rf/scan").json()
    assert first == {"rssi_dbm": {"2400": -90.0, "2402": -88.0}}
    n = mods2[1].count("scan")
    assert c.get("/rf/scan").json() == first and mods2[1].count("scan") == n  # cached
    app.state.scan_cache = (time.monotonic() - 11, first)
    c.get("/rf/scan")
    assert mods2[1].count("scan") == n + 1  # expired -> rescanned
