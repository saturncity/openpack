# 23. Packs relay for each other: a blocked actor is heard through the actor next to them

**One sentence.** Every pack also listens to its neighbours' slots and, when the hub's beacon flags a pack as lost, the nearest pack that heard that frame re-transmits it in a relay slot: cooperative relaying (3GPP sidelink, 802.11s, Bluetooth Mesh) applied to actors standing two metres apart.

**How the air works.** Idea 01/02 TDMA with ACK bitmap. Packs keep their radios in RX for the slots adjacent to their own (costs ~1 ms RX per 2 ms frame: ~5 mA average, acceptable) and buffer the last frame of 2-4 neighbours. The beacon's NACK bitmap names lost packs; a deterministic rule (the lowest-numbered pack that holds a copy and is not itself NACKed) relays in the repair region. The relayed copy arrives before the NACK-based self-repair would (the original pack is probably still shadowed; the neighbour is not).

**How the receiver works.** Unchanged (idea 01). The hub does not care who sent the repair.

**Capacity maths.** Relay slots share the repair region of idea 02 (6 of 38 slots). Zero added spectrum.

**Latency budget.** As idea 02: repair arrives ~T/2-T after the primary; 4-5 ms total with T = 2 ms, 3.5 ms with T = 1 ms.

**Reliability story.** The failure this addresses is body shadowing and local nulls, where the pack 2 m away has a 20 dB better path to the hub. It does not help against a carrier-wide interferer (both copies die), and pods (idea 16) address the same failure from the other side with no pack cost. Relaying also makes a pack's RX path busy, raising its own vulnerability slightly.

**Cost.** Zero hardware; ~5 mA average battery; firmware complexity on the pack (the one place P1 says to keep simple).

**UK legality.** Relaying raises each pack's duty cycle slightly (EN 300 328 medium utilisation).

**What v1 code or analysis it reuses.** bsim scenarios can model it directly.

**Riskiest assumption** and the cheapest experiment. That body shadowing (not interference) is a dominant loss cause in the black box, so a neighbour's copy is usually good. Experiment (< £60): two packs on two people, one hub; walk and turn; log per-frame CRC at the hub for both and the cross-reception at each pack.

**Why it might be wrong.** Pods solve the same problem with no change to the pack, no battery cost and no pack firmware risk; relaying is elegant and almost certainly dominated by them.
