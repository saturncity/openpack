/* Pack frame lead loop (#97, ADR-0022): hold the audio frame clock's phase against the net core's
 * payload latch. Pure C, integer only, no Zephyr deps (unit tested in fw/tests/pack_lead).
 *
 * Every OP_PACK_LEAD_REPORT_FRAMES frames the net core reports the latch margin (latch - frame
 * arrival, us) of the earliest frame in the window: the least-delayed frame, so encode time and
 * load jitter do not bias it. The first report is the reference (the phase the start-up sync set,
 * ADR-0020); the loop then steers the frame clock rate to keep the margin there:
 *   err = ref - margin (us; positive = frames late = speed the frame clock up)
 *   ppb = kp * err + I,   I += ki * err   (op_clk.c, I clamped to +-lim)
 * Plant: per report the margin moves by (rate offset + correction) * report period, 1e-4 us per ppb
 * at 100 frames. kp 2000 ppb/us, ki 100 ppb/us/report put both closed-loop poles at z = 0.9: a
 * ~1 s time constant; a +-40 ppm step moves the margin ~16 us before the integrator holds it.
 * The rate is HFCLKAUDIO (I2S MCK), whose FREQ register moves in 3311 ppb steps: op_lead_frame
 * dithers the correction between whole steps once per frame (sigma-delta, op_aclk_dither).
 */
#pragma once
#include <stdbool.h>
#include <stdint.h>
#include "op_clk.h"

struct op_lead {
	struct op_clk pi;
	int32_t ref;  /* reference margin, us (first report) */
	bool have_ref;
	bool open;    /* test only: loop open, the correction stays 0 (negative control) */
	int32_t ppb;  /* current correction */
	int32_t acc;  /* dither remainder, ppb */
	int32_t last; /* last reported margin, us */
};

void op_lead_init(struct op_lead *l, int32_t kp_ppb, int32_t ki_ppb, int32_t lim_ppb, bool open);

/* One net-core report: margin_us = the earliest frame's latch margin over the window.
 * Returns the correction in ppb (positive = frame clock faster). */
int32_t op_lead_report(struct op_lead *l, int32_t margin_us);

/* One frame: the whole HFCLKAUDIO steps to apply for this frame (dithered correction). */
int32_t op_lead_frame(struct op_lead *l);
