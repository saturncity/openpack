# host

FastAPI service.

Run: `OPENPACK_RX_PORTS=/dev/ttyUSB0,... uvicorn host.app:app`. Receiver n (1..8) is the n-th port and serves pack n.
Wire protocol: `PROTOCOL.md` (provisional until #25). Carriers: `channel_plan.yaml` (validated at startup).

**No authentication (API-4).** v1 is for a trusted LAN only: anyone who can reach the port can retune receivers and
flash firmware. Do not expose it to the internet.

Known risk: the gap carriers 2473-2479 are only 2 MHz apart, so pack-to-pack adjacent-channel interference is for #26/#27 to measure.
