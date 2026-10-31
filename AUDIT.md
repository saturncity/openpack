# OpenPack — Step 1 Audit

Numbers come from `python3 audit.py`. Assumptions are written in the script; change them there.

## Blockers (Step 2 can't start until these are decided)

1. **The nRF5340 has no 5 GHz radio.** It is 2.4 GHz only, with a 2 Mbps maximum PHY. The ESP32-C5 does have 5 GHz, but only through its Wi-Fi MAC (CSMA/backoff), so a deterministic 1 ms TDMA can't run on it. Its Wi-Fi TX also roughly doubles pack power (0.24 W → 0.59 W). Also, it's a single high-performance core, not dual-core.
2. **The TDMA doesn't fit.** 8 packs × LC3plus 160 kbps on one 2 Mbps channel needs 155% of a 1 ms frame, and 100% of a 2.5 ms frame. That's before any beacon slot or redundancy.
3. **LC3plus misses the latency target.** Its lowest-delay mode (2.5 ms frames) comes out to about 6 ms end-to-end, against a 1.9–3.0 ms target. (Check the look-ahead figure against the LC3plus spec.)

## What does fit (recommended)

**One RF channel per pack (FDMA), not a shared TDMA.** Commercial digital systems do the same thing: one carrier per pack.
- **Codec:** ADPCM at 6 bits/sample (288 kbps). It adds essentially no codec delay, and each 1 ms frame is about 36 B.
- **Redundancy:** each frame is sent twice, on two widely spaced 2.4 GHz channels, from the same nRF5340. That uses 52% of the airtime.
- **Receiver:** one nRF52/53 per pack. It hops between the two copies in step with the pack and switches antennas between them, so you get frequency and spatial diversity from one radio. 8 packs = 8 chips, about $40.
- **Latency:** about 2.2 ms. That meets the target.
- **Risk:** if the two copies both land on Wi-Fi-heavy channels, losses are correlated. Worst case is 16% residual loss, which is unusable. Mitigations are adaptive channel selection and choosing channels in the gaps between Wi-Fi channels 1, 6 and 11. Stage-wing directional antennas still help.
- **Alternative second band:** 902–928 MHz ISM (US only) on a TI CC1352P (2.4 GHz and sub-GHz on one chip). It needs a check that its sub-GHz data rate can carry about 288 kbps.

## Passes

- **Battery:** the nRF-only pack draws about 0.24 W, which gives about 47 h. The plan's 0.55 W gives 20.6 h. Either meets the 16–20 h target.
- **Thermal:** about 3 K rise at 0.24 W and about 8 K rise at 0.55 W inside a costume pouch. That's fine for a Li-ion cell.
- **Dual-gain "never clip":** use one 4-channel PCM1840, with two of its channels fed from the two OPA1612 gain paths. Both channels share one clock and one decimation filter, so there's no phase skew between them. Two crossfade over about 1 ms at the switch point, with gain matched by calibration, so there are no pops. Keep the analog bandwidth of the two paths matched (same RC values). **Drop the CS5361:** it adds a second chip with its own skew.

## Minor

- Many lavs (for example DPA) are specified for about 5 V bias. Add a 3.3 V / 5 V jumper.
- BOM: an nRF5340 module costs $8–10 in small quantities, so the $28.80 target is tight but possible with a bare chip at volume. Use a pre-certified module for the 4-pack prototype, because FCC Part 15 applies once you sell it.
- Step 3 pass criteria need a number. Suggestion: at most 1% residual frame loss, with packet-loss concealment (PLC) hiding isolated single-frame drops.
