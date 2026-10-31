# ADR-0003: Pass numbers for "survives a packed auditorium"
Status: accepted (default Q3). 2026-10-31.
- **Context:** R1 needs a number to pass or fail, in the twin (G2) and on the bench/stage (G5, G6).
- **Decision:** Over 1 h: residual frame loss ≤ 0.1 %, ≤ 2 consecutive lost frames, ≤ 1 audible dropout event (a run of ≥ 3 lost frames, i.e. one PLC cannot hide). Interference: laptop + 2 phones running iperf on Wi-Fi 1/6/11, 2 m from the receiver antenna; pack at 10 m. In bsim this is `2G4_device_WLAN_actmod` at the Phase 1 busy fraction (#16).
- **Consequences:** SYS-3 and gates G2/G5/G6 use these numbers verbatim; they live in a test, not prose. Changing them needs a new ADR.
- **Requirements check:** R1 ✓ (defines it) · R13 ✓ (testable in sim first).
