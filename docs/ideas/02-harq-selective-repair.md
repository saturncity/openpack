# 02. HARQ: resend only what was lost (ACK bitmap in the beacon)

**One sentence.** Instead of always sending a second copy of every frame, the hub's beacon carries a 32-bit bitmap of which packs' last frames arrived, and only the packs whose frame was lost resend it in a shared repair region, exactly as LTE/5G hybrid ARQ does.

**How the air works.** Same TDMA as idea 01, but the superframe is divided into a primary region (32 slots) and a repair region of, say, 6 slots. Beacon at the top of the frame contains ACK bits for the previous frame. A NACKed pack retransmits its previous frame in a repair slot chosen by rank order among the NACKed packs (deterministic, no contention: the bitmap tells every pack who else was lost). If more than 6 packs are lost in one frame the lowest-ranked ones are concealed instead (idea 20). The downlink and the ACKs come for free with the beacon that TDMA needs anyway. Alternatively the acknowledgement can be per packet using the radio's ACK-with-payload feature (nRF ESB, nRF24 Enhanced ShockBurst), which saves the beacon round trip at the cost of one extra turnaround per slot.

**How the receiver works.** Identical hardware to idea 01; the gain is entirely in airtime: 32 primary + 6 repair slots instead of 64, so about 40 % fewer carriers (radios) for the same 32 mics, or the saved airtime buys longer guards and lower-rate robust framing.

**Capacity maths.** At 2 Mbps, 2 ms frame, ~250 µs slots: 7 slots per carrier → 38 slots need 6 carriers (vs 13 for always-repeat). Expected frame loss under hostile conditions ~1 %: 0.3 packs per frame need repair; 6 repair slots handle a 50× burst. Spectrum ~10 MHz.

**Latency budget.** The repair must arrive before the host's playout deadline. Beacon ACK arrives T after the primary; repair slot follows within ~T/2; so worst case latency = codec 300 + frame 2000 + air 300 + wait-for-NACK-and-repair ~1500 + host/USB 800 + out 250 ≈ 5.1 ms with T = 2 ms, 3.6 ms with T = 1 ms. HARQ therefore pushes toward a 1 ms superframe (more slot overhead, fewer slots per carrier: ~3 at 2 Mbps, ~7 at 4 Mbps).

**Reliability story.** Same first-copy loss as idea 01, but repair bandwidth is shared, so a burst that kills everyone's frame at once (a long Wi-Fi frame on the carrier) exceeds the repair pool: mitigate by putting the repair region on a different carrier from the primary. Beacon loss means no ACKs → fall back to always-repeat for that frame (packs that miss the beacon resend unconditionally). This degrades gracefully to idea 01 and never below it.

**Cost.** Pack unchanged (~£24). Hub: 6 modules instead of 13 (saves ~£35) or, more importantly, fewer USB endpoints and a simpler carrier board.

**UK legality.** As idea 01; lower per-pack duty cycle helps the EN 300 328 medium-utilisation limit.

**What v1 code or analysis it reuses.** v1's time-diversity analysis (why always-repeat costs 2×) and the bsim scenario runner, which already models frame loss per slot and can model the bitmap.

**Riskiest assumption** and the cheapest experiment. That the NACK round trip fits in the latency budget on real radios (beacon decode → NACK → TX in ≤ 1.5 ms). Experiment (< £60): two nRF52840 DKs; inject 5 % loss by a deliberately bad channel; measure repair arrival time with a logic analyser.

**Why it might be wrong.** Loss in a theatre is bursty, not random; if 8 packs lose the same frame, 6 repair slots are not enough and the ones concealed are exactly the ones in the worst spot. The 1 ms superframe that HARQ wants costs half the per-carrier capacity, eating much of the saving.
