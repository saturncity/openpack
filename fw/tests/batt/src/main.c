/* PK-8 / ADR-0012 cell monitor (fw/src/app/op_batt.c): the pack's R12/R13 = 1M/1M divider, red LED below 3.4 V
 * with 50 mV hysteresis, cutoff after 5 samples below 3.3 V, latched. */
#include <zephyr/ztest.h>
#include "op_batt.h"

#define FULL 2000000u /* R12 + R13, hw/pack/out/pack.net (the board's vbat node) */
#define OUT  1000000u

static struct op_batt b;

static void before(void *f)
{
	op_batt_init(&b, 3400, 3300, 50, 5);
}

ZTEST(batt, test_divider)
{
	zassert_equal(op_batt_cell_mv(2100, FULL, OUT), 4200, "4.2 V cell reads 2.1 V at the pin");
	zassert_equal(op_batt_cell_mv(1650, FULL, OUT), 3300);
	zassert_equal(op_batt_cell_mv(-3, FULL, OUT), 0, "negative SAADC reading clamps to 0");
	zassert_equal(op_batt_cell_mv(1000, 280000, 100000), 2800, "other ratios");
	zassert_equal(op_batt_cell_mv(1, 3, 2), 2, "rounded, not truncated (1.5 -> 2)");
}

ZTEST(batt, test_low_hysteresis)
{
	zassert_equal(op_batt_update(&b, 3900), OP_BATT_OK);
	zassert_equal(op_batt_update(&b, 3399), OP_BATT_LOW, "red below 3.4 V");
	zassert_equal(op_batt_update(&b, 3420), OP_BATT_LOW, "inside the hysteresis band");
	zassert_equal(op_batt_update(&b, 3450), OP_BATT_OK, "green again at 3.45 V");
	zassert_equal(op_batt_update(&b, 3400), OP_BATT_OK, "3.4 V itself is not low");
}

ZTEST(batt, test_cutoff_needs_consecutive_samples)
{
	for (int i = 0; i < 4; i++) {
		zassert_equal(op_batt_update(&b, 3299), OP_BATT_LOW, "sample %d", i);
	}
	zassert_equal(op_batt_update(&b, 3300), OP_BATT_LOW, "3.3 V resets the count");
	for (int i = 0; i < 4; i++) {
		zassert_equal(op_batt_update(&b, 3200), OP_BATT_LOW, "sample %d", i);
	}
	zassert_equal(op_batt_update(&b, 3200), OP_BATT_CUTOFF, "5th in a row");
}

ZTEST(batt, test_cutoff_latches)
{
	for (int i = 0; i < 5; i++) {
		(void)op_batt_update(&b, 3000);
	}
	zassert_equal(op_batt_update(&b, 4200), OP_BATT_CUTOFF, "a recovering cell does not restart the pack");
	zassert_equal(b.last_mv, 4200);
}

ZTEST(batt, test_one_sample_cutoff)
{
	op_batt_init(&b, 3400, 3300, 50, 0);
	zassert_equal(op_batt_update(&b, 3299), OP_BATT_CUTOFF, "cut_n 0 behaves as 1");
}

ZTEST_SUITE(batt, NULL, NULL, before, NULL, NULL);
