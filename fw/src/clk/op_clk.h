/* RX-7 clock recovery: PI loop from jitter-slot fill to audio-clock correction (ADR-0013).
 * Pure C, integer only, no Zephyr deps (unit tested in fw/tests/rx_clk).
 *
 * Once per received frame the caller measures the slot fill just before writing the frame
 * (samples written - samples played by the DAC, Q16) and passes err = fill - target. The loop
 * returns the correction to apply to the DAC clock in ppb: positive = play faster.
 *   out = kp * err + I,   I += ki * err   (I clamped to +-lim: anti-windup)
 * Plant: the fill integrates 48 * (f_pack - f_dac) / f_nom samples per frame, so with
 * kp = 26000 ppb/sample and ki = 8 ppb/sample/frame the loop crosses over at ~0.2 Hz with
 * ~75 deg phase margin; the integrator removes any constant crystal offset (zero mean error).
 */
#pragma once
#include <stdint.h>

struct op_clk {
	int32_t kp;    /* ppb per sample of fill error */
	int32_t ki;    /* ppb per sample of fill error per frame */
	int32_t lim;   /* |correction| limit, ppb */
	int64_t integ; /* integrator, ppb Q16 */
	int32_t out;   /* last correction, ppb */
};

void op_clk_init(struct op_clk *c, int32_t kp_ppb, int32_t ki_ppb, int32_t lim_ppb);

/* One frame: err_q16 = fill - target in Q16 samples. Returns the correction in ppb. */
int32_t op_clk_update(struct op_clk *c, int32_t err_q16);

/* HAL (op_aclk.c): the receiver's audio clock. DK: HFCLKAUDIO feeds I2S; bsim/native has no
 * HFCLKAUDIO, so a software DAC clock on an app-core TIMER (device crystal drift included)
 * stands in for the I2S sample counter. Both apply the same HFCLKAUDIO step quantisation. */
#define OP_ACLK_STEP_PPB 3311 /* HFCLKAUDIO.FREQUENCY LSB: 32 MHz / 12 / 2^16 at 12.288 MHz */

int op_aclk_start(void);
/* Apply a correction, quantised to whole HFCLKAUDIO steps; returns the applied value (ppb). */
int32_t op_aclk_set_ppb(int32_t ppb);
/* DAC samples played since op_aclk_start, Q16. Call at least once per second. */
uint64_t op_aclk_played_q16(void);
/* Quantise ppb to whole HFCLKAUDIO steps (round to nearest). Pure, shared with the unit test. */
int32_t op_aclk_quant(int32_t ppb, int32_t *steps);
