# ADR-0002: 8 packs firm; accept Wi-Fi overlap on ≥ 6 of 16 carriers
Status: accepted (default Q2). 2026-10-31.
- **Context:** 8 packs × 2 copies = 16 carriers of 2 MHz. Only 7–10 fit in the gaps between Wi-Fi 1/6/11 (`audit.py` channel plan), so "never overlap Wi-Fi" is impossible at 8 packs.
- **Decision:** 8 packs per rack is a firm requirement. Gap carriers are assigned first (AIR-5); the remaining ≥ 6 carriers sit under Wi-Fi channels, with fB ≥ 40 MHz from fA so the two copies of one pack never share a Wi-Fi channel.
- **Consequences:** Loss resilience rests on frequency diversity, copy merge (RX-4), PLC and, if needed, time diversity (ADR-0001). bsim scenario (c) must use 8 packs with WLAN on 1/6/11. Adaptive channels stay out of v1 (SPEC §10).
- **Requirements check:** R9 ✓ (8 packs) · R1 partial until scenario (c) passes; if it can't, stop-and-ask reason 5.
