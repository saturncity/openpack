/* Receiver I2S DAC FIFO (fw/src/audio/op_i2s_ring.c, #118). The producer is the jitter slot's drain (8-sample
 * write_block calls, 6 per 1 ms frame), the consumer the TXPTRUPD interrupt (one 8-sample DMA block per call). */
#include <zephyr/ztest.h>
#include "op_i2s_ring.h"

#define BLK   8
#define PRIME (2 * BLK)

static struct op_i2s_ring q;

static void before(void *f)
{
	op_i2s_ring_init(&q, PRIME);
}

static void ramp(int16_t *s, uint32_t n, int16_t from)
{
	for (uint32_t i = 0; i < n; i++) {
		s[i] = (int16_t)(from + i);
	}
}

ZTEST(i2s_ring, test_zeros_until_primed)
{
	int16_t in[BLK], out[BLK];

	ramp(in, BLK, 1);
	zassert_equal(op_i2s_ring_put(&q, in, BLK), 0);
	op_i2s_ring_get(&q, out, BLK);
	for (int i = 0; i < BLK; i++) {
		zassert_equal(out[i], 0, "silence while priming");
	}
	zassert_equal(op_i2s_ring_fill(&q), BLK, "priming consumes nothing");
	zassert_equal(q.under, 0, "priming is not an underrun");
	ramp(in, BLK, 1 + BLK);
	(void)op_i2s_ring_put(&q, in, BLK);
	op_i2s_ring_get(&q, out, BLK);
	for (int i = 0; i < BLK; i++) {
		zassert_equal(out[i], 1 + i, "first queued sample first");
	}
	zassert_equal(q.out, 2 * BLK);
}

ZTEST(i2s_ring, test_steady_state_is_bit_exact_across_wrap)
{
	int16_t in[BLK], out[BLK];
	int16_t next_in = 0, next_out = 0;

	for (int i = 0; i < PRIME / BLK; i++) {
		ramp(in, BLK, next_in);
		next_in += BLK;
		(void)op_i2s_ring_put(&q, in, BLK);
	}
	for (int blk = 0; blk < 10 * OP_I2S_RING_CAP; blk++) { /* many wraps of the 128-sample buffer */
		ramp(in, BLK, next_in);
		next_in += BLK;
		zassert_equal(op_i2s_ring_put(&q, in, BLK), 0);
		op_i2s_ring_get(&q, out, BLK);
		for (int i = 0; i < BLK; i++) {
			zassert_equal(out[i], (int16_t)(next_out + i), "block %d sample %d", blk, i);
		}
		next_out += BLK;
		zassert_equal(op_i2s_ring_fill(&q), PRIME, "fill holds at the prime level");
	}
	zassert_equal(q.under + q.over, 0);
}

ZTEST(i2s_ring, test_underrun_zero_fills_and_reprimes)
{
	int16_t in[PRIME], out[BLK];

	ramp(in, PRIME, 100);
	(void)op_i2s_ring_put(&q, in, PRIME);
	op_i2s_ring_get(&q, out, BLK);
	op_i2s_ring_get(&q, out, BLK);
	zassert_equal(out[BLK - 1], 100 + PRIME - 1);
	(void)op_i2s_ring_put(&q, in, 3); /* producer late: only 3 samples */
	op_i2s_ring_get(&q, out, BLK);
	zassert_equal(out[0], 100);
	zassert_equal(out[2], 102);
	for (int i = 3; i < BLK; i++) {
		zassert_equal(out[i], 0, "missing samples are zeros");
	}
	zassert_equal(q.under, BLK - 3);
	(void)op_i2s_ring_put(&q, in, BLK); /* less than prime: still silent */
	op_i2s_ring_get(&q, out, BLK);
	zassert_equal(out[0], 0, "re-priming after an underrun");
	zassert_equal(q.under, BLK - 3, "re-priming does not count as underrun");
	(void)op_i2s_ring_put(&q, in, BLK);
	op_i2s_ring_get(&q, out, BLK);
	zassert_equal(out[0], 100, "plays again once primed");
}

ZTEST(i2s_ring, test_overrun_drops_newest)
{
	int16_t in[OP_I2S_RING_CAP + BLK], out[BLK];

	ramp(in, OP_I2S_RING_CAP + BLK, 0);
	zassert_equal(op_i2s_ring_put(&q, in, OP_I2S_RING_CAP + BLK), BLK, "the last block does not fit");
	zassert_equal(q.over, BLK);
	zassert_equal(op_i2s_ring_fill(&q), OP_I2S_RING_CAP);
	op_i2s_ring_get(&q, out, BLK);
	zassert_equal(out[0], 0, "oldest sample kept");
	zassert_equal(op_i2s_ring_put(&q, in, BLK), 0, "room again after a block was played");
}

ZTEST(i2s_ring, test_prime_clamped_to_capacity)
{
	op_i2s_ring_init(&q, 10 * OP_I2S_RING_CAP);
	zassert_equal(q.prime, OP_I2S_RING_CAP);
}

ZTEST_SUITE(i2s_ring, NULL, NULL, before, NULL, NULL);
