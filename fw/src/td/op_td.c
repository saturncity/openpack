/* Time diversity pack/unpack and RX-4 recovery (op_td.h). */
#include <string.h>
#include "op_td.h"

void op_td_tx_init(struct op_td_tx *s)
{
	memset(s, 0, sizeof(*s));
}

size_t op_td_tx(struct op_td_tx *s, const uint8_t frame[OP_FRAME_LEN], bool on, uint8_t out[OP_FRAME_TD_LEN])
{
	memcpy(out, frame, OP_FRAME_LEN);
	if (on) {
		memcpy(&out[OP_FRAME_LEN], s->hist[s->i], OP_TD_LEN); /* written OP_TD_D frames ago */
	}
	memcpy(s->hist[s->i], &frame[OP_TD_HDR], OP_TD_LEN);
	s->i = (s->i + 1) % OP_TD_D;
	return on ? OP_FRAME_TD_LEN : OP_FRAME_LEN;
}

void op_td_rx_init(struct op_td_rx *s)
{
	memset(s, 0, sizeof(*s));
}

enum op_td_res op_td_rx(struct op_td_rx *s, const uint8_t *pkt, uint16_t tag, uint8_t out[OP_FRAME_LEN],
			uint16_t *tag_out)
{
	uint8_t i = s->i;
	enum op_td_res r = OP_TD_NONE;

	if (s->n >= OP_TD_D) {
		*tag_out = s->tag[i];
		if (s->ok[i]) {
			memcpy(out, s->pkt[i], OP_FRAME_LEN);
			r = OP_TD_OK;
		} else if (pkt != NULL) {
			out[0] = (uint8_t)(pkt[0] - OP_TD_D);
			memcpy(&out[1], &pkt[1], OP_TD_HDR - 1); /* status: packet k's, 2 ms newer */
			memcpy(&out[OP_TD_HDR], &pkt[OP_FRAME_LEN], OP_TD_LEN);
			r = OP_TD_REC;
		} else {
			memset(out, 0, OP_FRAME_LEN);
			r = OP_TD_LOST;
		}
	} else {
		s->n++;
	}
	s->ok[i] = pkt != NULL;
	s->tag[i] = tag;
	if (pkt != NULL) {
		memcpy(s->pkt[i], pkt, OP_FRAME_TD_LEN);
	}
	s->i = (i + 1) % OP_TD_D;
	return r;
}
