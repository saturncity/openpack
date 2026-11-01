"""Receiver module driver over serial. Wire format: host/PROTOCOL.md, firmware side fw/PROTOCOL.md."""
import re
import threading
import time

import serial

_locks = {}
_locks_guard = threading.Lock()
_REPLY = re.compile(r"(ok|err)(\s.*)?")  # fw/PROTOCOL.md: anything else on the line (boot banner, printk logs) is not a reply
EARLY_ERR_WAIT = 0.25  # s: how long a payload request waits for a refusal before sending the payload
_MAX_BUF = 4096  # an unterminated line longer than any reply (firmware max line is 96 B, scan reply ~400 B)


class ModuleError(Exception):
    """The receiver did not give a usable reply (down, silent, busy, garbage)."""


class ModuleRejected(ModuleError):
    """The receiver answered `err <reason>`."""


def _lock(port):
    with _locks_guard:
        return _locks.setdefault(port, threading.Lock())


def request(port, line, payload=b"", timeout=1.0):
    """Send one request line (+ optional raw payload), return the reply text after 'ok'. Raises ModuleError.

    `timeout` bounds the whole call (waiting for the port, writing, and reading), not each read, so a module that
    trickles log lines or garbage cannot keep a request alive. Lines that are not `ok`/`err` are skipped.
    """
    deadline = time.monotonic() + timeout
    lock = _lock(port)
    if not lock.acquire(timeout=timeout):  # a stuck request (dfu) must not pile up threads behind it
        raise ModuleError("port busy")
    try:
        reply = _exchange(port, line, payload, deadline, timeout)
    except (serial.SerialException, OSError, ValueError) as e:  # ValueError: pyserial on a port closed under it
        raise ModuleError(str(e) or type(e).__name__) from e
    finally:
        lock.release()
    if reply is None:
        raise ModuleError("no reply")
    m = _REPLY.fullmatch(reply)
    if m.group(1) == "err":
        raise ModuleRejected(reply)
    return (m.group(2) or "").strip()


def _read_reply(s, buf, deadline):
    """Read until a complete ok/err line or the deadline. Returns (reply or None, leftover bytes)."""
    while True:
        if time.monotonic() >= deadline:
            return None, buf
        buf += s.read(max(1, s.in_waiting))
        *lines, buf = buf.split(b"\n")
        for raw in lines:
            text = raw.decode(errors="replace").strip()
            if _REPLY.fullmatch(text):
                return text, buf
        if len(buf) > _MAX_BUF:
            buf = b""


def _exchange(port, line, payload, deadline, timeout):
    with serial.Serial(port, 115200, timeout=0.02, write_timeout=max(timeout, 0.1)) as s:  # reopened per call: survives module reset
        s.reset_input_buffer()
        s.write(line.encode() + b"\n")
        buf = b""
        if payload:
            # A receiver that refuses the request line (fw: `err dfu not implemented`) would parse the raw payload as
            # command lines and corrupt its next request, so give an immediate `err` a moment to arrive first.
            early, buf = _read_reply(s, buf, min(deadline, time.monotonic() + EARLY_ERR_WAIT))
            if early and early.startswith("err"):
                return early
            s.write(payload)
        else:
            early = None
        reply, _ = _read_reply(s, buf, deadline)
        return reply or early  # a lone early `ok` (receiver acks the header, not the payload) still counts
