/* Pack frame lead loop (see op_lead.h). */
#include "op_lead.h"

void op_lead_init(struct op_lead *l, int32_t kp_ppb, int32_t ki_ppb, int32_t lim_ppb, bool open)
{
	*l = (struct op_lead){.open = open};
	op_clk_init(&l->pi, kp_ppb, ki_ppb, lim_ppb);
}

int32_t op_lead_report(struct op_lead *l, int32_t margin_us)
{
	l->last = margin_us;
	if (!l->have_ref) {
		l->ref = margin_us;
		l->have_ref = true;
	}
	if (!l->open) {
		l->ppb = op_clk_update(&l->pi, (l->ref - margin_us) * 65536);
	}
	return l->ppb;
}

int32_t op_lead_frame(struct op_lead *l)
{
	return op_aclk_dither(l->ppb, &l->acc);
}
