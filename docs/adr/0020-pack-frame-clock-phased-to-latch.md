# ADR-0020: Pack frames are paced by the audio frame clock, phased 100 us before the net core's latch
Status: accepted. Issue #87. Follow-ups #97 (silicon: hold the lead), #98 (latch just before TXEN).
- **Context:** The placeholder frame source was a 1 ms `k_timer` = 33 RTC ticks = 1007 us. Its phase swept past the net core's latch (copy B DISABLED, t0 + 565 us) every 142 frames. Any other timeout due within 3 RTC ticks of a frame (nrf_rtc_timer `MIN_CYCLES_FROM_NOW`) made that frame's callback 2 ticks (61 us) late. bsim logs showed this: 33 -> 35 -> 31 ticks app side; arrivals +68/-54 us net side. Near the latch the late frame missed its slot, and the next frame overwrote it: a repeat, then a seq skip. 50 ms console poll: 1 skip in 10 s. 50 ms / 200 us load: 10. `op_ipc_send` never failed or blocked.
- **Decision:** The app core runs the real pipeline (`fw/src/app/pack.c`): audio frame clock interrupt -> `op_audio_read_frame` -> ADPCM-6 -> `op_ipc_send`. A cooperative thread (prio -2) does the work. The frame clock is TIMER1 until I2S lands; it runs on the same crystal as TIMER0. The net core sends one sync message at start: the time to its next latch. The app places its frame clock `OP_PACK_FRAME_LEAD_US` (100 = SPEC §2 "Encode + IPC") before the latch. The lead is the frame thread's deadline. The net core keeps sending the newest frame; there is no queue, so no added latency.
- **Requirements check:**

| R-id | A: frame-clock ISR, phased to latch (chosen) | B: keep k_timer, net-side 2-frame FIFO | C: keep k_timer, newest-wins (as was) |
|---|---|---|---|
| R1 | ✓ 0 skips, 0 repeats under load within the lead | ✓ skips absorbed | ✗ skips, 0.7 % repeats |
| R3 | ✓ +0 vs SPEC line (100 us) | ✗ up to +1 ms once the FIFO holds a frame | partial: random 0..1 ms wait |
| R13 | ✓ bsim stress in CI, bit-exact payloads | ✓ | ✗ |

- **Consequences:** No skips under any load that leaves the frame thread its 100 us. A higher-priority load of 300 us > lead skips, as it should (negative control). Repeats fall from 0.7 % to 0. On silicon the I2S clock (HFCLKAUDIO, +0.37 ppm) drifts 1.34 ms/h against TIMER0, so the lead must be steered (#97). The wait from latch to TXEN (435 us) is not in SPEC §2 (#98).
- **Update (#98):** the latch moved from the DISABLED interrupt after copy B (t0 + 565 µs) to TIMER0 COMPARE3 at t0 − `OP_PACK_LATCH_LEAD_US` (20 µs), the same for 42 B and 81 B. Audio frame done → TXEN is now 100 + 20 = 120 µs, measured in bsim (a) from the app core's frame clock. SYS-2: 2.67 ms TD off (2.28 with FLT=1), 4.60 ms TD on with FLT=1.
