/* RX-7 clock recovery, closed loop on the host (ADR-0013): the real PI loop (op_clk.c), jitter slot
 * (op_jslot.c) and HFCLKAUDIO step quantisation (op_aclk_quant) against a modelled pack clock and
 * receiver DAC clock, 1 simulated hour per case (3.6 M frames).
 *
 * Plant: the pack sends one frame per 1 ms of its own crystal (1 + ep); frames reach the app core
 * with +-5 us uniform jitter (IPC, merge deadline re-centring). The DAC plays 48 kHz of the receiver
 * crystal (1 + er) times (1 + applied correction). RX-7 asserts, after lock:
 *   - 0 slips (no underrun, no overrun, the slot never re-primes after the first frame)
 *   - output rate error <= 1 sample/h: mean fill over the last minute minus mean fill over the
 *     first minute after lock (any rate error accumulates in the fill)
 *   - fill error within +-1 sample of the target every frame after lock (bounded steady state)
 */
#include <math.h>
#include <zephyr/ztest.h>
#include "op_clk.h"
#include "op_jslot.h"

#define TARGET   6
#define SLOT_MAX      (TARGET + 2 * OP_JSLOT_FRAME)
#define KP       26000
#define KI       8
#define LIM      100000
#define FRAMES   3600000 /* 1 h */
#define LOCK_FR  10000   /* "after lock" = after 10 s */
#define MIN_FR   60000   /* one minute */
#define JIT_US   5.0

struct res {
	uint32_t slips, primes;
	double lock_s, worst_err, drift, ss_ppb, lat_us, start_dev;
};

static uint32_t lcg = 1;

static double urand(void) /* [-1, 1) */
{
	lcg = lcg * 1664525u + 1013904223u;
	return (double)lcg / 2147483648.0 - 1.0;
}

/* ep(t), er: crystal offsets (fraction). ramp: if nonzero, ep goes linearly from ep0 to ep1
 * between t = 1200 s and 1200 + ramp s (temperature change). */
static struct res run(double ep0, double ep1, double ramp, double er)
{
	static struct op_jslot js;
	struct op_clk c;
	struct res r = {0};
	double t = 0, t_dac = 0, played = 0, u = 0, sum_first = 0, sum_last = 0, sum_u = 0, sum_need = 0,
	       sum_lat = 0;
	int32_t applied = 0;
	uint32_t locked_at = 0;

	op_clk_init(&c, KP, KI, LIM);
	op_jslot_init(&js, TARGET, SLOT_MAX);
	lcg = 12345;
	for (uint32_t k = 0; k < FRAMES; k++) {
		double ep = ep0;

		if (ramp > 0 && t > 1200) {
			ep = t > 1200 + ramp ? ep1 : ep0 + (ep1 - ep0) * (t - 1200) / ramp;
		}
		t += 1e-3 / (1 + ep);
		double ta = t + JIT_US * 1e-6 * urand();

		played += (ta - t_dac) * 48000.0 * (1 + er) * (1 + u);
		if (k >= FRAMES / 2) { /* time-weighted DAC rate error vs the pack, second half hour */
			sum_u += ((1 + er) * (1 + u) - (1 + ep)) / (1 + ep) * (ta - t_dac);
			sum_need += ta - t_dac;
		}
		t_dac = ta;
		int32_t fill;
		int32_t err = op_jslot_arrive(&js, (uint64_t)(played * 65536.0), &fill);
		double e = err / 65536.0;

		applied = op_aclk_quant(op_clk_update(&c, err), NULL);
		u = applied * 1e-9;
		int16_t pcm[OP_JSLOT_FRAME] = {0};

		op_jslot_write(&js, pcm);
		if (k < LOCK_FR) {
			r.start_dev = fmax(r.start_dev, fabs(e));
			if (fabs(e) > 1.0) {
				locked_at = k + 1;
			}
			continue;
		}
		r.worst_err = fmax(r.worst_err, fabs(e));
		sum_lat += fill / 65536.0;
		if (k < LOCK_FR + MIN_FR) {
			sum_first += e;
		}
		if (k >= FRAMES - MIN_FR) {
			sum_last += e;
		}
	}
	r.slips = js.under + js.over;
	r.primes = js.primes;
	r.lock_s = locked_at / 1000.0;
	r.drift = (sum_last - sum_first) / MIN_FR;
	r.ss_ppb = sum_u / sum_need * 1e9;
	r.lat_us = sum_lat / (FRAMES - LOCK_FR) / 48.0 * 1000.0;
	printk("RX_CLK ep=%+.1f->%+.1f ppm er=%+.1f ppm: slips=%u primes=%u lock_s=%.3f "
	       "start_dev=%.3f worst_err_samples=%.3f drift_samples_per_h=%+.4f ss_err_ppb=%+.2f "
	       "slot_latency_us=%.1f\n",
	       ep0 * 1e6, ep1 * 1e6, er * 1e6, r.slips, r.primes, r.lock_s, r.start_dev, r.worst_err,
	       r.drift, r.ss_ppb, r.lat_us);
	return r;
}

static void check(struct res r)
{
	zassert_equal(r.slips, 0, "slips");
	zassert_equal(r.primes, 1, "slot re-primed");
	zassert_true(r.lock_s < 5.0, "lock %.3f s", r.lock_s);
	zassert_true(r.worst_err <= 1.0, "fill error %.3f samples after lock", r.worst_err);
	zassert_true(fabs(r.drift) <= 1.0, "rate error %.3f samples/h", r.drift);
	/* 1 sample/h = 1 / (48000 * 3600) = 5.8 ppb */
	zassert_true(fabs(r.ss_ppb) <= 5.8, "steady-state rate error %.2f ppb", r.ss_ppb);
}

ZTEST(rx_clk, test_plus40ppm_1h)
{
	check(run(20e-6, 20e-6, 0, -20e-6));
}

ZTEST(rx_clk, test_minus40ppm_1h)
{
	check(run(-20e-6, -20e-6, 0, 20e-6));
}

/* Pack crystal swings 40 ppm in 10 minutes (far faster than any real temperature change). */
ZTEST(rx_clk, test_ramp_1h)
{
	check(run(20e-6, -20e-6, 600, -20e-6));
}

ZTEST(rx_clk, test_pi_basics)
{
	struct op_clk c;
	int32_t s;

	op_clk_init(&c, KP, KI, LIM);
	zassert_equal(op_clk_update(&c, 0), 0);
	zassert_equal(op_clk_update(&c, 65536), KP + KI); /* P + one frame of integral */
	for (int i = 0; i < 100000; i++) {
		op_clk_update(&c, 65536 * 50);
	}
	zassert_equal(c.out, LIM, "clamped");
	zassert_equal(c.integ, (int64_t)LIM * 65536, "anti-windup");
	zassert_equal(op_aclk_quant(1655, &s), 0);
	zassert_equal(op_aclk_quant(1656, &s), OP_ACLK_STEP_PPB);
	zassert_equal(s, 1);
	zassert_equal(op_aclk_quant(-40000, &s), -12 * OP_ACLK_STEP_PPB);
}

ZTEST(rx_clk, test_slot_slips)
{
	static struct op_jslot js;
	int16_t pcm[OP_JSLOT_FRAME];
	uint64_t p = 1000ULL << 16;

	for (int i = 0; i < OP_JSLOT_FRAME; i++) {
		pcm[i] = i + 1;
	}
	op_jslot_init(&js, TARGET, SLOT_MAX);
	zassert_equal(op_jslot_arrive(&js, p, NULL), 0);
	op_jslot_write(&js, pcm);
	zassert_equal(js.wr, 1000 + TARGET + 48);
	/* on time: fill = target -> err 0 */
	p += 48ULL << 16;
	zassert_equal(op_jslot_arrive(&js, p, NULL), 0);
	zassert_equal(js.primes, 1);
	op_jslot_write(&js, pcm);
	/* late by target + 1 sample -> underrun, re-prime */
	p += (48ULL + TARGET + 1) << 16;
	op_jslot_arrive(&js, p, NULL);
	zassert_equal(js.under, 1);
	zassert_equal(js.primes, 2);
	op_jslot_write(&js, pcm);
	/* two frames without play-out -> fill + 48 > max -> overrun */
	op_jslot_arrive(&js, p, NULL);
	op_jslot_write(&js, pcm);
	op_jslot_arrive(&js, p, NULL);
	zassert_equal(js.over, 1);
}

static int16_t got[512];
static uint32_t ngot;

static void sink(const int16_t *blk, uint16_t n, void *ctx)
{
	for (int i = 0; i < n; i++) {
		got[ngot++] = blk[i];
	}
}

ZTEST(rx_clk, test_slot_drain)
{
	static struct op_jslot js;
	int16_t pcm[OP_JSLOT_FRAME];
	uint64_t p = 0;

	for (int i = 0; i < OP_JSLOT_FRAME; i++) {
		pcm[i] = i + 1;
	}
	op_jslot_init(&js, TARGET, SLOT_MAX);
	ngot = 0;
	op_jslot_arrive(&js, p, NULL);
	op_jslot_write(&js, pcm);
	p += 48ULL << 16;
	zassert_equal(op_jslot_drain(&js, p, 8, sink, NULL), 6);
	/* target samples of priming silence, then the frame */
	for (int i = 0; i < TARGET; i++) {
		zassert_equal(got[i], 0);
	}
	for (int i = TARGET; i < 48; i++) {
		zassert_equal(got[i], i - TARGET + 1);
	}
	/* no further frame: the DAC plays the frame tail then silence */
	p += 48ULL << 16;
	zassert_equal(op_jslot_drain(&js, p, 8, sink, NULL), 6);
	zassert_equal(got[48 + TARGET - 1], 48);
	zassert_equal(got[48 + TARGET], 0);
}

ZTEST_SUITE(rx_clk, NULL, NULL, NULL, NULL, NULL);
