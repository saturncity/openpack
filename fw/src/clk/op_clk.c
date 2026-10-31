/* RX-7 PI loop (see op_clk.h). */
#include "op_clk.h"

static int64_t clamp64(int64_t v, int64_t lim)
{
	return v > lim ? lim : v < -lim ? -lim : v;
}

void op_clk_init(struct op_clk *c, int32_t kp_ppb, int32_t ki_ppb, int32_t lim_ppb)
{
	*c = (struct op_clk){.kp = kp_ppb, .ki = ki_ppb, .lim = lim_ppb};
}

int32_t op_clk_update(struct op_clk *c, int32_t err_q16)
{
	int64_t lim_q16 = (int64_t)c->lim * 65536;
	int64_t out;

	c->integ = clamp64(c->integ + (int64_t)c->ki * err_q16, lim_q16);
	out = ((int64_t)c->kp * err_q16 + c->integ) / 65536;
	c->out = (int32_t)clamp64(out, c->lim);
	return c->out;
}

int32_t op_aclk_quant(int32_t ppb, int32_t *steps)
{
	int32_t n = (ppb >= 0 ? ppb + OP_ACLK_STEP_PPB / 2 : ppb - OP_ACLK_STEP_PPB / 2) /
		    OP_ACLK_STEP_PPB;

	if (steps) {
		*steps = n;
	}
	return n * OP_ACLK_STEP_PPB;
}
