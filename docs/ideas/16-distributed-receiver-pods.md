# 16. Distributed receiver pods: many cheap radios in many places, the host keeps the best copy

**One sentence.** Instead of two antennas on one rack, put small receiver pods (a £15 Pi Zero 2 W or an Ethernet MCU board with 2-4 radio modules) at several points around the stage, all listening to the same carriers, backhauled by Ethernet/PoE or long USB, and let the host take, per frame per mic, whichever pod heard it correctly: spatial diversity at £25 per point instead of £140 per antenna stand.

**How the air works.** Idea 01/02 TDMA unchanged. Every pod radio on carrier k receives every slot on carrier k; pods are passive except one, which transmits the beacon (or beacons come from each pod on a schedule so that a pack anywhere hears one). Packs do not know pods exist. Multiple pods receiving the same frame give selection combining; with raw-bit reception (idea 21) they give bit-level majority combining.

**How the receiver works.** Pod = Raspberry Pi Zero 2 W (£15) + USB Ethernet (£8) + 3-4 nRF52840 dongles (£15), or a WT32-ETH01/W5500 board + nRF modules, in a printed box with a PoE splitter (£8); a 5-port PoE switch (£35) powers four pods over Cat5 run along the stage edge and fly floor. Pods timestamp frames against a PTP-style clock from the host (Linux PTP over Ethernet gets < 10 µs; even NTP-grade 1 ms is enough to align frames by sequence number) and forward them as UDP. Host as idea 01.

**Capacity maths.** Capacity is set by carriers (idea 01); pods add reliability, not slots. Four pods × 4 radios = 16 radios covering 4 carriers 4-fold, or 8 carriers 2-fold. Beyond 32 mics: pods on different carrier sets in different zones (idea 18).

**Latency budget.** As idea 01 plus Ethernet: air 300 → pod USB/driver 500 → UDP over a switch 100-200 → host waits for the slowest pod (bounded by a 300 µs window) → host 300 → out 250. ≈ 3.9 ms single copy, 4.9 ms with repair at T/2. The pod-wait window is a tunable trade between diversity and latency.

**Reliability story.** The hostile test's worst case is an interferer near one receiver; with four pods the frame is lost only if all four miss it. Body shadowing (an actor turned away from the antenna) is the main real-world loss mechanism for body packs and is exactly what spatial diversity defeats, which is why professional systems sell "antenna distribution" at four figures. Pod failure: the host detects silence from a pod and alarms; mics are unaffected while another pod hears them. Ethernet cables along a stage are standard theatre practice (DMX, Dante run that way).

**Cost.** Pack unchanged (~£24). Hub: host £110 + PoE switch £35 + 4 pods × (£15 + £8 + 4 × £5 + £8 box/PoE) = £204 → £350 fixed (tripwire assessment: 2.3× the £150 budget; the per-channel figure is £0 and the whole 32-channel system remains ≈ £1,120, under £1,500). A two-pod variant is £240 fixed.

**UK legality.** As the air scheme; the beacon transmitter count rises (one per pod) but each is ≤ 10 dBm at low duty cycle.

**What v1 code or analysis it reuses.** v1's antenna placement analysis (wings, stands) is replaced; v1's receiver firmware and host code reusable.

**Riskiest assumption** and the cheapest experiment. That pods can be aligned to < 300 µs over Ethernet with cheap switches, and that frame-level selection across 4 pods measurably beats 2 antennas in the black box. Experiment (< £100): two Pi Zero 2 W + 2 dongles each + a used PoE switch; log per-frame CRC results from both pods while a person walks the room with a pack; count frames only one pod got.

**Why it might be wrong.** Cables along the stage are a show-night tripping and setup cost that the old two-antenna rack did not have; four Linux boards are four more things to boot, update and watchdog; and the gain over a two-antenna hub depends on how bad body shadowing really is in a 10 m room (possibly not very).
