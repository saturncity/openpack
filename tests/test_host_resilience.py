"""#30 / G3: the host degrades per spec and never hangs when receivers misbehave (fake receiver ptys, no firmware)."""
import os
import sys
import threading
import time

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from host import modules
from host.app import app

pytestmark = pytest.mark.timeout(60)

STATUS = "ok locked=1 rssi=-60 loss=0.000 batt=90 peak=-12 clip=0 temp=0"
GOOD = {"info": "ok fw=0.1.0", "status": STATUS, "trim": "ok", "pair": "ok", "scan": "ok 2400:-90 2402:-88", "dfu": "ok"}


class Fake:
    """A pty with a scriptable receiver on the master end. `script(fake, cmd)` replaces the default reply."""

    def __init__(self, script=None, replies=GOOD):
        self.master, self.slave = os.openpty()
        self.path = os.ttyname(self.slave)
        self.replies, self.script, self.seen = replies, script, []
        self.alive = True
        threading.Thread(target=self._run, daemon=True).start()

    def send(self, data):
        try:
            os.write(self.master, data)
        except OSError:
            pass

    def reply(self, cmd):
        r = self.replies.get(cmd)
        if r is not None:
            self.send(r.encode() + b"\n")

    def _run(self):
        buf, skip = b"", 0
        while self.alive:
            try:
                buf += os.read(self.master, 4096)
            except OSError:
                return
            while True:
                if skip:                  # an accepted `dfu N` is followed by N raw bytes: consume them, never parse
                    n = min(skip, len(buf))
                    buf, skip = buf[n:], skip - n
                    if skip:
                        break
                if b"\n" not in buf:
                    break
                line, buf = buf.split(b"\n", 1)
                words = line.decode(errors="replace").split()
                if not words:
                    continue
                self.seen.append(words)
                if self.script:
                    self.script(self, words[0])
                else:
                    self.reply(words[0])
                if (words[0] == "dfu" and len(words) > 1 and words[1].isdigit()
                        and (self.replies.get("dfu") or "").startswith("ok") and not self.script):
                    skip = int(words[1])

    def close(self):
        self.alive = False
        try:
            os.close(self.master)
        except OSError:
            pass


@pytest.fixture
def fakes():
    made = []

    def make(script=None, replies=GOOD):
        f = Fake(script, replies)
        made.append(f)
        return f

    yield make
    for f in made:
        f.script = None
        f.alive = False  # master fds stay open (closing a pty with a blocked reader hangs on macOS)


def timed(fn, *a, **k):
    t0 = time.monotonic()
    try:
        return fn(*a, **k), time.monotonic() - t0
    except Exception as e:
        return e, time.monotonic() - t0


# ---- modules.request(): framing -------------------------------------------------------------------------------

def test_log_lines_before_and_between_replies_are_ignored(fakes):
    def s(f, cmd):
        f.send(b"*** Booting nRF Connect SDK ***\r\n<inf> op_rx: lock lost\r\n")
        f.send(b"okay-not-a-reply\nerror: also a log line\n")
        f.reply(cmd)
        f.send(b"<dbg> after the reply\n")
    f = fakes(s)
    assert modules.request(f.path, "info", timeout=1.0) == "fw=0.1.0"
    assert modules.request(f.path, "info", timeout=1.0) == "fw=0.1.0"  # trailing log line must not leak into the next call


def test_crlf_reply(fakes):
    f = fakes(lambda f, c: f.send(b"ok fw=1\r\n"))
    assert modules.request(f.path, "info") == "fw=1"


def test_partial_line_is_not_a_reply(fakes):
    f = fakes(lambda f, c: f.send(b"ok locked=1 rssi=-6"))  # module died mid-line, no newline
    r, dt = timed(modules.request, f.path, "status", timeout=0.4)
    assert isinstance(r, modules.ModuleError) and "no reply" in str(r) and dt < 1.0


def test_partial_line_completed_later(fakes):
    def s(f, c):
        f.send(b"ok fw=")
        time.sleep(0.1)
        f.send(b"0.1.0\n")
    f = fakes(s)
    assert modules.request(f.path, "info", timeout=1.0) == "fw=0.1.0"


def test_only_garbage_times_out(fakes):
    f = fakes(lambda f, c: f.send(b"\xff\xfe\x00garbage\nmore garbage\n"))
    r, dt = timed(modules.request, f.path, "info", timeout=0.3)
    assert isinstance(r, modules.ModuleError) and dt < 1.0


def test_log_flood_cannot_extend_timeout(fakes):
    stop = []

    def s(f, c):
        def spam():
            while not stop:
                f.send(b"<inf> spam spam spam\n")
                time.sleep(0.005)
        threading.Thread(target=spam, daemon=True).start()
    f = fakes(s)
    r, dt = timed(modules.request, f.path, "info", timeout=0.4)
    stop.append(1)
    assert isinstance(r, modules.ModuleError) and dt < 1.0


def test_unterminated_flood_is_bounded(fakes):
    def s(f, c):
        for _ in range(50):
            f.send(b"x" * 1000)
    f = fakes(s)
    r, dt = timed(modules.request, f.path, "info", timeout=0.4)
    assert isinstance(r, modules.ModuleError) and dt < 1.0


def test_err_reply_is_rejected_not_down(fakes):
    f = fakes(replies={"pair": "err bad pairing"})
    with pytest.raises(modules.ModuleRejected, match="^err bad pairing"):
        modules.request(f.path, "pair 1 2 3")


def test_refused_dfu_does_not_send_payload(fakes):
    """fw answers `err dfu not implemented` at once; the payload would be parsed as commands and corrupt the next request."""
    f = fakes(replies={"dfu": "err dfu not implemented", "info": "ok fw=1"})
    with pytest.raises(modules.ModuleRejected, match="not implemented"):
        modules.request(f.path, "dfu 5", b"abcde")
    assert modules.request(f.path, "info") == "fw=1"
    assert f.seen == [["dfu", "5"], ["info"]]


def test_bare_ok_and_bare_err(fakes):
    f = fakes(replies={"trim": "ok", "pair": "err"})
    assert modules.request(f.path, "trim 1") == ""
    with pytest.raises(modules.ModuleRejected):
        modules.request(f.path, "pair 1 2 3")


def test_slow_reply_within_and_beyond_timeout(fakes):
    def s(f, c):
        time.sleep(0.3)
        f.reply(c)
    f = fakes(s)
    assert modules.request(f.path, "info", timeout=1.0) == "fw=0.1.0"
    r, dt = timed(modules.request, f.path, "info", timeout=0.1)
    assert isinstance(r, modules.ModuleError) and dt < 0.5
    time.sleep(0.5)  # the late reply from the abandoned request must not be taken as the next answer
    assert modules.request(f.path, "info", timeout=1.0) == "fw=0.1.0"


def test_unplugged_and_bad_ports():
    for port in ("/dev/does-not-exist", "/dev/null", "/proc", ""):
        r, dt = timed(modules.request, port, "info", timeout=0.3)
        assert isinstance(r, modules.ModuleError) and dt < 1.0, port


def test_pty_closed_before_and_during_request():
    f = Fake()
    f.close()  # unplugged: master gone
    r, dt = timed(modules.request, f.path, "info", timeout=0.5)
    assert isinstance(r, modules.ModuleError) and dt < 1.5

    g = Fake(lambda fake, c: fake.close())  # dies while the request is in flight
    r, dt = timed(modules.request, g.path, "info", timeout=0.5)
    assert isinstance(r, modules.ModuleError) and dt < 1.5


def test_dfu_into_receiver_that_stopped_reading():
    """The write must not block forever (write_timeout)."""
    f = Fake(lambda fake, c: time.sleep(5))
    r, dt = timed(modules.request, f.path, "dfu 2000000", b"\x55" * 2_000_000, timeout=0.5)
    assert isinstance(r, modules.ModuleError) and dt < 3.0
    f.alive = False


def test_busy_port_does_not_queue_forever(fakes):
    f = fakes(lambda fake, c: time.sleep(1.0))
    t = threading.Thread(target=lambda: timed(modules.request, f.path, "info", timeout=1.2))
    t.start()
    time.sleep(0.1)
    r, dt = timed(modules.request, f.path, "status", timeout=0.2)
    assert isinstance(r, modules.ModuleError) and "busy" in str(r) and dt < 0.6
    t.join()


# ---- the HTTP service ------------------------------------------------------------------------------------------

@pytest.fixture
def svc(fakes):
    app.state.scan_cache = None
    mods = [fakes() for _ in range(8)]
    app.state.ports = [m.path for m in mods]
    return TestClient(app), mods, fakes


@pytest.mark.parametrize("present", [[], [1], [8], [1, 2, 3, 4, 5, 6, 7, 8], [2, 4, 6, 8], [1, 3, 5, 7], [1, 8], list(range(1, 8))])
def test_slots_present_absent(svc, present):
    c, mods, fakes = svc
    app.state.ports = [m.path if i + 1 in present else "/dev/openpack-absent" for i, m in enumerate(mods)]
    t0 = time.monotonic()
    p = c.get("/packs")
    assert p.status_code == 200 and time.monotonic() - t0 < 3.0
    for e in p.json():
        assert (e["status"] is not None) == (e["id"] in present)
        assert ("error" in e) == (e["id"] not in present)
    rx = c.get("/rx").json()
    assert [("fw" in e) for e in rx] == [(n in present) for n in range(1, 9)]
    for n in range(1, 9):
        assert c.get(f"/packs/{n}").status_code == 200
        assert c.put(f"/packs/{n}/trim", json={"gain_db": 1}).status_code == (200 if n in present else 504)
    with c.websocket_connect("/telemetry") as ws:
        time.sleep(0.5)
        msg = ws.receive_json()["packs"]
    assert [(e["status"] is not None) for e in msg] == [(n in present) for n in range(1, 9)]


def test_port_list_shorter_than_plan(svc):
    c, mods, _ = svc
    app.state.ports = app.state.ports[:3]
    p = c.get("/packs").json()
    assert [e["status"] is not None for e in p] == [True] * 3 + [False] * 5
    assert c.put("/packs/5/trim", json={"gain_db": 0}).status_code == 503
    with c.websocket_connect("/telemetry") as ws:
        time.sleep(0.4)
        assert sum(e["status"] is not None for e in ws.receive_json()["packs"]) == 3
    app.state.ports = []
    assert c.get("/health").json() == {"ok": True}
    assert all(e["status"] is None for e in c.get("/packs").json())
    assert c.get("/rf/scan").status_code == 503


@pytest.mark.parametrize("bad", ["ok locked", "ok =1 =", "ok locked=1 junk", "ok \x01\x02", "err busy"])
def test_malformed_status_never_500(svc, bad):
    c, mods, fakes = svc
    mods[0].replies = {**GOOD, "status": bad, "info": bad}
    assert c.get("/packs/1").status_code == 200
    assert c.get("/packs").status_code == 200
    assert c.get("/rx").status_code == 200
    assert c.get("/rf/scan").status_code in (200, 503)
    with c.websocket_connect("/telemetry") as ws:
        assert len(ws.receive_json()["packs"]) == 8


@pytest.mark.parametrize("scan", ["ok 2400", "ok 2400:abc", "ok a:b", "ok 2400:nan", "ok 2400:-90:1", "ok 2400:inf", "ok"])
def test_malformed_scan_never_500(svc, scan):
    c, mods, fakes = svc
    mods[1].replies = {**GOOD, "status": "ok locked=0", "scan": scan}
    assert c.get("/rf/scan").status_code in (200, 503)


def test_err_reply_maps_to_502(svc):
    c, mods, _ = svc
    mods[1].replies = {**GOOD, "trim": "err out of range", "pair": "err bad pairing", "dfu": "err dfu not implemented"}
    assert c.put("/packs/2/trim", json={"gain_db": 1}).status_code == 502
    assert c.put("/rx/2/pair", json={"pack": 2, "fA": 2414, "fB": 2482}).status_code in (422, 502)
    assert c.post("/rx/2/firmware", content=b"abc").status_code == 502


def test_trim_wire_format_is_plain_decimal(svc):
    c, mods, _ = svc
    for v in (0.00001, -0.0, 12, -12, 3.14159):
        assert c.put("/packs/1/trim", json={"gain_db": v}).status_code == 200
    sent = [w[1] for w in mods[0].seen if w[0] == "trim"]
    assert sent == ["0.0", "-0.0", "12.0", "-12.0", "3.1"]


def test_receiver_stalls_then_recovers(svc):
    """A silent receiver costs one timeout for its own pack and nothing for the others; it recovers without restart."""
    c, mods, _ = svc
    mods[3].script = lambda f, cmd: None  # reads, never answers
    t0 = time.monotonic()
    p = c.get("/packs").json()
    assert time.monotonic() - t0 < 2.5
    assert p[3]["status"] is None and all(e["status"] for i, e in enumerate(p) if i != 3)
    mods[3].script = None
    assert c.get("/packs/4").json()["status"]["batt"] == "90"


def test_receiver_reset_mid_stream(svc):
    """API-2 + G3: a receiver resets while /telemetry streams. Its entry blanks, others stay live, then it comes back."""
    c, mods, _ = svc
    with c.websocket_connect("/telemetry") as ws:
        for _ in range(3):
            ws.receive_json()
        mods[2].script = lambda f, cmd: f.send(b"*** Booting ***\n")  # rebooting: banner only
        t0, blank, m = time.monotonic(), None, None
        while time.monotonic() - t0 < 2.0 and blank is None:
            m = ws.receive_json()["packs"]
            if m[2]["status"] is None:
                blank = time.monotonic() - t0
        assert blank is not None and blank < 1.0
        assert all(e["status"] for i, e in enumerate(m) if i != 2)
        mods[2].script = None  # back up
        t0, back = time.monotonic(), False
        while time.monotonic() - t0 < 2.0 and not back:
            back = ws.receive_json()["packs"][2]["status"] is not None
        assert back


def test_module_removed_and_replugged_on_new_path(svc):
    """A rebooted receiver can re-enumerate under a new device path; the service follows app.state.ports."""
    c, mods, fakes = svc
    mods[0].close()
    assert c.put("/packs/1/trim", json={"gain_db": 0}).status_code == 504
    new = fakes()
    app.state.ports[0] = new.path
    assert c.put("/packs/1/trim", json={"gain_db": 0}).status_code == 200


def test_eight_concurrent_modules_and_clients(svc):
    c, mods, _ = svc
    for m in mods:
        m.script = lambda f, cmd: (time.sleep(0.02), f.reply(cmd))
    results, errs = [], []

    def hit(i):
        try:
            for _ in range(5):
                results.append(c.get("/packs").status_code)
                results.append(c.put(f"/packs/{i % 8 + 1}/trim", json={"gain_db": i % 5}).status_code)
        except Exception as e:  # pragma: no cover
            errs.append(e)

    ts = [threading.Thread(target=hit, args=(i,)) for i in range(12)]
    [t.start() for t in ts]
    [t.join(30) for t in ts]
    assert not errs and not any(t.is_alive() for t in ts)
    assert results and set(results) <= {200, 504}  # contention may time a request out (504), nothing else


def test_health_responds_while_receivers_are_stuck(svc):
    c, mods, _ = svc
    for m in mods:
        m.script = lambda f, cmd: None
    ts = [threading.Thread(target=lambda: c.get("/packs")) for _ in range(3)]
    [t.start() for t in ts]
    time.sleep(0.2)
    t0 = time.monotonic()
    assert c.get("/health").status_code == 200 and time.monotonic() - t0 < 1.0
    [t.join(30) for t in ts]


def test_firmware_upload_errors(svc):
    c, mods, _ = svc
    app.state.ports[0] = "/dev/openpack-absent"
    assert c.post("/rx/1/firmware", content=b"x" * 1000).status_code == 504
    assert c.post("/rx/1/firmware", content=b"").status_code == 422
    assert c.post("/rx/9/firmware", content=b"x").status_code == 404


def test_telemetry_client_disconnect_leaves_service_healthy(svc):
    c, mods, _ = svc
    for _ in range(3):
        with c.websocket_connect("/telemetry") as ws:
            ws.receive_json()
    assert c.get("/packs/1").json()["status"]
