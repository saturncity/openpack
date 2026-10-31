import os
import sys
import threading

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


REPLIES = {"info": "ok fw=0.1", "status": "ok locked=1 rssi=-60 loss=0.0 batt=90", "trim": "ok", "pair": "ok",
           "scan": "ok 2400:-90 2402:-88", "dfu": "ok"}


@pytest.fixture
def client():
    mods = [fake_module(REPLIES) for _ in range(8)]
    app.state.ports = [m[0] for m in mods]
    yield TestClient(app), mods  # fds left open: closing a pty with a blocked reader hangs on macOS


def test_plan_file_valid():
    assert len(channel_plan.load()) == 8


@pytest.mark.parametrize("edit", [
    lambda p: p.pop(8),                                  # missing pack
    lambda p: p[1].update(fA=2445),                      # fA > 2440
    lambda p: p[1].update(fB=p[1]["fA"] + 20),           # fB too close
    lambda p: p[3].update(fB=p[4]["fB"]),                # duplicate carrier
    lambda p: p[3].update(fB=2460),                      # no gap carrier
    lambda p: p[3].update(fA=2423, fB=2448),             # two gap carriers
    lambda p: [p[i].update(fA=a) for i, a in ((5, 2414), (6, 2418), (7, 2402))],                   # 5 in-band carriers under Wi-Fi 1
])
def test_bad_plans_rejected(edit):
    plan = yaml.safe_load(channel_plan.PATH.read_text())
    edit(plan["packs"])
    with pytest.raises(ValueError):
        channel_plan.validate(plan)


def test_api(client):
    c, mods = client
    assert c.get("/health").json() == {"ok": True}
    p = c.get("/packs").json()
    assert len(p) == 8 and p[0]["fA"] == 2423 and p[0]["status"]["locked"] == "1"
    assert c.get("/packs/3").json()["fB"] == 2448
    assert c.get("/packs/9").status_code == 404
    assert c.put("/packs/2/trim", json={"gain_db": 3.5}).status_code == 200
    assert "trim 3.5" in mods[1][1]
    assert c.put("/packs/2/trim", json={"gain_db": 99}).status_code == 422
    assert c.get("/rx").json()[0] == {"n": 1, "fw": "0.1"}
    assert c.put("/rx/3/pair", json={"pack": 3, "fA": 2406, "fB": 2448}).status_code == 200
    assert "pair 3 2406 2448" in mods[2][1]
    assert c.put("/rx/3/pair", json={"pack": 3, "fA": 2406, "fB": 2450}).status_code == 422
    assert c.get("/rf/scan").json() == {"rssi_dbm": {"2400": -90.0, "2402": -88.0}}
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
