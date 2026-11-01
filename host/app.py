"""OpenPack host API (SPEC API-1). No authentication in v1: LAN only (API-4, see README)."""
import asyncio
import math
import os
import time
from concurrent.futures import ThreadPoolExecutor

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

from . import channel_plan, modules

app = FastAPI(title="OpenPack host", version="0.1.0")
app.state.plan = channel_plan.load()
app.state.td = channel_plan.td()  # packs with time diversity on (ADR-0017)
# Receiver n (1..8) = n-th port; set OPENPACK_RX_PORTS=/dev/ttyUSB0,/dev/ttyUSB1,...
app.state.ports = [p.strip() for p in os.environ.get("OPENPACK_RX_PORTS", "").split(",") if p.strip()]
# Degraded-mode answers, declared so the OpenAPI schema (and Schemathesis) knows them: a dead or silent receiver is
# 504, one that answers `err` or garbage is 502, a receiver with no port configured is 503. Others are unaffected.
DEGRADED = {404: {"description": "no such pack or receiver"},
            502: {"description": "receiver answered err or an unparseable reply"},
            503: {"description": "receiver has no serial port configured, or nothing could scan"},
            504: {"description": "receiver down, silent or busy"}}
BODY = {400: {"description": "request body is not valid JSON"}}


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
    except modules.ModuleRejected as e:
        raise HTTPException(502, f"receiver {n}: {e}")
    except modules.ModuleError as e:
        raise HTTPException(504, f"receiver {n}: {e}")


def _kv(s):
    try:
        return dict(x.split("=", 1) for x in s.split())
    except ValueError:
        raise modules.ModuleError(f"unparseable reply {s[:60]!r}") from None


def _ask_kv(request, n, line):
    r = _ask(request, n, line)
    try:
        return _kv(r)
    except modules.ModuleError as e:
        raise HTTPException(502, f"receiver {n}: {e}")


def _each(fn, ns):
    with ThreadPoolExecutor(8) as pool:  # a dead receiver costs one timeout, not eight in a row
        return list(pool.map(fn, ns))


def _pack(request, n):
    a, b = request.app.state.plan[n]
    out = {"id": n, "fA": a, "fB": b, "td": n in request.app.state.td}
    try:
        out["status"] = _ask_kv(request, n, "status")
    except HTTPException as e:
        out["status"] = None
        out["error"] = e.detail
    return out


@app.get("/health")
def health():
    return {"ok": True}


@app.get("/packs")
def packs(request: Request):
    return _each(lambda n: _pack(request, n), sorted(request.app.state.plan))


@app.get("/packs/{id}", responses={404: DEGRADED[404]})
def pack(id: int, request: Request):
    if id not in request.app.state.plan:
        raise HTTPException(404, "no such pack")
    return _pack(request, id)


@app.put("/packs/{id}/trim", responses={**DEGRADED, **BODY})
def trim(id: int, body: Trim, request: Request):
    _ask(request, id, f"trim {body.gain_db:.1f}")  # fw/PROTOCOL.md: decimal, one decimal kept (no 1e-05)
    return {"id": id, "gain_db": body.gain_db}


@app.get("/rx")
def rx(request: Request):
    def one(n):
        try:
            return {**_ask_kv(request, n, "info"), "n": n}
        except HTTPException as e:
            return {"n": n, "error": e.detail}

    return _each(one, sorted(request.app.state.plan))


@app.put("/rx/{n}/pair", responses={**DEGRADED, **BODY})
def pair(n: int, body: Pair, request: Request):
    if request.app.state.plan.get(body.pack) != (body.fA, body.fB):
        raise HTTPException(422, [{"loc": ["body"], "msg": "pair does not match channel_plan.yaml", "type": "value_error"}])  # API-3: plan is the source; FastAPI's own 422 shape
    _ask(request, n, f"pair {body.pack} {body.fA} {body.fB}")
    # ADR-0017: the receiver learns what the plan expects; its status td= says what the pack really sends
    _ask(request, n, f"td {'on' if body.pack in request.app.state.td else 'off'}")
    return body


SCAN_TTL = 10.0  # API-5
app.state.scan_cache = None  # (monotonic time, result)


@app.get("/rf/scan", responses={503: DEGRADED[503]})
def scan(request: Request):
    """API-5: every receiver that is not locked scans; per-frequency max; cached 10 s."""
    c = app.state.scan_cache
    if c and time.monotonic() - c[0] < SCAN_TTL:
        return c[1]

    def one(n):
        try:
            if _ask_kv(request, n, "status").get("locked") == "1":
                return {}
            got = {}
            for x in _ask(request, n, "scan", timeout=5.0).split():
                k, v = x.split(":")
                if not math.isfinite(float(v)):
                    raise ValueError(v)
                got[int(k)] = float(v)
            return got
        except (HTTPException, ValueError):
            return {}  # dead or garbling receiver: others still scan

    rssi = {}
    for got in _each(one, sorted(request.app.state.plan)):
        for k, v in got.items():
            rssi[k] = max(v, rssi.get(k, -999.0))
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
    except (WebSocketDisconnect, RuntimeError):  # client gone (send on a closed socket raises RuntimeError)
        pass
    finally:
        for t in tasks:
            t.cancel()


@app.post("/rx/{n}/firmware", responses={**DEGRADED, 422: {"description": "empty firmware"}},
          openapi_extra={"requestBody": {"required": True, "content": {"application/octet-stream": {
              "schema": {"type": "string", "format": "binary", "minLength": 1}}}}})
async def firmware(n: int, request: Request):
    data = await request.body()
    if not data:
        raise HTTPException(422, "empty firmware")
    _ask(request, n, f"dfu {len(data)}", data, timeout=30.0)
    return {"n": n, "bytes": len(data)}
