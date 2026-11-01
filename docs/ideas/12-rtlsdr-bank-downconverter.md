# 12. A bank of £30 RTL-SDR dongles behind one 13 cm amateur-radio downconverter

**One sentence.** Eight RTL-SDR dongles (2.4 MHz of bandwidth each, 8-bit, £25-35) on a USB hub, fed by a single £30-60 2.4 GHz-to-UHF downconverter of the kind amateur satellite users buy for the 13 cm band, give 19 MHz of receive bandwidth for about £250 with zero RF design.

**How the air works.** Any of the 2.4 GHz TDMA or FDMA schemes (ideas 01, 02, 11). Carriers are arranged in a contiguous 19 MHz block (e.g. 2455-2474 MHz) so that each dongle's 2.4 MHz window holds one 2 MHz carrier (TDMA: ~5-7 mics each, 8 dongles = 32-56 mics) or three 700 kHz continuous carriers. Downlink by one nRF52840 module (£4), which also provides TDMA timing.

**How the receiver works.** A 13 cm downconverter (LO ~2000 MHz, IF 400-500 MHz; QO-100-style units from Nolle/BaMaTech/AMSAT-DL kits ~£50, or a mixer + ADF4351 module ~£30) → splitter → 8 RTL-SDR v4 (R828D tuner, tunes to ~1.76 GHz, so the IF at 400-500 MHz is comfortable; even plain RTL-SDRs do) → USB 3 hub → mini PC. Each dongle streams 2.4 MSPS × 2 bytes = 4.8 MB/s; eight = 38 MB/s, fine for USB 3. Host does 8 GFSK demods. The 13 cm LNB/downconverter is the only RF part and it is a bought product.

**Capacity maths.** TDMA at 2 Mbps with 2 ms frames: 5-7 slots per carrier → 8 dongles = 40-56 mics single copy or 20-28 with repair. FDMA: 24 continuous carriers. Add 8 more dongles for 16 more MHz (second downconverter LO or a wider IF). Per channel ≈ £7.50 of dongle (below the £10 budget).

**Latency budget.** The weak point: RTL-SDR USB transfer buffering (librtlsdr defaults to 16 × 256 kB buffers = tens of ms; the minimum workable is one 16 kB transfer ≈ 3.4 ms at 2.4 MSPS; smaller transfers are possible with libusb isochronous tweaks down to ~1 ms [measure]). Codec 300 → frame 2000 → air 300 → RTL buffering 1000-3400 → demod 300 → out 250 ≈ 4.2-6.6 ms. Borderline to failing on P3 unless the transfer size is made small and reliable.

**Reliability story.** Same air-side story as the chosen scheme. Receiver side: eight independent USB devices have eight independent sample clocks (the R820T/R828D crystals drift ±50 ppm and are notoriously thermally sensitive) which the host must track per dongle; dongle disconnects/re-enumerations are a known nuisance. 8-bit ADC limits dynamic range (~45 dB), so a strong Wi-Fi signal within the 2.4 MHz window saturates the tuner's AGC; the downconverter's gain must be set so the nearest phone does not pin it.

**Cost.** Pack unchanged (as idea 01, ~£24). Hub: downconverter £50 + 8 dongles £240 + hub/PSU £30 + mini PC £110 = £430 fixed for 32-56 channels (≈ the £150 + 32 × £10 budget line; £0 marginal to 56). 32-channel ≈ £1,200.

**UK legality.** Receive-only hardware; the pack's legality is the chosen air scheme's.

**What v1 code or analysis it reuses.** Pack firmware and codec if idea 11's air is kept; UI, host.

**Riskiest assumption** and the cheapest experiment. RTL-SDR host latency ≤ 1.5 ms with stable streaming from 8 dongles. Experiment (< £80): two RTL-SDR v4 + a hacked librtlsdr with small transfers + a GPIO-toggled test transmitter (nRF52 DK); measure delay histogram over an hour.

**Why it might be wrong.** The dongles are consumer TV tuners: 8-bit, drifty, latency-happy; this idea exists because they are cheap, not because they are good. If the 1 ms transfer trick does not hold, P3 fails outright. Eight sample clocks plus a shared LO is a timing mess compared with one SDR.
