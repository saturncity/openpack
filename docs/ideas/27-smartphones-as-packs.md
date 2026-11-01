# 27. Repurposed hardware: used smartphones (or off-the-shelf dev boards) as the packs

**One sentence.** A £20 second-hand Android phone with a 3.5 mm/USB-C lavalier, a 3,000 mAh battery, Wi-Fi 5/6, a case and a belt clip is a bodypack that nobody has to design; write an app that sends 1 ms audio frames over UDP (ideas 05/06) and fix the receiver side only. The broader form: build the first dozen packs from bought dev boards (XIAO nRF52840 Sense £12, ESP32-C5 DevKit £8) in a printed case rather than designing a PCB.

**How the air works.** Phones: Wi-Fi UDP to a router/host (idea 06's CSMA version, since phones cannot inject raw frames) with the app pinning the radio awake. Dev boards: exactly the chosen TDMA scheme; the "pack" is the dev board plus a preamp hat.

**How the receiver works.** As ideas 05/06/15.

**Capacity maths.** Phones: whatever the Wi-Fi network gives under CSMA; realistically 16-32 at 2 ms frames on a quiet 5 GHz channel. Dev boards: as the scheme.

**Latency budget.** Phones: Android's audio input path (AAudio low-latency mode) is 5-20 ms on its own; iOS ~5-7 ms; plus Wi-Fi. Fails P3 by 2-4×. Dev boards: as the scheme.

**Reliability story.** Phones: OS power management, notifications, OS updates and Wi-Fi roaming are each a dropout waiting to happen; no watchdog control. Dev boards: the module's firmware is ours; the only difference from a custom PCB is the connector hat and the battery wiring.

**Cost.** Phones: £20-30 each including a used battery of unknown health, no 18650 swap, no locking jack. Dev boards: XIAO nRF52840 Sense £12 + preamp hat £4 + charger board £1.50 + jack £3 + printed case £2 ≈ £22.50 ex cell, inside budget, zero PCB NRE, available in a week.

**UK legality.** Pre-certified consumer/dev hardware.

**What v1 code or analysis it reuses.** Host, UI, codec.

**Riskiest assumption** and the cheapest experiment. Phones: audio input latency < 3 ms on any Android device (the answer is known: no). Dev boards: that a hat-and-case assembly is reliable enough for a show and looks like a pack (P9).

**Why it might be wrong.** Phones fail P3 and P1 outright and are here for completeness. The dev-board route is not an architecture but a build strategy: it is how the two-pack prototype should probably be built whatever the architecture, and the evaluator should say so rather than score it.
