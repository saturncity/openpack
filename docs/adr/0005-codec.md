# ADR-0005: Codec — ADPCM-6 (6 bits/sample)
Status: accepted. 2026-10-31. Data: `sim/codec/RESULTS.md` (21 clips: VCTK speech, VocalSet singing incl. belt/forte/pp, whisper-to-scream sweep; 0 dB and -20 dB; ViSQOL v3.3.3 + PESQ-WB vs the unquantised input).
- **Context:** SYS-4 needs ViSQOL ≥ 4.0; AIR-3 caps the payload at 85 B, and ADR-0001 likely ships time diversity ON, which only fits ADPCM-6 (seq 1 + status 2 + 39 B frame + 39 B TD copy = 81 B; ADPCM-8 / block-float 8+3 are 51 B frames, 105 B with the copy, over 85 B).
- **Results:** ViSQOL mean / worst, 0 dB: adpcm6 4.60 / 4.20, adpcm8 4.62 / 4.34, bf8_3 4.62 / 4.27 (16-bit ceiling 4.73). At -20 dB: 4.61 / 4.29, 4.65 / 4.46, 4.65 / 4.50. PESQ-WB agrees (adpcm6 mean 4.56, worst 4.36).
- **Decision:** ADPCM-6. It meets ViSQOL ≥ 4.0 on every clip (worst 4.20). No codec above 8 bits/sample is needed, so no ADR-0008 flip to nRF54L15.
- **Top two within 0.1:** all three means are within 0.05, but the choice is set by R1 (only ADPCM-6 fits the TD copy), not by quality, so no owner listening test is needed. If #26 ships TD **off**, re-open this ADR: then ADPCM-8 vs ADPCM-6 is a quality tie and the A/B clips (`sim/codec/bakeoff.py` writes them) go to the owner.
- **Consequences:** FW-4 targets the `adpcm6` golden vectors. The worst clips are loud sung belt, so keep them in the Phase 2 regression corpus.
- **Requirements check:** R1 ✓ (39 B keeps the TD copy inside 85 B) · R5 ✓ (ViSQOL ≥ 4.0 on all 21 clips, both levels; noise floor part of R5 is separate, #15) · R3 ✓ (no change to ADR-0001 latency) · R12 ✓ (no chip change).
