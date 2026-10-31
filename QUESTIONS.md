# OpenPack — Open questions and their hands-off defaults

Context: `AUDIT-2.md`. The owner has delegated these (`docs/agents/hands-off.md`). Each default below becomes an ADR in `docs/adr/`; change one only with simulation or test evidence, recorded in the ADR. The question text that follows is kept so the reasoning is visible.

## Hands-off defaults (the answer sheet)

| Q | Default | Why |
|---|---|---|
| Q1 latency vs dropouts | Time diversity is a build/runtime option. Phase 2 measures both. Rule: if the R1 dropout gate passes without it at the Phase 1 busy fraction, ship it **off** (~2.6 ms, meets R3 target); otherwise ship it **on** (~4.6 ms, within R3's 5 ms hard limit) and record the R1-over-R3 trade in ADR-0001. | `REQUIREMENTS.md` ranks R1 above R3; R3's hard limit is 5 ms |
| Q2 pack count | 8 packs firm; accept Wi-Fi overlap for ≥6 of 16 carriers | Stated goal |
| Q3 pass numbers | Residual loss ≤ 0.1 %, ≤ 2 consecutive lost frames, ≤ 1 audible dropout event/h, over 1 h, interferers: laptop + 2 phones running iperf on Wi-Fi 1/6/11 at 2 m from the receiver antenna, pack at 10 m | AUDIT-2 suggestion |
| Q4 downlink | One-way in v1; 300 µs RX slot reserved in the frame; channel/ID over USB-C when docked | Gain and mute don't need it |
| Q5 codec | Decided by ViSQOL + PESQ in Phase 1; "good speech" accepted for v1 | No ears needed |
| Q6 chip | nRF5340; nRF54L15 only if Phase 1 picks > 8 bits/sample | SDK maturity, audio clock proven |
| Q7 front end | Schematic carries both gain paths; v1 firmware single path + PCM1840 DRE; switch only if ngspice/bench shows clipping or > 2 dB noise penalty | AUDIT-2 B6 |
| Q8 region | US first, +20 dBm; EU is a +10 dBm build-time setting | Owner's Wi-Fi/18650 context is US |
| Q9 rx antennas | Two directional antennas at the stage wings on coax to the rack | Near-far |
| Q10 host | Raspberry Pi CM4 on a carrier with Ethernet, Python FastAPI, modules on UART | Cheapest known-good |
| Q11 battery | Removable protected 18650, external charger, no in-pack charging | Hot-swap |
| Q12 config port | Recessed USB-C, DFU + config, no charging | Free on nRF5340 |
| Q13 enclosure | PETG, conformal-coated PCB, no gasket in v1 | Proto |
| Q14 budget | $30–35/pack ex. cell at qty 100 accepted | audit.py |
| Q15 staging | Phases 0→6 as in `PLAN.md` | |
| Nice-to-know | First user = one theater, not a product; lav/headset mics only; keep I2S on the backplane, no AES67 | |

## Original questions (kept for context)

## Must answer (no default possible)

**Q1. Latency ceiling vs dropouts.** The two-copy scheme gives ~2.2 ms but no protection against Wi-Fi bursts; ~100 multi-frame dropouts/min even on quiet channels (audit.py). Time diversity fixes that at ~4.2 ms. Pick one:
- (a) ≤3 ms, accept dropout risk, rely on venue measurement + antenna placement + v1.1 adaptive channels.
- (b) ≤5 ms, build time diversity in from day one.
- (c) Both as a runtime mode (costs firmware complexity; the receiver's output delay changes with mode).
Follow-ups: Are in-ear monitors in scope? (IEM users hear 4 ms as comb filtering; stage-monitor and house-only shows don't.) What system does the target theater use today and what delay do they live with?

**Q2. 8 packs in a packed house is the goal, or the ceiling?** 16 carriers don't fit the Wi-Fi gaps. If the real v1 need is 4–6 packs (10 gap carriers = 5 packs), the "never overlap Wi-Fi" claim becomes true and D1 is less scary. If 8+ is firm, say so and accept Wi-Fi overlap as a design assumption.

**Q3. Pass number.** Define "works" for the hostile-RF gate: residual frame loss (suggest ≤0.1%), max consecutive lost frames (suggest ≤2), audible dropout events per hour (suggest ≤1), measured for 1 h with a specific interference setup. Without this, Step 3 can't pass or fail.

**Q4. One-way link in v1?** Recommendation: yes. Consequences: no remote mute/gain/channel-move during a show; channel set over USB-C when docked; telemetry still flows pack→rack. Accept, or require the downlink in v1 (adds a 9th rack module, control antenna, RX windows in the pack schedule, ~30% more firmware)?

## Should answer (defaults given)

**Q5. Codec.** Default: decide by D2 listening test among ADPCM-6, ADPCM-8, block-float 8+3. Does the user have audio quality references (what does "Sennheiser quality" mean to them: EW-D, G4 analog, ULX-D)? Any willingness to accept "good speech, not studio" for v1?

**Q6. Chip: nRF5340 vs nRF54L15.** Default: nRF5340 (mature, dual core, audio clock proven). Switch to nRF54L15 only if D2 wants >8 bits/sample. Does the user care about future-proofing vs SDK maturity?

**Q7. Dual-gain front end.** Default: schematic keeps both paths, v1 firmware uses one path + PCM1840 DRE. Is the user attached to the dual-path idea for a reason not in the audit (e.g. a specific mic or a past clipping incident)?

**Q8. Region.** US only for v1? (Decides TX power: +20 dBm US vs +10 dBm EU; decides whether 902–928 MHz is ever an option; decides which Wi-Fi channels exist, EU has 12/13.)

**Q9. Receiver antennas.** Will the rack live in the booth or at the stage? Default spec: two directional antennas at the stage wings on coax to the rack. If the user expects "two whips on the back of the rack in the booth", say now; that setup is the worst case for near-far Wi-Fi.

**Q10. Host.** Default: Raspberry Pi CM4/Zero 2 W running Python (FastAPI) for REST/WebSocket; nRF modules on UART. Any objection to a Linux SBC in the rack (boot time, SD card reliability)? Alternative: one more nRF or an STM32 with Ethernet, more work, no OS.

**Q11. Battery.** Removable 18650 with external charger (no charging in the pack)? Protected cells only? Who buys the cells (crew will put in unprotected laptop pulls)?

**Q12. Pack config/DFU over USB-C.** Accept a USB-C port on the pack (recessed, no charging)? Alternative: tag-connect pogo pads under the battery door, no port.

**Q13. Enclosure material.** PETG/ASA print for the 4-pack? Who prints? Is a sweat-ingress gasket and conformal coating in scope for v1?

**Q14. Budget honesty.** $30–35 per pack ex. cell at qty 100; roughly $60–80 at qty 4 (dev kits are separate). Receiver ~$150–250 in parts. OK?

**Q15. Prototype staging.** Accept D1 → D2 → D3 (dev-kit bench proto) → D4 (PCB + 4-pack)? Or does the user want to skip to PCBs for a reason (deadline, a show date)? If there's a show date, what is it?

## Nice to know
- Who is the first user: one theater, or a product? (Certification cost ~$10–15k only matters for the second.)
- Any mics beyond Sennheiser-pinout lavs/headsets? (Line input, instrument, DPA MicroDot adapters.)
- Should the receiver keep a digital path (I2S on the backplane) for a future AES67 add-on, or is analog XLR forever?
- Name for the project's frame/copy/carrier terms, for `GLOSSARY.md`.
