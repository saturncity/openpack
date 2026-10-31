/* RX-6 PLC (see op_plc.h). */
#include <string.h>
#include "op_plc.h"

void op_plc_init(struct op_plc *p)
{
	memset(p, 0, sizeof(*p));
}

void op_plc_frame(struct op_plc *p, const int16_t *in, int16_t out[OP_PLC_N])
{
	if (in) {
		memcpy(p->last, in, sizeof(p->last));
		memcpy(out, in, sizeof(p->last));
		p->run = 0;
		return;
	}
	p->run++;
	p->concealed++;
	for (int i = 0; i < OP_PLC_N; i++) {
		if (p->run <= OP_PLC_MUTE_AFTER) {
			out[i] = p->last[i];
		} else if (p->run == OP_PLC_MUTE_AFTER + 1) {
			out[i] = (int16_t)((int32_t)p->last[i] * (OP_PLC_N - i) / OP_PLC_N);
		} else {
			out[i] = 0;
		}
	}
}
