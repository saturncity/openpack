/* #97 pack frame lead loop, closed loop on the host (ADR-0022): the real loop (op_lead.c: op_clk PI
 * + HFCLKAUDIO step dither) against a modelled audio frame clock and net-core latch, 1 simulated
 * hour per case (3.6 M frames).
 *
 * Plant: the net core latches at n * 1000 + 980 us of TIMER0 (#98). The audio frame clock starts
 * 100 us before a latch (the sync, ADR-0020) and runs at (1 + d) * (1 + steps * 3311 ppb); a frame
 * reaches the net core 0..30 us after its clock (encode + IPC + load jitter). It goes on air in the
 * first slot whose latch follows its arrival. Two frames in one slot = a skip (one never on air),
 * a slot with none = a repeat. Every 100 frames (the first time after 10) the net core reports the
 * earliest frame's margin (latch - arrival, integer us, as TIMER0 captures it). Asserted per case, closed loop:
 *   - 0 skips, 0 repeats in 1 h
 *   - margin never below 40 us (the frame lead is 100, the arrival jitter 30)
 *   - after 60 s: every report within +-3 us of the reference (the lead holds; 1 us TIMER0
 *     capture + the earliest-of-100 jitter make a +-3 us limit cycle)
 * Negative controls, loop open: +0.371 ppm skips within the hour (#97: about every 45 min),
 * -40 ppm repeats within seconds.
 */
#include <math.h>
#include <stdlib.h>
#include <zephyr/ztest.h>
#include "op_lead.h"

#define KP     2000
#define KI     100
#define LIM    100000
#define WIN    100
#define WIN1   10 /* the net core's first window (sched.c LEAD_FIRST_FRAMES): the reference */
#define LEAD   100
#define LATCH  980.0
#define FRAMES 3600000 /* 1 h */
#define SS_FR  60000   /* steady state after 60 s */
#define PROC   30.0

struct res {
	uint32_t skips, repeats, first_bad_s;
	int32_t mmin, ss_dev;
	double ss_mean, peak_dev;
};

static uint32_t lcg = 1;

static double u01(void)
{
	lcg = lcg * 1664525u + 1013904223u;
	return (double)lcg / 4294967296.0;
}

static struct res run(double d_ppb, bool open)
{
	struct op_lead l;
	struct res r = {.mmin = INT32_MAX};
	double t = LATCH - LEAD, sum = 0;
	int64_t last = -1;
	int32_t wmax = INT32_MIN;
	uint32_t n = 0, nss = 0, win = WIN1;

	op_lead_init(&l, KP, KI, LIM, open);
	lcg = 777;
	for (uint32_t k = 0; k < FRAMES; k++) {
		double arr = t + PROC * u01();
		int64_t slot = (int64_t)floor((arr - LATCH) / 1000.0) + 1;
		int32_t m = (int32_t)(slot * 1000 + LATCH - floor(arr));

		if (last >= 0 && (slot == last || slot > last + 1)) {
			r.skips += slot == last;
			r.repeats += slot > last + 1 ? slot - last - 1 : 0;
			if (!r.first_bad_s) {
				r.first_bad_s = k / 1000 + 1;
			}
		}
		last = slot;
		if (m > LEAD + 500) { /* the net core's +-half-frame window around the lead */
			m -= 1000;
		}
		r.mmin = MIN(r.mmin, m);
		wmax = MAX(wmax, m);
		if (++n == win) {
			win = WIN;
			op_lead_report(&l, wmax);
			r.peak_dev = fmax(r.peak_dev, fabs(wmax - l.ref));
			if (k >= SS_FR) {
				r.ss_dev = MAX(r.ss_dev, abs(wmax - l.ref));
				sum += wmax;
				nss++;
			}
			n = 0;
			wmax = INT32_MIN;
		}
		t += 1000.0 * (1 - (d_ppb + op_lead_frame(&l) * (double)OP_ACLK_STEP_PPB) * 1e-9);
	}
	r.ss_mean = nss ? sum / nss : 0;
	printk("PACK_LEAD d=%+.3f ppm %s: skips=%u repeats=%u first_bad_s=%u margin_min_us=%d "
	       "peak_dev_us=%.0f ss_dev_us=%d ss_margin_us=%.2f ref_us=%d ppb=%d\n",
	       d_ppb / 1000, open ? "open" : "closed", r.skips, r.repeats, r.first_bad_s, r.mmin,
	       r.peak_dev, r.ss_dev, r.ss_mean, l.ref, l.ppb);
	return r;
}

static void check(struct res r)
{
	zassert_equal(r.skips, 0, "skips");
	zassert_equal(r.repeats, 0, "repeats");
	zassert_true(r.mmin >= 40, "margin %d us", r.mmin);
	zassert_true(r.ss_dev <= 3, "steady-state margin deviation %d us", r.ss_dev);
}

ZTEST(pack_lead, test_hfclkaudio_plus0371ppm_1h)
{
	check(run(371, false));
}

ZTEST(pack_lead, test_plus40ppm_1h)
{
	check(run(40000, false));
}

ZTEST(pack_lead, test_minus40ppm_1h)
{
	check(run(-40000, false));
}

ZTEST(pack_lead, test_open_loop_skips)
{
	struct res r = run(371, true);

	zassert_true(r.skips > 0 && r.first_bad_s > 1800, "open loop +0.371 ppm: skip after %u s",
		     r.first_bad_s);
	r = run(-40000, true);
	zassert_true(r.repeats > 0 && r.first_bad_s < 10, "open loop -40 ppm: repeat after %u s",
		     r.first_bad_s);
}

ZTEST(pack_lead, test_dither)
{
	const int32_t want[] = {371, 1655, 1656, -371, 12345, -40000, 0};

	for (size_t i = 0; i < ARRAY_SIZE(want); i++) {
		int32_t acc = 0;
		int64_t sum = 0;

		for (int k = 0; k < 10000; k++) {
			int32_t s = op_aclk_dither(want[i], &acc);

			zassert_true(abs(s * OP_ACLK_STEP_PPB - want[i]) < OP_ACLK_STEP_PPB, "one step around");
			sum += s;
			zassert_true(abs(acc) <= OP_ACLK_STEP_PPB / 2 + 1, "remainder bounded");
		}
		/* mean within 1 step / 10000 frames */
		zassert_true(llabs(sum * OP_ACLK_STEP_PPB - (int64_t)want[i] * 10000) <= OP_ACLK_STEP_PPB,
			     "%d ppb: mean %lld", want[i], sum * OP_ACLK_STEP_PPB / 10000);
	}
}

ZTEST(pack_lead, test_reference_is_first_report)
{
	struct op_lead l;

	op_lead_init(&l, KP, KI, LIM, false);
	zassert_equal(op_lead_report(&l, 93), 0);
	zassert_equal(l.ref, 93);
	zassert_equal(op_lead_report(&l, 92), KP + KI); /* 1 us late: speed up */
	op_lead_init(&l, KP, KI, LIM, true);
	op_lead_report(&l, 93);
	zassert_equal(op_lead_report(&l, 50), 0, "open loop: no correction");
}

ZTEST_SUITE(pack_lead, NULL, NULL, NULL, NULL, NULL);
