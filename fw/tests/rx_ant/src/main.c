/* RX-5 antenna choice (fw/src/rx/ant.c, ADR-0011): probe schedule, 6 dB switch, miss ageing. */
#include <zephyr/ztest.h>
#include "op_rx.h"

#define PROBE 100
#define HYST  6

static struct op_ant s;

static void before(void *f)
{
	op_ant_init(&s, PROBE, HYST);
}

ZTEST(rx_ant, test_probe_schedule)
{
	/* Channel A probes at frame 0 mod 100, channel B at 50 mod 100: never both in one frame. */
	for (uint32_t f = 0; f < 3 * PROBE; f++) {
		uint8_t a = op_ant_pick(&s, 0, f);
		uint8_t b = op_ant_pick(&s, 1, f);

		zassert_equal(a, f % PROBE == 0, "frame %u ch A", f);
		zassert_equal(b, f % PROBE == PROBE / 2, "frame %u ch B", f);
		zassert_false(a && b, "both copies on the other antenna in frame %u", f);
	}
	op_ant_init(&s, 0, HYST);
	zassert_equal(op_ant_pick(&s, 0, 0), 0, "probe 0 disables probing");
}

ZTEST(rx_ant, test_switch_at_threshold)
{
	zassert_false(op_ant_report(&s, 0, 0, true, -70), NULL);
	zassert_false(op_ant_report(&s, 0, 1, true, -65), "5 dB stronger: stay");
	zassert_equal(s.cur[0], 0, NULL);
	zassert_true(op_ant_report(&s, 0, 1, true, -64), "6 dB stronger: switch");
	zassert_equal(s.cur[0], 1, NULL);
	zassert_equal(s.cur[1], 0, "channel B is independent");
	/* Now antenna 0 is "other": it needs 6 dB over antenna 1 to come back. */
	zassert_false(op_ant_report(&s, 0, 0, true, -60), NULL);
	zassert_true(op_ant_report(&s, 0, 0, true, -58), NULL);
	zassert_equal(s.switches, 2, NULL);
}

ZTEST(rx_ant, test_dead_antenna_ages_out)
{
	op_ant_report(&s, 1, 0, true, -60);
	op_ant_report(&s, 1, 1, true, -63);
	/* Current antenna stops hearing the pack: 1 dB per missed window, switch once 6 dB below. */
	int n = 0;

	while (!op_ant_report(&s, 1, 0, false, 0)) {
		n++;
		zassert_true(n < 20, "never switched");
	}
	zassert_equal(n + 1, 9, "switch after 9 misses (-60 -> -69 vs -63)");
	zassert_equal(s.cur[1], 1, NULL);
	/* A miss on the probe antenna does not age the current one. */
	zassert_false(op_ant_report(&s, 1, 0, false, 0), NULL);
	zassert_equal(s.last[1][1], -63, NULL);
}

ZTEST(rx_ant, test_first_heard_wins)
{
	zassert_true(op_ant_report(&s, 0, 1, true, -80), "only the other antenna ever heard: switch");
	zassert_equal(s.cur[0], 1, NULL);
}

ZTEST(rx_ant, test_miss_switch_and_hold)
{
	/* ADR-0021: antenna 0 is 3 dB stronger but misses now and then (a hot 3 MHz neighbour); antenna 1 is clean. */
	op_ant_set_miss(&s, 12, 50);
	op_ant_report(&s, 0, 0, true, -47);
	op_ant_report(&s, 0, 1, true, -50);
	zassert_equal(s.cur[0], 0, NULL);
	zassert_true(op_ant_report(&s, 0, 0, false, 0), "a miss with the other antenna good: switch at once");
	zassert_equal(s.cur[0], 1, NULL);
	/* A valid probe on antenna 0 does not win it back during the hold, although it is stronger. */
	zassert_false(op_ant_report(&s, 0, 0, true, -40), "hold: RSSI rule waits");
	for (int i = 0; i < 49; i++) {
		zassert_false(op_ant_report(&s, 0, 1, true, -50), "hold window %d", i);
	}
	zassert_true(op_ant_report(&s, 0, 1, true, -50), "hold over: 10 dB stronger antenna 0 wins back");
	zassert_equal(s.cur[0], 0, NULL);
}

ZTEST(rx_ant, test_miss_switch_needs_good_other)
{
	op_ant_set_miss(&s, 12, 50);
	op_ant_report(&s, 1, 0, true, -47);
	op_ant_report(&s, 1, 1, false, 0);    /* other antenna's last window missed */
	zassert_false(op_ant_report(&s, 1, 0, false, 0), "other not known good: stay");
	op_ant_report(&s, 1, 1, true, -70);   /* other good but 23 dB weaker */
	zassert_false(op_ant_report(&s, 1, 0, false, 0), "other more than 12 dB below: stay");
	zassert_equal(s.cur[1], 0, NULL);
}

ZTEST_SUITE(rx_ant, NULL, NULL, before, NULL, NULL);
