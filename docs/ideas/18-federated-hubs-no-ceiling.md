# 18. No ceiling: federated hubs on one time base, packs roam between them

**One sentence.** Make "32" a hub size, not a system size: hubs (or pods) each own a set of carriers and a slot table, share one superframe clock over Ethernet (idea 17) or by hearing each other's beacons, and a pack joins whichever hub has a free slot and the best signal, so a 100-mic production is three hubs on one switch and one booth page.

**How the air works.** Any TDMA scheme. All hubs beacon at the same instant on different carriers with a common frame number; a pack scanning for beacons hears several, ranks them by RSSI and free-slot count (advertised in the beacon), and joins one. Carrier sets are planned by the booth host from the hubs' spectrum scans so hubs never share a carrier within range. Handover: a pack whose beacon fades requests a slot from a second hub before releasing the first (make-before-break), as cellular does; the host sees one logical mic with two sources during the overlap and takes the better frame.

**How the receiver works.** Each hub is idea 01/15/16 hardware; a booth host aggregates hubs over Ethernet (UDP + PTP), presents one UAC2/AES67 device of N channels and one web UI. Hubs are identical and stateless beyond their slot table; adding one is plugging it in.

**Capacity maths.** 2.4 GHz: ~83 MHz / 2 MHz = 40 carriers; minus Wi-Fi occupancy in the venue (22-44 MHz) leaves 20-30 usable carriers × 5-10 mics = 100-300 mics per venue at the spectrum limit (single copy; half with repair). 1785-1805: 20 MHz / 0.5-2 MHz = 10-40 carriers. DECT: 10 carriers × 16 = 160. The licensing ceiling, as REQUIREMENTS.md expects, is the band's width.

**Latency budget.** Identical to the single-hub scheme as long as all hubs share the superframe: a frame's delay does not depend on which hub heard it. Ethernet aggregation adds 100-200 µs, already counted in idea 16.

**Reliability story.** A hub failing drops its slots; packs re-join other hubs within 0.5 s if those have spare slots (the host keeps 10-20 % spare capacity on purpose). Inter-hub interference is designed out by the carrier plan, and over-the-air beacon reception lets hubs detect a clash and re-plan.

**Cost.** Per hub as the chosen idea (£70-170); the booth host is one mini PC regardless of hub count. Per channel stays flat; 96 channels ≈ 3 × hub + packs.

**UK legality.** As the scheme; more beacons, each low duty cycle.

**What v1 code or analysis it reuses.** Host aggregation and UI concepts from v1.

**Riskiest assumption** and the cheapest experiment. That make-before-break handover between hubs can be done without an audible seam. Experiment (< £80): two hub dongles with separate beacons, one pack walking between them; log frame continuity.

**Why it might be wrong.** Like idea 17 it is a design principle: it must be built into the MAC from day one (frame numbers, hub IDs, slot advertisement) or it will never be added. The real limit it exposes is spectrum, which no architecture fixes.
