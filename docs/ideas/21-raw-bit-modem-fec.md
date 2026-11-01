# 21. Treat the radio as a dumb modem: own FEC, raw-bit soft combining, rate adaptation, half-rate codec

**One sentence.** Turn off the radio chip's CRC rejection and let the host see every received bit (nRF radios deliver payloads with failed CRCs and flag them), then apply our own forward error correction, combine bits from multiple copies or multiple receivers, and adapt bitrate per pack, so a frame that is 95 % correct is recovered instead of discarded.

**How the air works.** Any GFSK TDMA scheme. Each 68-byte frame is encoded with a short block code chosen for 1 ms decode on an MCU/host: Reed-Solomon RS(255,223)-style shortened (16 bytes of parity corrects 8 byte errors), or a rate-¾ convolutional code with Viterbi (3 dB gain), or LDPC from the 5G short-block family if the host decodes. Interleaving stays inside the frame (no latency). Packs whose frames fail repeatedly are told via beacon to switch to a lower-rate codec (4-bit ADPCM at 128 kbps, halving airtime and doubling FEC strength for the same slot) or to the radio's coded PHY (BLE S=2 at 500 kbps, 4× airtime, -4 dB sensitivity gain). Capacity rises in the other direction too: the 4-bit codec for everyone doubles mics per carrier when the show needs 32 and spectrum is scarce.

**How the receiver works.** Hub radios in "CRC off / report" mode passing raw payloads and RSSI to the host; the host runs the FEC decoder and, when two copies (repair, or two pods) are available, bit-wise soft combining (with GFSK hard bits, a simple rule: trust the copy with higher RSSI per byte, or majority with three). Diversity receivers (idea 16) turn into real bit-level diversity.

**Capacity maths.** FEC parity costs 15-25 % of airtime; the 4-bit codec saves 50 %; net per-carrier capacity ranges from 0.8× (strong FEC, 8-bit audio) to 1.6× (4-bit audio, light FEC) of idea 01's. Rate adaptation is per pack, so a 32-mic show can run 24 packs at 8-bit and 8 struggling packs at 4-bit.

**Latency budget.** RS decode of a 68-byte block on a Cortex-A76 ≈ 10-30 µs; Viterbi similar; on the pack, encoding is a few µs. Zero added latency; it uses host CPU that is otherwise idle.

**Reliability story.** GFSK packet loss at the margin is usually a handful of bit errors in a 500-bit frame, not a total wipe; the chip's CRC discards the whole thing. With RS(84,68) correcting 8 bytes, the frame survives up to ~10 % byte errors. Under a Wi-Fi burst that overlaps half the frame, nothing saves it except a copy (idea 02) or concealment (idea 20); under the common case (co-channel Bluetooth hop, DMX burst, fade) FEC converts loss into nothing. Expected effect: 3-10× fewer lost frames for 20 % airtime; the bench measures it.

**Cost.** Zero hardware. Saves radios indirectly (fewer repairs needed).

**UK legality.** None.

**What v1 code or analysis it reuses.** v1's codec (4-bit variant is a parameter change), bsim link model (extend from packet-loss to bit-error), ViSQOL harness.

**Riskiest assumption** and the cheapest experiment. That the nRF radio reliably delivers CRC-failed payloads with their bits mostly intact (rather than losing sync and delivering garbage). Experiment (< £40): two nRF52840 DKs, known PRBS payload, attenuate until 10-50 % frames fail CRC, dump failed payloads, histogram the bit errors; if most failed frames have < 5 % bit errors, this idea is worth 3-6 dB.

**Why it might be wrong.** If failures are mostly sync losses (no bits at all) FEC gains nothing; GFSK gives no soft information, so combining is crude; and every byte of parity is a byte of airtime the slot plan had earmarked for a second mic.
