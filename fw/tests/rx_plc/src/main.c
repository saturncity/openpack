/* RX-6 PLC (fw/src/rx_app/op_plc.c): the sim/loss/plc.py rule, frame by frame. */
#include <stdlib.h>
#include <zephyr/ztest.h>
#include "op_plc.h"

static int16_t good[OP_PLC_N], other[OP_PLC_N], out[OP_PLC_N];

static void setup(void)
{
	for (int i = 0; i < OP_PLC_N; i++) {
		good[i] = (int16_t)(1000 * (i + 1) * (i % 2 ? -1 : 1)); /* +-1000..48000 */
		other[i] = (int16_t)(7 * i - 100);
	}
}

ZTEST(rx_plc, test_good_passes_through)
{
	struct op_plc p;

	setup();
	op_plc_init(&p);
	op_plc_frame(&p, good, out);
	zassert_mem_equal(out, good, sizeof(out));
	zassert_equal(p.concealed, 0);
}

ZTEST(rx_plc, test_repeat_fade_mute)
{
	struct op_plc p;

	setup();
	op_plc_init(&p);
	op_plc_frame(&p, good, out);
	/* lost frames 1..10: the last good frame repeats (10 ms) */
	for (int k = 1; k <= OP_PLC_MUTE_AFTER; k++) {
		op_plc_frame(&p, NULL, out);
		zassert_mem_equal(out, good, sizeof(out), "repeat %d", k);
	}
	/* frame 11: 1 ms linear fade, gain (48 - i) / 48, truncated toward 0 as numpy astype */
	op_plc_frame(&p, NULL, out);
	zassert_equal(out[0], good[0]);
	for (int i = 0; i < OP_PLC_N; i++) {
		int32_t want = (int32_t)good[i] * (OP_PLC_N - i) / OP_PLC_N;

		zassert_equal(out[i], want, "fade[%d] %d != %d", i, out[i], want);
		if (i > 0) {
			zassert_true(abs(out[i]) <= abs(good[i]), "fade grows");
		}
	}
	zassert_equal(out[OP_PLC_N - 1], good[OP_PLC_N - 1] / OP_PLC_N);
	/* then mute */
	for (int k = 0; k < 20; k++) {
		op_plc_frame(&p, NULL, out);
		for (int i = 0; i < OP_PLC_N; i++) {
			zassert_equal(out[i], 0);
		}
	}
	zassert_equal(p.concealed, 31);
	/* the next good frame plays as is (no fade-in, as the model) and resets the run */
	op_plc_frame(&p, other, out);
	zassert_mem_equal(out, other, sizeof(out));
	op_plc_frame(&p, NULL, out);
	zassert_mem_equal(out, other, sizeof(out));
	zassert_equal(p.run, 1);
}

ZTEST(rx_plc, test_loss_before_any_good_is_silent)
{
	struct op_plc p;

	op_plc_init(&p);
	op_plc_frame(&p, NULL, out);
	for (int i = 0; i < OP_PLC_N; i++) {
		zassert_equal(out[i], 0);
	}
}

ZTEST_SUITE(rx_plc, NULL, NULL, NULL, NULL, NULL);
