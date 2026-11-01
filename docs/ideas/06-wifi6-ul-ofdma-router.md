# 06. Thirty-two Wi-Fi 6 stations and a £30 router: uplink OFDMA as the TDMA scheduler

**One sentence.** Use the scheduler that already exists inside every Wi-Fi 6 access point: the AP's trigger frames allocate uplink resource units (UL OFDMA) to associated stations, so 32 ESP32-C6/C5 packs associated to one cheap Wi-Fi 6 router transmit simultaneously in orthogonal sub-channels on a schedule the AP sets.

**How the air works.** Standard 802.11ax in 2.4 or 5 GHz. Packs are ordinary stations (WPA3-less open network or PSK) sending small UDP datagrams every 1-2 ms. The AP uses UL OFDMA: one trigger frame → up to 9 stations (20 MHz) or 18 (40 MHz) transmit at once in 26-tone RUs for ~200-300 µs; two to four triggers cover 32 packs in 1-2 ms. Target Wake Time (TWT) gives each pack a scheduled wake, so the pack's radio sleeps in between. Downlink is the AP's ordinary traffic (multicast control messages from the host). Join = Wi-Fi association + DHCP: automatic by definition.

**How the receiver works.** A Wi-Fi 6 router (£30-60, e.g. an OpenWrt-capable MediaTek MT7981 unit) plus a host on its Ethernet LAN (mini PC or the laptop) receiving UDP. Zero custom radio hardware. Capacity scales by adding routers on other channels.

**Capacity maths.** 32 stations × 68 bytes per 2 ms = 1.1 Mbps of payload; the airtime problem is per-frame overhead, which OFDMA removes by parallelising: one 20 MHz channel carries all 32 mics in 4 trigger rounds of ~300 µs = 1.2 ms per 2 ms frame. 40 MHz halves that. Spectrum: one Wi-Fi channel.

**Latency budget.** Codec 300 → frame 2000 → wait for trigger 0-1500 (depends entirely on the AP's scheduler cadence) → air 300 → AP forwarding + Ethernet 200-500 → host 300 → out 250 ≈ 3.4-5.2 ms if the AP triggers at ≥ 1 kHz; unbounded if it does not.

**Reliability story.** Standard 802.11 retries exist but are counterproductive at this latency (a retry arrives too late); set the retry limit to 0-1. OFDMA tones at low MCS are robust; the AP can be configured for a channel the hotspot is not on; and a second router on a second channel can carry a repair copy if packs dual-associate (they cannot: one station, one BSS; so a second radio per pack would be needed, idea 22). Interference from the venue's own Wi-Fi is the same as idea 05.

**Cost.** Pack: ESP32-C6 module £2.50 + codec £3 + misc £11 + jack £3 + case £2 ≈ £21.50 ex cell. Base: router £45 + host £80 (or £0) = £45-125 fixed, £0 per channel. 32-channel ≈ £800.

**UK legality.** Fully standard, pre-certified Wi-Fi equipment on both ends; nothing to measure beyond confirming the router's region setting.

**What v1 code or analysis it reuses.** Codec, UI, host, concealment.

**Riskiest assumption** and the cheapest experiment. That any affordable AP actually issues UL OFDMA triggers at ≥ 500 Hz to 32 stations and that this can be configured or at least observed. Consumer AP firmware decides when to use OFDMA; OpenWrt's mt76 driver exposes little. Experiment (< £60): one Wi-Fi 6 router, 4-8 ESP32-C6 boards sending 1 kHz UDP, Wireshark on a monitor-mode dongle to see whether trigger frames appear and at what cadence; measure UDP one-way delay.

**Why it might be wrong.** The scheduler is inside closed AP firmware and tuned for throughput and fairness, not for a 1 kHz isochronous deadline. Wi-Fi association, power-save and roaming logic in the pack SoC add state and failure modes (deauth storms, DHCP renewals). If OFDMA triggers do not come when we need them, this collapses to plain CSMA Wi-Fi audio, which is the 20-ms world the project exists to escape.
