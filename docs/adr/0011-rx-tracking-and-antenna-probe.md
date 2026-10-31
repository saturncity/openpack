# ADR-0011: Receiver tracking reference, antenna probing, pack-reboot test
Status: accepted. 2026-10-31. Issue #23.
- **Context:** SPEC RX-2..RX-5 fix acquisition on channel A, ±50 µs windows, 100-miss re-acquire, first-valid merge and a 6 dB antenna rule, but not: what the timing reference is, how a one-switch receiver ever hears its other antenna, or how bsim emulates a pack reboot (no `-stop_at` on nrf5340bsim).
- **Decision:** (1) Timing reference = RADIO ADDRESS event captured by TIMER0 over DPPI; a copy counts only if its ADDRESS is within ±W of the expected time; every valid copy moves the next frame boundary by its error (1 µs steps). (2) RX-5: one window per channel every `OP_RX_ANT_PROBE_FRAMES` (100) listens on the other antenna, channel B offset half a period, so one frame never has both copies on the probe antenna. A missed window on the current antenna ages its last-valid RSSI by 1 dB, so a dead antenna loses to an equally strong one after 6 misses. Switch GPIO is a weak stub until the hw/rx board. (3) Net → app IPC: one 46 B `op_rx_msg` per frame while locked, lost frames included (flags, lock epoch, RSSI, antennas). (4) bsim (e): `OP_PACK_TEST_RUN_MS` (test-only) silences the pack; reboot = new device with `-start_offset`, phase shifted off the old one.
- **Consequences:** bsim (a)/(e) pass with ±20 ppm crystals. Probing costs at most one copy per probe frame (1 % of windows), covered by the other copy. Antenna logic is unit-tested (`fw/tests/rx_ant`); RX-5 "bsim with two path losses" waits for a second-antenna model.
- **Requirements check:**

| R-id | ADDRESS + probe (chosen) | END-time ref, no probe | Probe both copies |
|---|---|---|---|
| R1 dropouts | ✓ diversity kept | ✗ never leaves a dead antenna | partial: probe frame unprotected |
| R10 two antennas | ✓ | ✗ second antenna unused | ✓ |
| R13 sim first | ✓ same on silicon/bsim | ✓ | ✓ |
