# 08. DECT-2020 NR+ on nRF9151: a licensed-band-grade PHY in a licence-exempt, Wi-Fi-free band

**One sentence.** Use Nordic's nRF9151 (the only cheap chip with a DECT NR+ PHY) in the 1880-1900 MHz DECT band, where there is no Wi-Fi, no Bluetooth and no hotspot, and write the MAC ourselves as a 32-slot TDMA.

**How the air works.** 1880-1900 MHz, ten 1.728 MHz carriers, OFDM with QPSK/16-QAM (MCS 0-4), 0.4167 ms slots and ~104 µs subslots, as defined by ETSI TS 103 636. Nordic exposes the PHY (TX/RX of physical layer packets with timing in sub-µs units) and leaves the MAC to the application. Our MAC: hub radio per carrier sends a beacon every 2 ms (4.8 slots), packs transmit 1 or 2 subslots of audio each; DECT-style channel selection (RSSI scan, "least interfered carrier") is required by the band's rules and gives automatic frequency planning. Downlink is the beacon.

**How the receiver works.** 4-6 nRF9151 modules (£12-18 each) on a board with U.FL antennas, each over USB/UART to the host. The nRF9151 is a complete SiP (radio + Cortex-M33 + PMIC), so the board is traces only. Cheap-ish because the band buys reliability that 2.4 GHz has to buy with repair copies and radios.

**Capacity maths.** NR+ payload per subslot at MCS4 ≈ 1,000 bits [estimate; verify against TS 103 636-3 tables]: a 68-byte frame fits one subslot plus guard; ~18 subslots per 2 ms carrier minus one for the beacon → ~16 packs per carrier single copy, 8 with repair. 32 mics with repair = 4 carriers out of 10. Spectrum 7 MHz of the 20. Beyond 32: ~80 mics with repair in the whole band, more if the venue's cordless phones have gone.

**Latency budget.** Codec 300 → frame 2000 → air ~110 → modem-to-host (UART/USB) 500 [measure] → host 300 → out 250 ≈ 3.5 ms; repair at T/2 → 4.5 ms.

**Reliability story.** The band is shared only with DECT cordless phones (declining) and other NR+ systems; none of the hostile-test interferers can transmit there. OFDM with coding and 16-QAM at short range; the chip has a receive sensitivity near -100 dBm at MCS0. Power: up to 23 dBm (250 mW peak, 10 mW average-rule per DECT regulation [verify]). Re-acquire: beacon every 2 ms. The reliability story is the strongest on the board; the price is a chip that costs three nRF52840s.

**Cost.** Pack: nRF9151 £14 + codec £3 + misc £8 + jack £3 + case £2 ≈ £30 ex cell (at the budget line). Hub: host £110 + 4 modules £60 = £170 fixed (13 % over £150, inside the 25 % tripwire), £1.90 per channel. 32-channel ≈ £1,130.

**UK legality.** EN 301 406-2 (DECT NR+), 1880-1900 MHz licence-exempt in the UK (IR2030 lists DECT). Must implement the channel-selection procedure and the power limits; verify with a spectrum analyser.

**What v1 code or analysis it reuses.** Codec, UI, host, concealment. Zephyr (the nRF9151 SDK is nRF Connect / Zephyr, like v1) so build tooling and some driver patterns carry over.

**Riskiest assumption** and the cheapest experiment. That the nRF9151 DECT NR+ PHY API allows ~1 kHz frame scheduling with sub-100 µs timing on a self-written MAC and that the modem firmware does not impose DECT-frame-level latency (10 ms frames). Experiment (< £200): two nRF9151 DKs (~£90 each; tripwire-adjacent) running Nordic's dect_phy_hello sample modified to 2 ms frames; logic analyser on TX request and RX callback.

**Why it might be wrong.** One supplier, one chip, a closed modem firmware with its own roadmap, and a PHY designed for 10 ms industrial frames that may not love 2 ms ones. The pack sits exactly at £30. If the nRF9151 modem adds even 1 ms of internal latency the whole budget is gone.
