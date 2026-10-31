# ADR-0013: Receiver jitter slot size, PI clock loop input, bsim audio clock
Status: accepted. 2026-10-31. Issue #24.
- **Context:** RX-7 asks for a PI loop on jitter-buffer fill steering HFCLKAUDIO, ≤ 1 sample/h rate error and no slips over 1 h at ±40 ppm. AUDIT-2 says "jitter buffer of 1 frame", but SPEC §2 gives "decode + jitter slot" only 200 µs (a 1 ms buffer makes SYS-2 3.72 ms, over the 3.0 ms target). bsim has no HFCLKAUDIO and no I2S, so there is no DAC clock to steer.
- **Decision:** (1) The slot holds one frame of headroom, but its *setpoint* is `OP_RX_SLOT_TARGET_SAMPLES` = 6 samples (125 µs) of fill when a frame arrives. That is the only latency it adds. Frames come out of the RX-4 fixed deadline, so arrival jitter is µs, not ms. Overrun = fill > target + 2 frames, underrun = fill < 0. Either one counts as a slip and re-primes the slot. (2) Loop input = fill at frame arrival measured against the DAC *sample position* (written − played, Q16), not the ring count, which only moves in 8-sample DMA blocks. On silicon "played" is the I2S DMA fetch position; the one block it runs ahead is the separate 170 µs `DAC_BLOCK` line in §2. (3) Gains kp 26000 ppb/sample, ki 8 ppb/sample/frame (≈ 0.2 Hz crossover). The output is quantised to the HFCLKAUDIO step (3311 ppb) on every target. The integrator survives re-lock. (4) HAL `op_aclk_*`: on the DK it writes `HFCLKAUDIO.FREQUENCY`. The played count comes from a software DAC clock on app-core TIMER2, which bsim drives from the device's own `-xo_drift` crystal. The I2S sample counter replaces it in Phase 5.
- **Consequences:** ztest `fw/tests/rx_clk` (1 h per case, ±40 ppm, 40 ppm/10 min ramp, ±5 µs jitter): 0 slips, error ≤ 0.28 samples, drift ≤ 0.002 samples/h. bsim (d)/(dn) run the real path for 1 h. A late frame has 125 µs of margin. If Phase 5 measures more arrival jitter, raise the Kconfig; there is ~75 µs left in the §2 line.
- **Requirements check:**

| R-id | 6-sample setpoint, sample-position input (chosen) | 1-frame (48-sample) setpoint | Ring-count input (8-sample steps) |
|---|---|---|---|
| R3 latency ≤ 3 ms | ✓ +125 µs, inside §2 | ✗ +1 ms → 3.72 ms | partial: needs a ≥ 16-sample setpoint to absorb ±4 sample noise |
| R1 no dropouts | ✓ 0 slips/h | ✓ | ✓ |
| R13 sim first | ✓ same code on bsim and DK | ✓ | ✓ |
