# ADR-0017: Time diversity off by default; on as a per-pack setting for hostile venues
Status: accepted (owner decision B, 2026-11-01). Issue #26. **Supersedes ADR-0001**. Numbers: `python3 audit.py` (#26 section), `docs/analysis/td-latency.md`, ADR-0016.
- **Context:** ADR-0001 built time diversity (TD: packet n also carries frame n−2) as a Kconfig option. Its rule was to ship TD off only if SYS-3 passes with it off. With ADR-0016 every UK pack has a gap carrier, and the receive antennas plus the install rule hold the gap copies. bsim (c) at 40 % Wi-Fi then shows packs 2–8 at **0.000 % loss with TD off**, the same as with it on, and pack 1 matches by equivalence. TD buys nothing there and costs 2.3 ms. The corrected SYS-2 budget (#88) is 2.65 ms with TD off and 4.96 ms with TD on. With the PCM5102A low-latency filter (FLT=1), TD on is 4.58 ms and TD off 2.27 ms. hw/rx already straps FLT high (`hw/rx/rx.py`, #32). FLT=1 needs a SYS-4 ViSQOL check in Phase 5.
- **Decision:** TD is **off by default**, giving 2.65 ms (2.27 ms with the FLT=1 strap). That meets the R3 3 ms target and keeps the AIR-4 RX slot. TD stays available as a **per-pack setting** for hostile venues: those that cannot keep the ADR-0016 install rule, or where a pack has no gap carrier (Wi-Fi 13, US pack 1). With TD on, latency is **4.58 ms with FLT=1**, under the 5 ms hard limit. The receiver handles both per pack: a TD packet is 81 B, not 42 B, so its length tells the receiver which it is. It is a configuration setting, stored like `chan`; it is not switched mid-show. When `OP_TIME_DIVERSITY` lands, its Kconfig default is n. The setting itself, `td_audio` (AIR-3) and RX-4 recovery are built in the #26 follow-up issue; bsim already measures TD-length packets (`OP_TEST_FRAME_LEN`).
- **Requirements check:**

| R-id | A: TD off default, per-pack TD on (chosen) | B: TD on everywhere (ADR-0001 fallback) | C: TD off, no TD at all |
|---|---|---|---|
| R1 | ✓ 0.000 % TD off for packs 2–8 under ADR-0016; TD on where the rule fails | ✓ same loss, no setting to get wrong | partial: no fallback for a venue that breaks the rule |
| R3 | ✓ 2.65 ms (2.27 with FLT=1) ≤ 3 ms target; 4.58 ms on the TD packs | partial: 4.58 ms, hard limit only | ✓ |
| R5 | ✓ (FLT=1 checked by ViSQOL in Phase 5) | ✓ | ✓ |
| R13 | ✓ decided in the twin (bsim + audit) | ✓ | ✓ |

R1 outranks R3. A keeps R1 wherever B does, because the setting exists, and it meets the R3 target, which B does not.
- **Consequences:** Default SPEC numbers are TD off (SYS-2, AIR-7). The crew sets TD per pack from the booth (R11), and `docs/human/antenna-install.md` says when. Receiver output delay differs per pack (2.3 ms more on TD packs), so monitors mixing a TD pack with a non-TD pack hear a 2.3 ms offset. That is within R3 but is noted for the sound designer. ADR-0001's "no runtime mode switching" becomes "set per pack at configuration time".
