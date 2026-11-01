/* Pack cell monitor logic (op_batt.h). */
#include "op_batt.h"

int32_t op_batt_cell_mv(int32_t pin_mv, uint32_t full_ohms, uint32_t out_ohms)
{
	if (pin_mv < 0) {
		pin_mv = 0; /* single-ended SAADC reads a few LSB below 0 at 0 V */
	}
	return (int32_t)(((int64_t)pin_mv * full_ohms + out_ohms / 2) / out_ohms);
}

void op_batt_init(struct op_batt *b, int32_t low_mv, int32_t cut_mv, int32_t hyst_mv, uint8_t cut_n)
{
	*b = (struct op_batt){.low_mv = low_mv, .cut_mv = cut_mv, .hyst_mv = hyst_mv,
			      .cut_n = cut_n ? cut_n : 1, .st = OP_BATT_OK};
}

enum op_batt_state op_batt_update(struct op_batt *b, int32_t cell_mv)
{
	b->last_mv = cell_mv;
	if (b->st == OP_BATT_CUTOFF) {
		return b->st;
	}
	b->below = cell_mv < b->cut_mv ? (uint8_t)(b->below + 1) : 0;
	if (b->below >= b->cut_n) {
		b->st = OP_BATT_CUTOFF;
	} else if (cell_mv < b->low_mv) {
		b->st = OP_BATT_LOW;
	} else if (cell_mv >= b->low_mv + b->hyst_mv) {
		b->st = OP_BATT_OK;
	}
	return b->st;
}
