#include <errno.h>
#include <string.h>
#include <zephyr/kernel.h>
#include <zephyr/storage/flash_map.h>
#include <zephyr/ztest.h>
#include "op_store.h"

/* Blank the NVS area so each test starts from a never-saved device. */
static void blank(void *f)
{
	const struct flash_area *fa;

	zassert_ok(flash_area_open(PARTITION_ID(storage_partition), &fa));
	zassert_ok(flash_area_flatten(fa, 0, fa->fa_size));
	flash_area_close(fa);
	zassert_ok(op_store_init());
}
ZTEST_SUITE(store, NULL, NULL, blank, NULL, NULL);

static struct op_pack_cfg sample(void)
{
	struct op_pack_cfg c = {.id = 5, .ch_a = 2410, .ch_b = 2460, .power_dbm = -8, .td = 1};

	strcpy(c.region, "eu");
	return c;
}

ZTEST(store, test_nothing_saved)
{
	struct op_pack_cfg c = {0};

	zassert_equal(op_store_load(&c), -ENOENT);
}

ZTEST(store, test_round_trip_across_remount) /* "reboot": mount the NVS area again from flash alone */
{
	struct op_pack_cfg in = sample(), out = {0};

	zassert_ok(op_store_save(&in));
	zassert_ok(op_store_init());
	zassert_ok(op_store_load(&out));
	zassert_equal(out.id, 5);
	zassert_equal(out.ch_a, 2410);
	zassert_equal(out.ch_b, 2460);
	zassert_equal(out.power_dbm, -8);
	zassert_equal(out.td, 1);
	zassert_str_equal(out.region, "eu");
}

ZTEST(store, test_overwrite_many_times) /* garbage collection across the two sectors keeps the latest */
{
	struct op_pack_cfg c = sample(), out = {0};

	for (int i = 0; i < 500; i++) {
		c.power_dbm = -40 + i % 44;
		c.id = i % 8;
		zassert_ok(op_store_save(&c));
	}
	zassert_ok(op_store_init());
	zassert_ok(op_store_load(&out));
	zassert_equal(out.power_dbm, c.power_dbm);
	zassert_equal(out.id, c.id);
}

ZTEST(store, test_invalid_record_ignored) /* a record outside the command limits is not loaded */
{
	struct op_pack_cfg bad = sample(), out = {0};

	bad.id = 9;
	zassert_ok(op_store_save(&bad));
	zassert_equal(op_store_load(&out), -EINVAL);
	zassert_equal(out.id, 0);
}

ZTEST(store, test_save_command_end_to_end) /* the console `save` -> flash -> reload */
{
	struct op_pack_state s, t;
	char line[OP_PROTO_LINE_MAX], reply[OP_PROTO_REPLY_MAX];

	op_pack_state_init(&s, 0, 2424, 2473);
	s.persist = op_store_save;
	strcpy(line, "chan 2406 2450");
	op_proto_exec(op_pack_cmds, op_pack_ncmds, &s, line, reply, sizeof(reply));
	strcpy(line, "save");
	op_proto_exec(op_pack_cmds, op_pack_ncmds, &s, line, reply, sizeof(reply));
	zassert_str_equal(reply, "ok\n");

	op_pack_state_init(&t, 0, 2424, 2473); /* fresh boot */
	zassert_ok(op_store_init());
	zassert_ok(op_store_load(&t.cur));
	zassert_equal(t.cur.ch_a, 2406);
	zassert_equal(t.cur.ch_b, 2450);
}
