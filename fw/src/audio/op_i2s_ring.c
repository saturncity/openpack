/* Receiver DAC FIFO (op_i2s_ring.h). Indices are published with release stores and read with acquire loads, so the
 * thread and the I2S interrupt see each other's samples before the index that covers them. */
#include <string.h>
#include "op_i2s_ring.h"

#define MASK (OP_I2S_RING_CAP - 1u)
_Static_assert((OP_I2S_RING_CAP & MASK) == 0, "capacity is a power of 2");

void op_i2s_ring_init(struct op_i2s_ring *q, uint32_t prime)
{
	memset(q, 0, sizeof(*q));
	q->prime = prime > OP_I2S_RING_CAP ? OP_I2S_RING_CAP : prime;
}

uint32_t op_i2s_ring_fill(const struct op_i2s_ring *q)
{
	return __atomic_load_n(&q->w, __ATOMIC_ACQUIRE) - __atomic_load_n(&q->r, __ATOMIC_ACQUIRE);
}

uint32_t op_i2s_ring_put(struct op_i2s_ring *q, const int16_t *s, uint32_t n)
{
	uint32_t w = q->w;
	uint32_t room = OP_I2S_RING_CAP - (w - __atomic_load_n(&q->r, __ATOMIC_ACQUIRE));
	uint32_t k = n < room ? n : room;

	for (uint32_t i = 0; i < k; i++) {
		q->s[(w + i) & MASK] = s[i];
	}
	__atomic_store_n(&q->w, w + k, __ATOMIC_RELEASE);
	q->over += n - k;
	return n - k;
}

void op_i2s_ring_get(struct op_i2s_ring *q, int16_t *dst, uint32_t n)
{
	uint32_t r = q->r;
	uint32_t avail = __atomic_load_n(&q->w, __ATOMIC_ACQUIRE) - r;
	uint32_t k = 0;

	if (!q->primed && avail >= q->prime) {
		q->primed = true;
	}
	if (q->primed) {
		k = n < avail ? n : avail;
		for (uint32_t i = 0; i < k; i++) {
			dst[i] = q->s[(r + i) & MASK];
		}
		__atomic_store_n(&q->r, r + k, __ATOMIC_RELEASE);
		if (k < n) {
			q->primed = false; /* underrun: wait for prime samples again */
			q->under += n - k;
		}
	}
	memset(&dst[k], 0, (n - k) * sizeof(*dst));
	q->out += n;
}
