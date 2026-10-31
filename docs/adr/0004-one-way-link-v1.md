# ADR-0004: One-way link in v1, downlink slot reserved
Status: accepted (default Q4). 2026-10-31.
- **Context:** A rack→pack downlink adds a 9th module, a control antenna, RX windows in the pack and ~30 % more firmware. Gain and mute are not on the pack (R2, R4), so v1 needs no remote control of it.
- **Decision:** v1 is pack→rack only. Each 1 ms frame reserves a 300 µs RX slot at t0+700 µs, left idle (AIR-4, SYS-7). Pack id, channel pair, TX power and region are set over USB-C when docked (PK-9) from `host/channel_plan.yaml` (API-3).
- **Consequences:** No remote mute/gain/channel move mid-show; the pack has no "link" LED (PK-8). Pack telemetry still flows in every frame (PK-10). v1.1 can add a beacon without changing the frame.
- **Requirements check:** R4 ✓ · R11 ✓ (telemetry + trim at the rack) · R3 ✓ (slot fits in the idle part of the frame) · R12 ✓ (no 9th module).
