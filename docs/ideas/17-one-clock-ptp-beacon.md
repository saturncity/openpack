# 17. One clock for the whole system: beacon-disciplined sampling, PTP to the host, no sample-rate conversion anywhere

**One sentence.** Treat the hub's beacon as a time-transfer protocol (the way PTP/IEEE 1588 and 802.1AS do over Ethernet, and the way AES67 locks every device to one grandmaster): every pack's audio sample clock is steered to the beacon so that 32 packs sample the same instant, every frame has a known timestamp, the host never resamples, and the delay is identical for every pack by construction.

**How the air works.** Any TDMA scheme (01-08). The beacon carries the hub's 64-bit time; packs timestamp beacon arrival with the radio's hardware timer (nRF52 has sub-µs capture on radio events), estimate offset and drift, and steer their audio clock. On nRF5340 the audio PLL (HFCLKAUDIO) has fine frequency adjustment, which v1 already used; on nRF52840/54 the codec MCLK can come from a fractional PWM/timer steered in steps of a few ppm, or the codec's own PLL (e.g. TLV320ADC3101) can be nudged. Residual error is absorbed by a one-sample elastic buffer per pack, never an ASRC.

**How the receiver works.** The hub's superframe timer is the grandmaster. Multiple hub radios/pods are disciplined to it over a sync wire or PTP over Ethernet (linuxptp, hardware timestamping on many £10 NICs and on Pi 5's MAC). The host emits audio with the same clock: USB Audio Class 2 asynchronous mode with explicit feedback carries the hub clock to the laptop; AES67 output locks to the same PTP domain, so the A&H Dante card (in AES67 mode) and the packs share one grandmaster: the entire chain from capsule to console has one clock and one deterministic latency.

**Capacity maths.** Not a capacity idea; it removes per-channel ASRC CPU (32 ASRCs is real host load on a Pi) and the inter-pack delay spread that comb-filters duets.

**Latency budget.** Removes the ASRC's ~200-500 µs and the elastic-buffer slack (typically 1 frame) that an unsynchronised design must keep against drift; net saving ~1 ms of a 5 ms budget, and makes "identical delay on every pack" (P3) a property rather than a tuning.

**Reliability story.** A pack that loses the beacon free-wheels on its crystal: ±20 ppm × 2 s = 40 µs drift, inside a 50 µs guard; after 10 s the pack must re-sync (it would anyway have no slot). Beacon-forgery or clock-jump protection: a pack rejects beacon timestamps that imply a jump > 100 µs unless repeated. Nothing here adds a failure mode that TDMA does not already have.

**Cost.** Zero added parts if the codec/MCU already has a steerable clock (most do); otherwise a £1 VCXO. On the host, a PTP-capable NIC/Pi is standard.

**UK legality.** None.

**What v1 code or analysis it reuses.** v1's audio clock work (issues #24, #97: HFCLKAUDIO fine tuning, clock recovery) directly; v1's host ASRC becomes unnecessary.

**Riskiest assumption** and the cheapest experiment. That the beacon-derived clock on a cheap MCU reaches < 1 µs jitter (audio-grade) without a dedicated clock chip. Experiment (< £40): two nRF52840 DKs; one beacons, the other steers a 32 kHz timer output; measure the two clocks' phase on a scope/logic analyser over an hour.

**Why it might be wrong.** It is a design principle rather than a standalone architecture and can be adopted inside any TDMA idea; its only risk is engineering effort. The evaluator should treat it as a modifier that strengthens 01-08 and 15-16.
