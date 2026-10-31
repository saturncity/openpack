# ADR-0001: Latency vs time diversity — build both, measure, then pick
Status: accepted (default Q1); final on/off decided by Phase 2 data (#26). 2026-10-31.
- **Context:** Two copies on two carriers give ~2.6 ms (SYS-2) but no protection against Wi-Fi bursts longer than a frame; `audit.py` Gilbert-Elliott shows ~105 audible events/min even at 10 % busy. Re-sending frame n−2 in packet n (time diversity) costs +2 ms (~4.6 ms).
- **Decision:** Time diversity is Kconfig `OP_TIME_DIVERSITY` (AIR-3, RX-4). Phase 2 bsim (b)/(c) runs both. If SYS-3 passes **off** at the Phase 1 busy fraction, ship off; otherwise ship **on** and amend this ADR with the numbers.
- **Consequences:** Receiver output delay depends on the build; jitter buffer and deadline are Kconfig, not constants. Payload max 85 B (AIR-3). No runtime mode switching in v1.
- **Requirements check:** R1 ✓ (on fallback guarantees the best loss result we have) · R3 ✓ target if off / ✓ hard limit if on · R5 ✓ · R13 ✓ (decided in the twin). R1 outranks R3, so a failing "off" result means "on".
