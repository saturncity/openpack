/* Receiver jitter slot (see op_jslot.h). */
#include <string.h>
#include "op_jslot.h"

#define MASK (OP_JSLOT_RING - 1)

void op_jslot_init(struct op_jslot *s, uint16_t target, uint16_t max)
{
	memset(s, 0, sizeof(*s));
	s->target = target;
	s->max = max;
}

void op_jslot_unprime(struct op_jslot *s)
{
	s->primed = false;
}

/* Next write lands `target` samples after the DAC position; the gap plays as silence. */
static void prime(struct op_jslot *s, uint64_t played_q16)
{
	uint64_t now = (played_q16 + 0xffff) >> 16; /* first sample index not yet played */
	uint64_t wr = now + s->target;
	uint64_t i = s->wr;

	if (wr > i + OP_JSLOT_RING) {
		i = wr - OP_JSLOT_RING;
	}
	for (; i < wr; i++) {
		s->ring[i & MASK] = 0;
	}
	if (s->rd + OP_JSLOT_RING < now) {
		s->rd = now; /* first lock: nothing to replay before it */
	}
	s->wr = wr;
	s->primed = true;
	s->primes++;
}

int32_t op_jslot_arrive(struct op_jslot *s, uint64_t played_q16, int32_t *fill_q16)
{
	int64_t fill = (int64_t)(s->wr << 16) - (int64_t)played_q16;

	if (fill_q16) {
		*fill_q16 = (int32_t)(fill > INT32_MAX ? INT32_MAX : fill < INT32_MIN ? INT32_MIN : fill);
	}
	if (!s->primed) {
		prime(s, played_q16);
		return 0;
	}
	if (fill < 0) {
		s->under++;
		prime(s, played_q16);
		return 0;
	}
	if (fill + ((int64_t)OP_JSLOT_FRAME << 16) > ((int64_t)s->max << 16)) {
		s->over++;
		prime(s, played_q16);
		return 0;
	}
	return (int32_t)(fill - ((int64_t)s->target << 16));
}

void op_jslot_write(struct op_jslot *s, const int16_t pcm[OP_JSLOT_FRAME])
{
	for (int i = 0; i < OP_JSLOT_FRAME; i++) {
		s->ring[(s->wr + i) & MASK] = pcm[i];
	}
	s->wr += OP_JSLOT_FRAME;
}

uint32_t op_jslot_drain(struct op_jslot *s, uint64_t played_q16, uint16_t n,
			void (*out)(const int16_t *blk, uint16_t n, void *ctx), void *ctx)
{
	uint64_t played = played_q16 >> 16;
	int16_t blk[64];
	uint32_t k = 0;

	if (n == 0 || n > 64) {
		return 0;
	}
	while (s->rd + n <= played) {
		for (uint16_t j = 0; j < n; j++) {
			uint64_t i = s->rd + j;

			blk[j] = (i < s->wr && i + OP_JSLOT_RING >= s->wr) ? s->ring[i & MASK] : 0;
		}
		out(blk, n, ctx);
		s->rd += n;
		k++;
	}
	return k;
}
