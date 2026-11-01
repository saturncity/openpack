# Host <-> receiver module serial protocol

PROVISIONAL until #25 (firmware). Only `host/modules.py: request()` knows this; change it there.

ASCII, 115200 8N1, one line per message, `\n` terminated. Host sends a request, module sends exactly one reply line.
Receiver `n` (1..8) is on its own UART and serves pack `n`.

| Request | Reply |
|---|---|
| `info` | `ok fw=<version>` |
| `status` | `ok locked=<0\|1> rssi=<dBm> loss=<fraction> batt=<percent> peak=<dBFS> clip=<0\|1> temp=<0\|1>` (PK-10 telemetry; polled at 10 Hz by `/telemetry`, so keep it fast, reply < 50 ms) |
| `pair <pack> <fA> <fB>` | `ok` |
| `trim <dB>` | `ok` |
| `scan` | `ok <MHz>:<dBm> <MHz>:<dBm> ...` (2400-2483, 2 MHz steps) |
| `dfu <bytes>` + that many raw bytes | `ok` |

Failure: `err <reason>`. No reply within the timeout means the module is down (HTTP 504).

Host behaviour (`modules.request()`, #30): `timeout` bounds the whole call; lines that are not `ok`/`err` (boot banner, log lines) and unterminated partial lines are not replies; a receiver that answers `err` is HTTP 502 (also an unparseable `ok` reply), a silent, absent or busy one is 504, a slot with no port is 503. For `dfu` the payload is sent only if no immediate `err` arrives after the request line (0.25 s), so a refusing receiver never parses the payload as commands.
