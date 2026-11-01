# 22. Two radios, two bands in every pack

**One sentence.** Give each pack two cheap radios on bands that do not fail together, such as 2.4 GHz GFSK plus 5 GHz Wi-Fi (ESP32-C5 does both in one £3 module), 2.4 GHz plus UWB, or 2.4 GHz audio plus a sub-GHz control/downlink radio, so the hostile test's 2.4 GHz interferers cannot take the whole link.

**How the air works.** Variant A (two full links): the pack sends the primary copy on 2.4 GHz TDMA (idea 01) and the repair copy on 5 GHz raw 802.11 (idea 05), or alternates frames between bands so each band carries half the airtime. Variant B (robust control plane): audio on 2.4 GHz, beacon/downlink/join on 868 MHz (CC1101/SX1262, 50 kbps, -120 dBm sensitivity, 25 mW), so a pack never loses its slot timing and can be told to move carriers even when 2.4 GHz is being hammered. Variant C: ESP32-C5 alone, whose single radio is dual-band but not simultaneous; it hops bands per frame (TX on 2.4 GHz raw 802.11 this frame, 5 GHz next), which is a one-module version of A.

**How the receiver works.** Two hub radio families (idea 01 modules + idea 05 dongles, or + one sub-GHz module). Host takes the best copy per frame.

**Capacity maths.** Variant A doubles usable spectrum (2.4 GHz 83 MHz + 5 GHz ~400 MHz): capacity is no longer 2.4 GHz-bound; 32 mics with full redundancy on 4 GFSK carriers + 2 Wi-Fi channels. Variant B adds no audio capacity; it removes ~15 % of airtime (beacons and join slots) from 2.4 GHz and the 868 MHz band's duty-cycle limits (1-10 % depending on sub-band) suit a 1 kbps control stream.

**Latency budget.** As the underlying schemes; two paths with different pipelines must be delay-equalised at the host (the slower, Wi-Fi, path sets the delay: ~4 ms).

**Reliability story.** Independent failure: a 2.4 GHz hotspot cannot touch 5 GHz and vice versa; a 5 GHz hotspot cannot touch GFSK on 2.4 GHz. Sub-GHz control is nearly unjammable by consumer devices. The cost is complexity: two stacks, two antennas, two sets of compliance.

**Cost.** Variant A pack +£3-4 (second radio or the ESP32-C5 doing both) ≈ £27; hub + 2 dongles £40. Variant B pack +£2.50 (CC1101) + antenna £0.50 ≈ £27; hub +£5. Variant C pack ≈ £19 (one module). 32-channel ≈ £950-1,000.

**UK legality.** Each radio under its own standard (EN 300 328, EN 301 893, EN 300 220 for 868 MHz with its duty-cycle sub-bands).

**What v1 code or analysis it reuses.** As the components.

**Riskiest assumption** and the cheapest experiment. That the host can equalise two paths with different and varying delays without audible seams when switching copies. Experiment (< £60): ESP32-C5 dev board sending the same frame on both bands alternately; two receivers; log arrival-time difference distribution.

**Why it might be wrong.** Two radios double the firmware, the antennas, the certification surface and the ways the pack can fail; variant C's band-hopping on one Wi-Fi SoC relies on sub-millisecond band switches the vendor never promised. The reliability gain is real only if the hostile test actually kills a well-designed single-band link, which the bench must show first.
