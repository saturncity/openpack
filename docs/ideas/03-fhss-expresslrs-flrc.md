# 03. ExpressLRS-style frequency hopping on SX1280 FLRC radios

**One sentence.** Borrow the open-source drone control link ExpressLRS (2.4 GHz Semtech SX1280/SX1281, FLRC modulation at 1.3 Mbps, 1000 Hz packet rate, FHSS with a sync word and a bidirectional link) and replace its 8-byte control payload with 1 ms of ADPCM audio.

**How the air works.** SX1280 FLRC (Fast Long Range Communication: GMSK-based with built-in convolutional FEC 1/2 or 3/4 and a 32-bit sync word) at 1.3 Mbps, ~1.6 MHz channels, hopping over 40-80 channels across 2400-2480 MHz with a per-system pseudo-random sequence seeded from the hub's ID (ELRS "binding phrase"). Hub radio sends a sync/beacon packet every N hops; packs follow the hop table. Each pack owns one slot per 2 ms frame on one of ~8 hub radios' hop sequences. FHSS satisfies EN 300 328 as frequency-hopping equipment (≥ 15 hop channels), relaxing the duty-cycle rule and letting the pack transmit at 100 mW EIRP. Downlink = the hub's sync packets (ELRS telemetry in reverse).

**How the receiver works.** 8-16 SX1280 modules (Ebyte E28-2G4M12S/20S £4-8, with +12/+20 dBm PA) each driven by an MCU (one RP2040 can run 3-4 radios over SPI with DMA) or one nRF52840 per module; host as idea 01. ELRS receivers themselves (£10 complete, with ESP8285/ESP32) could be the hub radios for the prototype with new firmware.

**Capacity maths.** 46-76 bytes per packet at 1.3 Mbps = 280-470 µs + FLRC preamble/sync ~50 µs + SX1280 TX/RX turnaround ~100 µs ≈ 450-600 µs per slot. 2 ms frame → 3-4 slots per radio; 32 mics single copy = 8-11 radios; with repair 16-22 (too many; use HARQ, idea 02, instead: ~10). 1 ms frame: 2 slots per radio. Spectrum: all of 2.4 GHz, lightly, which is the point.

**Latency budget.** Codec 300 → frame 2000 → air 450 → SPI/USB to host 500 → host 300 → out 250 ≈ 3.8 ms single copy; HARQ repair +1500 → 5.3 ms (fails); 1 ms frame with HARQ ≈ 4 ms (fits, but 2 slots per radio → 16-19 radios).

**Reliability story.** The ELRS argument: hopping at ~1 kHz across the whole band means no single Wi-Fi channel or hotspot can take more than a fraction of the packets, and FLRC's coding gain (ELRS reports -104 dBm sensitivity at the 1.3 Mbps FLRC mode) buys 6-8 dB over plain GFSK. Loss is spread, not bursty, which suits concealment. Re-acquire: ELRS resyncs in well under 0.5 s; the pack listens on the current hop for the sync packet. Hostile test risk: 15 % of hops land on the 22 MHz the hotspot occupies; those are lost or repaired, never concentrated.

**Cost.** Pack: SX1280 module £5 (vs nRF module £4) plus an MCU to drive it (nRF52833/STM32G4 £3) → pack ≈ £27 ex cell. Hub: 10 modules £60 + 3 RP2040s £10 + host £110 ≈ £180 fixed/£2.20 per channel. 32-channel ≈ £1,050.

**UK legality.** EN 300 328 FHSS: ≥ 15 channels, dwell ≤ 400 ms, 100 mW EIRP, adaptive or non-adaptive allowed with hop-based medium utilisation. Must measure hop occupancy and PSD.

**What v1 code or analysis it reuses.** Codec, UI, host; none of the radio code (SX1280 is SPI-driven, not a Zephyr BLE radio).

**Riskiest assumption** and the cheapest experiment. That SX1280 turnaround and SPI load allow ~2000 packets/s per radio with reliable hop timing. Experiment (< £50): two ELRS 2.4 GHz receivers (£10 each) reflashed; measure packets/s and loss with a hotspot at 1 m.

**Why it might be wrong.** FLRC's airtime is 3× BLE 2M, so the hub needs two to three times the radios; FHSS over Wi-Fi gives spread loss, but spread 10 % loss is still 10 % loss, and the concealer has to carry it. ELRS works because 8 bytes at 500 Hz is tiny; audio is 40× that.
