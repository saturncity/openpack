# Firmware serial protocol (#25)

ASCII, 115200 8N1, one request line (`\n`, `\r` ignored), exactly one reply line: `ok[ <text>]` or `err <reason>`. Blank lines get no reply. Max 96 B per line, 5 tokens. Source: `fw/src/proto/` (parser and tables are pure C, ztest in `fw/tests/proto`, pty test in `tests/bsim/proto`).

## Receiver role (RX-9)

The wire format is `host/PROTOCOL.md` (the contract; `host/modules.py: request()` is the client). Not repeated here.

| Request | Firmware behaviour |
|---|---|
| `info` | `ok fw=0.1.0` |
| `status` | `ok locked= rssi= loss= batt= peak= clip= temp=`. `loss` is a fraction with 3 decimals. Values from a stub (`op_rx_stub_sample`) until #23/#24 |
| `pair <pack> <fA> <fB>` | pack 1..8, fA 2402..2440, fB in [fA+40, 2480] (same as `host/channel_plan.py`), else `err bad pairing` |
| `trim <dB>` | decimal, +-24, one decimal kept |
| `scan` | 42 entries 2400..2482 step 2, stub `-100` dBm |
| `dfu <n>` | `err dfu not implemented` (the raw payload would then be read as lines; not wired) |

## Pack role (PK-9), USB CDC console

A command without arguments reads the value.

| Request | Reply |
|---|---|
| `info` | `ok fw= role=pack id= chan=A,B power= region=` |
| `id [0-7]` | `ok` / `ok id=n` |
| `chan [<fA> <fB>]` | fA 2402..2440, fB in [fA+40, 2480] |
| `power [dBm]` | -40..3 (nRF5340 radio range) |
| `region [us\|eu\|jp]` | stored only; nothing consumes it yet |
| `save` | copies the config to a RAM slot. NVS/settings persistence is not wired (follow-up) |

On bsim the console is uart0 (pty). On the DK it is also the uart0 VCOM: the CDC ACM instance is not wired (needs the USB device stack and an overlay), so PK-9 over real USB is not covered yet.

## AIR-3 status word (PK-10)

`op_status_pack()`: bits 0-6 battery percent (0..100), bits 7-12 peak = 63 + dBFS (63 = full scale, -63..0), bits 13-15 flags clip, lowbat, temp. SPEC gives only the field widths; this order is our choice. The pack does not yet put it in frames (the frame source is #20/#21); the receiver reply carries the decoded fields.

## Gaps in host/PROTOCOL.md

- RX-9 asks for RSSI per channel A/B and loss counters; `status` has a single `rssi` and `loss`.
- `status` has no `lowbat` field although AIR-3 carries it.
- Pack ids: the host uses 1..8, firmware `OP_PACK_ID` / `id` use 0..7 (AIR-2 access address). The mapping is undefined.
- `dfu <bytes>` has no ready/ack line before the raw bytes, and no `err` framing for a short payload.
- `trim` unit/precision unstated (host sends a float `gain_db`).
