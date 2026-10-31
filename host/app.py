"""OpenPack host API (SPEC API-1). No authentication in v1: LAN only (API-4, see README)."""
import asyncio
import os
import time

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

from . import channel_plan, modules

app = FastAPI(title="OpenPack host", version="0.1.0")
app.state.plan = channel_plan.load()
# Receiver n (1..8) = n-th port; set OPENPACK_RX_PORTS=/dev/ttyUSB0,/dev/ttyUSB1,...
app.state.ports = [p for p in os.environ.get("OPENPACK_RX_PORTS", "").split(",") if p]


class Trim(BaseModel):
    gain_db: float = Field(ge=-12, le=12)


class Pair(BaseModel):
    pack: int
    fA: int
    fB: int


def _ask(request: Request, n: int, line: str, payload=b"", timeout=1.0):
    if n not in request.app.state.plan:
        raise HTTPException(404, "no such receiver")
    ports = request.app.state.ports
    if n > len(ports):
        raise HTTPException(503, f"receiver {n} has no serial port configured")
    try:
        return modules.request(ports[n - 1], line, payload, timeout)
    except modules.ModuleError as e:
        raise HTTPException(504, f"receiver {n}: {e}")


def _kv(s):
    return dict(x.split("=", 1) for x in s.split())


def _pack(request, n):
    a, b = request.app.state.plan[n]
    out = {"id": n, "fA": a, "fB": b}
    try:
        out["status"] = _kv(_ask(request, n, "status"))
    except HTTPException as e:
        out["status"] = None
        out["error"] = e.detail
    return out


@app.get("/health")
def health():
    return {"ok": True}


@app.get("/packs")
def packs(request: Request):
    return [_pack(request, n) for n in sorted(request.app.state.plan)]


@app.get("/packs/{id}")
def pack(id: int, request: Request):
    if id not in request.app.state.plan:
        raise HTTPException(404, "no such pack")
    return _pack(request, id)


@app.put("/packs/{id}/trim")
def trim(id: int, body: Trim, request: Request):
    _ask(request, id, f"trim {body.gain_db}")
    return {"id": id, "gain_db": body.gain_db}


@app.get("/rx")
def rx(request: Request):
    out = []
    for n in sorted(request.app.state.plan):
        try:
            out.append({"n": n, **_kv(_ask(request, n, "info"))})
        except HTTPException as e:
            out.append({"n": n, "error": e.detail})
    return out


@app.put("/rx/{n}/pair")
def pair(n: int, body: Pair, request: Request):
    if request.app.state.plan.get(body.pack) != (body.fA, body.fB):
        raise HTTPException(422, "pair does not match channel_plan.yaml")  # API-3: plan is the source
    _ask(request, n, f"pair {body.pack} {body.fA} {body.fB}")
    return body


SCAN_TTL = 10.0  # API-5
app.state.scan_cache = None  # (monotonic time, result)


@app.get("/rf/scan")
def scan(request: Request):
    """API-5: every receiver that is not locked scans; per-frequency max; cached 10 s."""
    c = app.state.scan_cache
    if c and time.monotonic() - c[0] < SCAN_TTL:
        return c[1]
    rssi = {}
    for n in sorted(request.app.state.plan):
        try:
            if _kv(_ask(request, n, "status")).get("locked") == "1":
                continue
            r = _ask(request, n, "scan", timeout=5.0)
        except HTTPException:
            continue  # dead receiver: others still scan
        for k, v in (x.split(":") for x in r.split()):
            rssi[int(k)] = max(float(v), rssi.get(int(k), -999.0))
    if not rssi:
        raise HTTPException(503, "no unlocked receiver could scan")
    out = {"rssi_dbm": rssi}
    app.state.scan_cache = (time.monotonic(), out)
    return out


PERIOD, MAX_AGE = 0.1, 0.2  # API-2: 10 Hz, <= 200 ms


@app.websocket("/telemetry")
async def telemetry(ws: WebSocket):
    """Each pack has its own poller, so a dead module only blanks its own entry (status null)."""
    await ws.accept()
    ports = app.state.ports
    latest = {}  # pack -> (monotonic time of reply, status dict)

    async def poll(n):
        while True:
            t0 = time.monotonic()
            try:
                if n > len(ports):
                    raise modules.ModuleError("no port")
                st = _kv(await asyncio.to_thread(modules.request, ports[n - 1], "status", b"", 0.15))
                latest[n] = (time.monotonic(), st)
            except modules.ModuleError:
                latest.pop(n, None)
            await asyncio.sleep(max(0, PERIOD - (time.monotonic() - t0)))

    tasks = [asyncio.create_task(poll(n)) for n in app.state.plan]
    gone = asyncio.create_task(ws.receive())  # completes on client disconnect
    tasks.append(gone)
    try:
        while not gone.done():
            await asyncio.sleep(PERIOD)
            now, out = time.monotonic(), []
            for n in sorted(app.state.plan):
                t, st = latest.get(n, (0, None))
                age = now - t
                fresh = st is not None and age <= MAX_AGE
                out.append({"id": n, "age_ms": round(age * 1000) if fresh else None, "status": st if fresh else None})
            await ws.send_json({"packs": out})
    except WebSocketDisconnect:
        pass
    finally:
        for t in tasks:
            t.cancel()


@app.post("/rx/{n}/firmware")
async def firmware(n: int, request: Request):
    data = await request.body()
    if not data:
        raise HTTPException(422, "empty firmware")
    _ask(request, n, f"dfu {len(data)}", data, timeout=30.0)
    return {"n": n, "bytes": len(data)}
