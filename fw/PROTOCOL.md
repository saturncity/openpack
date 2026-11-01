# Firmware serial protocol (#25)

ASCII, 115200 8N1 on the console UART, or USB CDC ACM where the board has one (DK, pack: below), one request line (`\n`, `\r` ignored), exactly one reply line: `ok[ <text>]` or `err <reason>`. Blank lines get no reply. Max 96 B per line, 5 tokens. Source: `fw/src/proto/` (parser and tables are pure C, ztest in `fw/tests/proto`, pty test in `tests/bsim/proto`).

## Receiver role (RX-9)

The wire format is `host/PROTOCOL.md` (the contract; `host/modules.py: request()` is the client). Not repeated here.

| Request | Firmware behaviour |
|---|---|
| `info` | `ok fw=0.1.0` |
| `status` | `ok locked= rssi= loss= batt= peak= clip= temp= td=`. Real values (`op_rx_app_snapshot`, `fw/src/rx_app/rx_app.c`): `locked` 1 if a merged frame arrived in the last 100 ms; `rssi` of the last valid frame (0 before one); `loss` = lost / frames over the last full 1000-frame (1 s) window, the running window until the first completes, 3 decimals; `batt peak clip temp` = the pack's AIR-3 status word from the last valid frame (PK-10; the pack sends 0 until its sensors land); `td` 1 when the merge receives 81 B time-diversity packets (ADR-0017) |
| `stats` | `ok frames= valid= lost= plc= a_ok= b_ok= skips= td_rec= under= over= fill_milli= ppb=`. Not in `host/PROTOCOL.md`; cumulative since boot: merged frames, frames with a valid copy, frames with none, PLC-concealed frames (RX-6), per-copy successes, seq skips, frames recovered by time diversity, jitter-slot underruns / overruns (RX-7), slot fill at the last frame in milli-samples, DAC clock correction in ppb (clock recovery, ADR-0013) |
| `pair <pack> <fA> <fB>` | pack 1..8, fA 2402..2440, fB in [fA+40, 2482], else `err bad pairing`. Any region: receiving is not regulated, `host/channel_plan.py` checks the plan against its region (ADR-0016) |
| `trim <dB>` | decimal, +-24, one decimal kept |
| `td [on\|off]` | what the booth expects this pack to send (host `td: true` in the plan, sent after `pair`). Stored only: the receiver tells time diversity per pack from the payload length (42 B off, 81 B on) and needs no setting. `td` alone reads it back (`ok td=on`) |
| `scan` | 42 entries 2400..2482 step 2, stub `-100` dBm |
| `dfu` | see "dfu" below. `dfu <n>` (host/PROTOCOL.md form) is refused: `err dfu takes no size...` |

## Pack role (PK-9), USB CDC console

A command without arguments reads the value.

| Request | Reply |
|---|---|
| `info` | `ok fw= role=pack id= chan=A,B power= region= td=` |
| `id [0-7]` | `ok` / `ok id=n` |
| `chan [<fA> <fB>]` | fA 2402..2440, fB in [fA+40, 2482] in region uk/eu, [fA+40, 2480] in us/jp (ADR-0016, same as `host/channel_plan.py` `FB_MAX`) |
| `power [dBm]` | -40..3 (nRF5340 radio range) |
| `region [uk\|us\|eu\|jp]` | default `uk` (ADR-0015). Caps `chan` fB (above). Switching to us/jp while fB is 2482 gives `err`: set `chan` first. Power is not yet clamped by region |
| `td [on\|off]` | time diversity (ADR-0017): packet n also carries frame n-2's codec_state + audio (`td_audio`, AIR-3), 81 B payload, +2 ms latency, recovered by the receiver when both copies of frame n fail (RX-4). Default `off`, or `on` in a `SB_CONFIG_OP_TIME_DIVERSITY` build. A configuration-time setting like `chan`: it takes effect on the next frame and the receiver re-locks on the new length (a few frames lost), so do not switch it mid-show. A TD pack sends into the AIR-4 RX slot (idle in v1) |
| `save` | writes the config to flash (NVS, two sectors at the start of `storage_partition`, `src/proto/op_store.c`) and the RAM slot. `err save failed` if the write fails. At boot a saved record that passes the same limits as the commands replaces the Kconfig defaults (id, carriers, power, region, td) |
| `dfu` | see "dfu" below |

Transport. DK and pack board: the protocol is on USB CDC ACM (devicetree chosen `openpack-proto`, `fw/boards/op_usb_cdc.dtsi`; `OP_CONSOLE_USB_CDC`; the DK's "nRF USB" connector, the pack's USB-C) and uart0 keeps boot and log lines. Receiver board: uart0 (the backplane header, ADR-0014), no USB. bsim: uart0 pty (no USB model). The CDC path is build-verified only (Twister `fw.build.dk.*`, `fw.build.board.pack`).

## dfu

`dfu` (either role): reply `ok`, 200 ms later set the retained boot mode and reset into MCUboot serial recovery (`BOOT_SERIAL_BOOT_MODE`, `fw/sysbuild/mcuboot.conf`; `src/proto/op_dfu.c`). MCUboot then speaks mcumgr SMP on its own serial port (UART on the DK and receiver, USB CDC on the pack board) and resets again after 60 s without a command. The image is uploaded with mcumgr/smpmgr; MCUboot checks the ECDSA-P256 signature. The receiver also enters recovery with the BP_BOOT strap low at reset (ADR-0014); the pack board has no strap.

Not the raw-bytes form of `host/PROTOCOL.md` (`dfu <bytes>` then the payload): the app cannot validate a signed image and MCUboot owns the swap. `dfu <bytes>` is answered with an immediate `err`, which is what `host/modules.py` waits 0.25 s for before it would stream a payload. Build-verified only; the unit test uses a fake hook, bsim answers `err dfu not available in this build`.

## Console rules

- Switching `td` re-locks the receiver (a few frames lost), so change it between shows, not during one.
- The console also carries boot and log `printk` lines. The host must ignore any line that does not start with `ok` or `err`.
- Pack numbering: host pack N (1..8) = firmware `OP_PACK_ID` N-1 (0..7).

## AIR-3 status word (PK-10)

`op_status_pack()`: bits 0-6 battery percent (0..100), bits 7-12 peak = 63 + dBFS (63 = full scale, -63..0), bits 13-15 flags clip, lowbat, temp. SPEC gives only the field widths; this order is our choice. The pack's frame pipeline (`src/app/pack.c`) sends status 0 until the battery and peak sensors land; the receiver reply carries the decoded fields.

## Deferred (#25)

- **Bench (#38):** USB CDC enumeration on the DK and pack, a `save` / power cycle on real flash, `dfu` + SMP upload + swap + revert, `status` against a live pack (the pack's status word is 0 until its sensors land, so `batt=0`).
- **Host follow-up:** `host/app.py` sends raw bytes after `dfu <n>`; it must instead send `dfu`, wait for the recovery port and run SMP. Until then the firmware refuses safely.
- **Net core is not updatable over `dfu`:** the radio image is not under MCUboot (upstream Zephyr 4.5 has no net-core update; it is an nRF Connect SDK feature). It is flashed over SWD.
- **Saved radio settings are reported, not applied:** the net core takes id and carriers from its own Kconfig; forwarding the app core's `id`/`chan`/`power` to it is not in #25.
- **USB VID/PID** are the pid.codes test pair 0x1209:0x0001 until a real one is chosen.
- **MCUboot on the pack board** (USB CDC build) is 64.4 kB of 65.5 kB: 1.1 kB headroom.

## Gaps in host/PROTOCOL.md

- RX-9 asks for RSSI per channel A/B and loss counters; `status` has a single `rssi` and `loss`.
- `status` has no `lowbat` field although AIR-3 carries it.
- `dfu <bytes>` has no ready/ack line before the raw bytes, and no `err` framing for a short payload. Superseded in firmware by `dfu` + MCUboot SMP (above); the host contract needs the matching change.
- `stats` is firmware-only; the host does not read it yet.
- `trim` unit/precision unstated (host sends a float `gain_db`).
