#include <string.h>
#include <zephyr/ztest.h>
#include "proto.h"

static struct op_rx_state rx;
static struct op_pack_state pk;

static const char *rx_do(const char *cmd)
{
	static char out[OP_PROTO_REPLY_MAX];
	char line[OP_PROTO_LINE_MAX];

	strcpy(line, cmd);
	op_proto_exec(op_rx_cmds, op_rx_ncmds, &rx, line, out, sizeof(out));
	return out;
}

static const char *pk_do(const char *cmd)
{
	static char out[OP_PROTO_REPLY_MAX];
	char line[OP_PROTO_LINE_MAX];

	strcpy(line, cmd);
	op_proto_exec(op_pack_cmds, op_pack_ncmds, &pk, line, out, sizeof(out));
	return out;
}

static void before(void *f)
{
	memset(&rx, 0, sizeof(rx));
	op_pack_state_init(&pk, 2, 2424, 2473);
}
ZTEST_SUITE(proto, NULL, NULL, before, NULL, NULL);

ZTEST(proto, test_status_word_layout)
{
	struct op_telem t = {.bat_pct = 100, .peak_dbfs = 0, .flags = 7}, u;

	zassert_equal(op_status_pack(&t), 100 | (63 << 7) | (7 << 13));
	t = (struct op_telem){.bat_pct = 87, .peak_dbfs = -12, .flags = OP_ST_CLIP | OP_ST_TEMP};
	zassert_equal(op_status_pack(&t), 87 | (51 << 7) | (5 << 13));
	op_status_unpack(op_status_pack(&t), &u);
	zassert_equal(u.bat_pct, 87);
	zassert_equal(u.peak_dbfs, -12);
	zassert_equal(u.flags, 5);
}

ZTEST(proto, test_status_word_clamps)
{
	struct op_telem t = {.bat_pct = 250, .peak_dbfs = -100, .flags = 0xff}, u;

	op_status_unpack(op_status_pack(&t), &u);
	zassert_equal(u.bat_pct, 100);
	zassert_equal(u.peak_dbfs, -63);
	zassert_equal(u.flags, 7);
	t.peak_dbfs = 9;
	op_status_unpack(op_status_pack(&t), &u);
	zassert_equal(u.peak_dbfs, 0);
}

ZTEST(proto, test_rx_info_status)
{
	zassert_str_equal(rx_do("info"), "ok fw=" OP_FW_VERSION "\n");
	rx.locked = 1;
	rx.rssi_dbm = -61;
	rx.loss_permille = 25;
	rx.telem = (struct op_telem){87, -12, OP_ST_CLIP};
	zassert_str_equal(rx_do("status"),
			  "ok locked=1 rssi=-61 loss=0.025 batt=87 peak=-12 clip=1 temp=0 td=0\n");
	rx.td = 1; /* the merge sees 81 B time-diversity packets (ADR-0017) */
	zassert_true(strstr(rx_do("status"), " td=1\n") != NULL);
}

ZTEST(proto, test_td) /* ADR-0017: per-pack time diversity, off by default */
{
	zassert_str_equal(pk_do("td"), "ok td=off\n");
	zassert_str_equal(pk_do("td on"), "ok\n");
	zassert_str_equal(pk_do("td"), "ok td=on\n");
	zassert_equal(pk.cur.td, 1);
	zassert_true(strstr(pk_do("info"), " td=on\n") != NULL);
	zassert_str_equal(pk_do("td maybe"), "err usage: td [on|off]\n");
	zassert_str_equal(pk_do("td on off"), "err usage: td [on|off]\n");
	zassert_str_equal(pk_do("save"), "ok\n");
	zassert_equal(pk.saved.td, 1);
	zassert_str_equal(pk_do("td off"), "ok\n");
	zassert_equal(pk.cur.td, 0);
	/* receiver: what the booth expects; status td= is what arrives */
	zassert_str_equal(rx_do("td"), "ok td=off\n");
	zassert_str_equal(rx_do("td on"), "ok\n");
	zassert_str_equal(rx_do("td"), "ok td=on\n");
	zassert_equal(rx.td_plan, 1);
	zassert_str_equal(rx_do("td 1"), "err usage: td [on|off]\n");
}

ZTEST(proto, test_rx_pair_trim)
{
	zassert_str_equal(rx_do("pair 3 2424 2473"), "ok\n");
	zassert_equal(rx.pack, 3);
	zassert_equal(rx.fb, 2473);
	zassert_str_equal(rx_do("pair 3 2424 2450"), "err bad pairing\n");
	zassert_str_equal(rx_do("pair 9 2424 2473"), "err bad pairing\n");
	zassert_str_equal(rx_do("pair 1 2424"), "err usage: pair <pack> <fA> <fB>\n");
	zassert_str_equal(rx_do("trim -3.5"), "ok\n");
	zassert_equal(rx.trim_tenths, -35);
	zassert_str_equal(rx_do("trim 3"), "ok\n");
	zassert_equal(rx.trim_tenths, 30);
	zassert_true(strncmp(rx_do("trim abc"), "err", 3) == 0);
	zassert_true(strncmp(rx_do("trim 99"), "err", 3) == 0);
}

ZTEST(proto, test_rx_scan_and_errors)
{
	const char *r = rx_do("scan");
	char blank[] = "   ", out[16];

	zassert_true(strncmp(r, "ok 2400:-100 2402:-100", 22) == 0);
	zassert_true(strstr(r, " 2482:-100\n") != NULL);
	zassert_str_equal(rx_do("bogus"), "err unknown command\n");
	zassert_true(strncmp(rx_do("dfu 10"), "err", 3) == 0);
	zassert_str_equal(rx_do("  info  \r"), "ok fw=" OP_FW_VERSION "\n");
	zassert_str_equal(rx_do("a b c d e f"), "err too many args\n");
	zassert_equal(op_proto_exec(op_rx_cmds, op_rx_ncmds, &rx, blank, out, sizeof(out)), 0);
}

ZTEST(proto, test_fb_cap_by_region) /* AIR-5, ADR-0016: 2482 is uk/eu only, same as host/channel_plan.py */
{
	zassert_str_equal(pk_do("region"), "ok region=uk\n"); /* default UK (ADR-0015) */
	zassert_str_equal(pk_do("chan 2414 2482"), "ok\n");
	zassert_true(strncmp(pk_do("chan 2414 2483"), "err", 3) == 0);
	zassert_true(strncmp(pk_do("region us"), "err", 3) == 0); /* fB 2482 would be illegal in the US */
	zassert_str_equal(pk_do("region eu"), "ok\n");
	zassert_str_equal(pk_do("chan 2414 2456"), "ok\n");
	zassert_str_equal(pk_do("region us"), "ok\n");
	zassert_true(strncmp(pk_do("chan 2414 2482"), "err", 3) == 0);
	zassert_str_equal(pk_do("chan 2414 2480"), "ok\n");
	zassert_true(strncmp(pk_do("region jp"), "ok", 2) == 0);
	zassert_equal(op_fb_max("uk"), 2482);
	zassert_equal(op_fb_max("jp"), 2480);
	/* the receiver accepts 2482 in any region: receiving is not regulated, the host checks the plan */
	zassert_str_equal(rx_do("pair 1 2414 2482"), "ok\n");
	zassert_str_equal(rx_do("pair 1 2414 2483"), "err bad pairing\n");
}

ZTEST(proto, test_pack_config)
{
	zassert_str_equal(pk_do("id"), "ok id=2\n");
	zassert_str_equal(pk_do("id 5"), "ok\n");
	zassert_str_equal(pk_do("id 8"), "err usage: id [0-7]\n");
	zassert_str_equal(pk_do("chan 2410 2460"), "ok\n");
	zassert_str_equal(pk_do("chan"), "ok chan=2410,2460\n");
	zassert_true(strncmp(pk_do("chan 2410 2440"), "err", 3) == 0);
	zassert_str_equal(pk_do("power -8"), "ok\n");
	zassert_true(strncmp(pk_do("power 10"), "err", 3) == 0);
	zassert_str_equal(pk_do("region eu"), "ok\n");
	zassert_true(strncmp(pk_do("region xx"), "err", 3) == 0);
	zassert_equal(pk.saved.id, 2); /* not saved yet */
	zassert_str_equal(pk_do("save"), "ok\n");
	zassert_equal(pk.saved.id, 5);
	zassert_str_equal(pk_do("info"),
			  "ok fw=" OP_FW_VERSION " role=pack id=5 chan=2410,2460 power=-8 region=eu td=off\n");
}

ZTEST(proto, test_loss_window) /* RX-9 loss: last full 1000-frame window, running estimate before the first */
{
	struct op_loss_win w;

	op_loss_win_init(&w);
	zassert_equal(op_loss_win_permille(&w), 0);
	for (int i = 0; i < 100; i++) {
		op_loss_win_frame(&w, i < 5); /* 5 of the first 100 */
	}
	zassert_equal(op_loss_win_permille(&w), 50);
	for (int i = 100; i < OP_LOSS_WIN; i++) {
		op_loss_win_frame(&w, i < 115); /* 5 + 15 = 20 of 1000 in the window */
	}
	zassert_equal(op_loss_win_permille(&w), 20);
	op_loss_win_frame(&w, 1); /* a new window does not move the last full one until it completes */
	zassert_equal(op_loss_win_permille(&w), 20);
}

ZTEST(proto, test_rx_status_from_snapshot) /* the app core's counters reach `status` and `stats` */
{
	struct op_rx_snap n = {
		.locked = 1, .rssi_dbm = -63, .loss_permille = 7, .td = 0,
		.status_word = 87 | (51 << 7) | ((OP_ST_CLIP | OP_ST_TEMP) << 13), /* bat 87, peak -12 */
		.frames = 5000, .valid = 4965, .lost = 35, .plc = 35, .a_ok = 4900, .b_ok = 4800, .skips = 2,
		.td_rec = 3, .under = 1, .over = 0, .fill_milli = 6012, .ppb = -1800,
	};

	op_rx_state_from_snap(&rx, &n);
	zassert_str_equal(rx_do("status"),
			  "ok locked=1 rssi=-63 loss=0.007 batt=87 peak=-12 clip=1 temp=1 td=0\n");
	zassert_str_equal(rx_do("stats"),
			  "ok frames=5000 valid=4965 lost=35 plc=35 a_ok=4900 b_ok=4800 skips=2 td_rec=3 under=1 "
			  "over=0 fill_milli=6012 ppb=-1800\n");
}

static int persisted;
static struct op_pack_cfg flash_cfg;
static int persist_fail;
static int fake_persist(const struct op_pack_cfg *c)
{
	if (persist_fail) {
		return -5;
	}
	flash_cfg = *c;
	persisted++;
	return 0;
}

ZTEST(proto, test_save_persists) /* `save` goes through the persist hook; a failure is an err and saves nothing */
{
	pk.persist = fake_persist;
	persisted = 0;
	zassert_str_equal(pk_do("id 6"), "ok\n");
	zassert_str_equal(pk_do("save"), "ok\n");
	zassert_equal(persisted, 1);
	zassert_equal(flash_cfg.id, 6);
	zassert_equal(pk.saved.id, 6);
	persist_fail = 1;
	zassert_str_equal(pk_do("id 7"), "ok\n");
	zassert_str_equal(pk_do("save"), "err save failed\n");
	zassert_equal(pk.saved.id, 6);
	persist_fail = 0;
}

ZTEST(proto, test_cfg_valid)
{
	struct op_pack_cfg c = pk.cur;

	zassert_true(op_pack_cfg_valid(&c));
	c.ch_b = 2482;
	zassert_true(op_pack_cfg_valid(&c));
	strcpy(c.region, "us");
	zassert_false(op_pack_cfg_valid(&c)); /* 2482 is uk/eu only (ADR-0016) */
	c = pk.cur;
	c.id = 8;
	zassert_false(op_pack_cfg_valid(&c));
	c = pk.cur;
	c.ch_b = c.ch_a + 39;
	zassert_false(op_pack_cfg_valid(&c));
	c = pk.cur;
	c.power_dbm = 4;
	zassert_false(op_pack_cfg_valid(&c));
	c = pk.cur;
	strcpy(c.region, "zz");
	zassert_false(op_pack_cfg_valid(&c));
}
