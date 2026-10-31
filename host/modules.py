"""Receiver module driver over serial. Wire format: host/PROTOCOL.md (provisional until #25)."""
import threading

import serial

_locks = {}


class ModuleError(Exception):
    pass


def request(port, line, payload=b"", timeout=1.0):
    """Send one request line (+ optional raw payload), return the reply text after 'ok'. Raises ModuleError."""
    lock = _locks.setdefault(port, threading.Lock())
    with lock:
        try:
            with serial.Serial(port, 115200, timeout=timeout) as s:  # reopened per call: survives module reset
                s.reset_input_buffer()
                s.write(line.encode() + b"\n" + payload)
                reply = s.readline().decode(errors="replace").strip()
        except (serial.SerialException, OSError) as e:
            raise ModuleError(str(e)) from e
    if not reply:
        raise ModuleError("no reply")
    if not reply.startswith("ok"):
        raise ModuleError(reply)
    return reply[2:].strip()
