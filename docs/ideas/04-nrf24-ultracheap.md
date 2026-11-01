# 04. Ultra-cheap nRF24L01+ class links with a Pico-driven hub

**One sentence.** Build the whole radio layer out of £1 nRF24L01+ (or Si24R1 / XN297 clone) 2 Mbps GFSK radios driven by sub-£1 microcontrollers, accepting no FEC and no RSSI, and spend the saved money on redundancy.

**How the air works.** 2.4 GHz, 2 Mbps GFSK, 32-byte maximum payload: one millisecond of 8-bit ADPCM at 32 kHz with no room for a header, so either a 31-sample frame with a 1-byte sequence/ID (sample rate 31 kHz) or a full 32-sample frame with the pack identified by its slot timing and the sequence number implied by the superframe. All packs transmit to one address; the hub radio on that carrier receives any pack. TDMA timing comes from the hub's periodic ACK payloads (Enhanced ShockBurst ACK-with-payload is a built-in downlink of 32 bytes per received packet: slot map, trim, mute, ACK). 1 ms superframe, ~160 µs on air + ~130 µs ACK/turnaround ≈ 300 µs per slot → 3 slots per carrier → 11 carriers for 32 mics single copy, always-repeat impossible, so this idea relies on idea 20 (concealment) and 02 (HARQ via the ACK).

**How the receiver works.** 11-12 nRF24 modules on a board, driven by 3 Raspberry Pi Pico (RP2040, £3.50) over SPI, which stream to the host over USB. Host as idea 01. Total radio hardware for 32 channels: ≈ £12 of radios + £11 of Picos.

**Capacity maths.** 3 mics per carrier per ms; 11 carriers × 2 MHz = 22 MHz of spectrum for 32 mics: a lot, and all of it exposed. With T = 2 ms the 32-byte limit forces two packets per frame per pack, so nothing is gained.

**Latency budget.** Codec 300 → frame 1000 → air 160 → ACK 130 → SPI/USB 500 → host 300 → out 250 ≈ 2.6 ms single copy. HARQ repair within the next ms → 3.6 ms. Plenty of margin, the one thing this idea has in abundance.

**Reliability story.** No FEC, 2-byte CRC, no RSSI (only a 1-bit "received power detect"), -82 dBm sensitivity at 2 Mbps (10 dB worse than nRF52840 at 1 Mbps). Range at 1 mW... counterfeit chips often deliver -5 dBm real output. Expect 2-5 % loss at 20 m through an audience; HARQ and concealment must carry it. Clone quality (Si24R1 is a different die with different register quirks) is a supply risk; the real Nordic part is discontinued-ish and £2-3.

**Cost.** Pack: nRF24 £1 + CH32V203/STM32G0 £1 + codec £3 (or MCU ADC, idea 24) + preamp/power/misc £8 + jack £3 + case £2 ≈ £18 ex cell. Hub: £25 radio hardware + host £110 ≈ £135 fixed, ~£1 per channel. 32-channel ≈ £720.

**UK legality.** EN 300 328 non-adaptive at ≤ 10 mW EIRP (any duty cycle), or up to 100 mW with the 10 % medium-utilisation rule; the duty cycle here is ~30 % per pack at 1 ms frames, so 10 mW it is, or a 20 dBm PA module (E01-2G4M27D, £3) at ≤ 10 %.

**What v1 code or analysis it reuses.** Codec, UI, host, concealment. No radio code.

**Riskiest assumption** and the cheapest experiment. That a 10 mW nRF24 reaches 20 m through bodies with ≤ 5 % loss. Experiment (< £30): two nRF24 + two Picos, PRBS at 1 kHz, walk the black box with a phone hotspot in a pocket.

**Why it might be wrong.** 22 MHz of fragile spectrum, no RSSI for channel planning, 10 dB worse sensitivity, and counterfeit silicon as the supply chain. Reliability is P1; this is the idea most likely to trade it for £6 per pack.
