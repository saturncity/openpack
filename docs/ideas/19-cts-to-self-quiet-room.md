# 19. Quiet the room: 802.11 CTS-to-self medium reservation around our slots (the Bluetooth-coexistence trick)

**One sentence.** The hub carries a Wi-Fi chip that, just before each burst of our TDMA slots, sends an 802.11 CTS-to-self frame whose duration field tells every Wi-Fi device in earshot to stay silent for the next ~1.5 ms, which is how every phone's Bluetooth/Wi-Fi combo chip protects its own Bluetooth audio from its own Wi-Fi.

**How the air works.** Idea 01 TDMA on 2.4 GHz carriers that overlap Wi-Fi channels in use. A Wi-Fi NIC at the hub (ESP32 £3 via raw TX, or a Linux adapter with injection) sends, at the lowest rate (1 Mbps, so every device decodes it) and 100 mW, a CTS-to-self with NAV duration = our slot region (max 32.767 ms). Compliant 802.11 stations set their NAV and defer; our GFSK packs then transmit into a channel that Wi-Fi has vacated. Repeat every superframe. Variants: reserve only the repair-copy region; reserve only on the Wi-Fi channel the hotspot/venue AP uses; use the CF-End-less "quiet element" in beacons if we run the venue AP ourselves.

**How the receiver works.** Idea 01 plus one or two Wi-Fi radios (one per overlapped Wi-Fi channel). No change to packs.

**Capacity maths.** Reclaims the 22 MHz under a busy Wi-Fi channel for our carriers; otherwise neutral.

**Latency budget.** Neutral; the CTS costs ~50 µs of airtime per superframe per Wi-Fi channel.

**Reliability story.** Wi-Fi is the dominant hostile-test interferer; CTS-to-self removes the cooperative part of it (phones, laptops, hotspots that hear the hub). It does not silence Bluetooth, DMX, other mic systems, or Wi-Fi devices that cannot hear the hub (behind the audience, far corners), and a device mid-frame finishes its frame regardless. Measured gain unknown; could be large in a small room.

**Cost.** +£3-25 at the hub.

**UK legality and ethics.** CTS-to-self is a standard 802.11 frame and legal to transmit; EN 300 328 adaptivity rules apply to our GFSK packs as before. The ethics are the problem: reserving 75 % of a Wi-Fi channel's airtime for two hours throttles the venue's box office, bar, QLab laptop and the audience's phones on that channel; it is a polite jammer. Reserving only the repair region (~10 % airtime) on only the overlapped channel is defensible; reserving everything is not. A system designed to be shared with other university societies must not need to win by silencing the room.

**What v1 code or analysis it reuses.** v1's coexistence/scenario modelling.

**Riskiest assumption** and the cheapest experiment. That phones honour a CTS-to-self from a non-AP station (most do; some chips ignore NAV from unknown BSSIDs). Experiment (< £30): one ESP32 at the hub, a phone streaming video over a hotspot to a laptop 3 m away, a second ESP32 or dongle counting our test packets' loss with CTS on vs off.

**Why it might be wrong.** It is coexistence by coercion, works only on devices that hear the hub, and would be the first thing an experienced venue technician objected to. Keep it as a measured, documented, opt-in emergency mode, if at all.
