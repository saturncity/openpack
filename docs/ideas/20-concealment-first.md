# 20. Concealment first: engineer for 1 % loss and make it inaudible, instead of engineering for 0.001 % loss

**One sentence.** Borrow packet-loss concealment from VoIP and Bluetooth audio (WebRTC's NetEQ, Opus PLC, LC3's built-in PLC, Google's WaveNetEQ) so that the system's reliability target, "≤ 1 audible artefact per 2 hours", is met by making lost 1 ms frames inaudible rather than by making them never happen, which halves the radio hardware and the airtime.

**How the air works.** Any TDMA scheme at single copy, with the repair budget (idea 02) reduced or removed. The codec is shaped for concealment: 1 ms frames, ADPCM state carried in each frame header (a few bytes: predictor and step index) so decoding restarts cleanly after a loss, and a short overlap-add window at frame boundaries.

**How the receiver works.** Host-side DSP per channel: on a lost frame, (1) waveform-substitution PLC: repeat the last pitch period (for voiced speech/singing, pitch 80-1000 Hz means 1-12 ms periods, so a 1 ms gap is less than a period) with a gain ramp; (2) for unvoiced/noise, LPC-based noise extrapolation; (3) crossfade on resumption; (4) if ≥ 3 consecutive frames are lost (3 ms), fade to a comfort level over 10 ms and alarm the booth. Modern codecs do this in ~5 µs per frame on a Cortex-A; 32 channels are trivial. Neural PLC (Microsoft/Google PLC challenge winners) conceals 20-40 ms gaps convincingly but adds latency and is unnecessary at 1 ms.

**Capacity maths.** If single-frame losses up to ~1-2 % are inaudible after PLC, always-repeat (2× airtime) and most of HARQ's repair region become unnecessary: 32 mics on 4-7 carriers instead of 7-13. That is the whole saving: 40-50 % of radios and spectrum.

**Latency budget.** PLC on 1 ms frames adds 0 ms if it conceals forwards (extrapolates) rather than waiting for the next frame; a 100-200 µs overlap-add is already in the host budget. Interpolating PLC (uses the next good frame too) is better-sounding but costs one frame (1-2 ms) and is excluded.

**Reliability story.** The P1 metric is "audible artefact": what is audible is testable with ViSQOL/POLQA and a listening panel on the v1 corpus with synthetic loss patterns (random 1 %, bursty 5-frame runs, periodic Wi-Fi beacon loss). The hypothesis to test: isolated 1 ms losses up to 1-2 % are inaudible on speech and singing with PLC; bursts > 3 ms are audible whatever the PLC. So the radio's job narrows to "never lose 3 consecutive frames", which hopping/HARQ do far more cheaply than "never lose a frame". Watchdog: PLC rate per mic is itself the booth's link-quality meter.

**Cost.** Zero hardware; saves 3-6 hub radios (£15-30) and, more importantly, 10-15 MHz of spectrum per 32 mics.

**UK legality.** None.

**What v1 code or analysis it reuses.** v1's codec and corpus, ViSQOL harness, bsim loss patterns (replayed into the PLC as loss traces).

**Riskiest assumption** and the cheapest experiment. That 1 % isolated 1 ms losses after PLC score ViSQOL ≥ 4.3 and pass a blind listening test on belt singing. Experiment (£0): implement PLC in Python on the v1 corpus, inject loss, run ViSQOL, and have three people listen. This is the cheapest experiment on the board and should be run first because its result sets the radio's loss target for every other idea.

**Why it might be wrong.** Singing with sustained vibrato exposes repeated pitch periods as flutter; percussive consonants lost at onset cannot be extrapolated; and 1 % loss in a theatre is not random: it comes in 2-10 ms Wi-Fi-frame-sized bursts, which is exactly where PLC fails. The experiment answers all three.
