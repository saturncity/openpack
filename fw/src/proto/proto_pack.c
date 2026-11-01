/* Pack config commands over the console / USB CDC (PK-9). A command with no argument reads the value. */
#include <stdio.h>
#include <string.h>
#include "proto.h"

static const char *c_info(void *c, int argc, char **argv, char *out, size_t n)
{
	struct op_pack_state *s = c;

	snprintf(out, n, " fw=%s role=pack id=%d chan=%d,%d power=%d region=%s td=%s", OP_FW_VERSION, s->cur.id,
		 s->cur.ch_a, s->cur.ch_b, s->cur.power_dbm, s->cur.region, s->cur.td ? "on" : "off");
	return NULL;
}

static const char *c_id(void *c, int argc, char **argv, char *out, size_t n)
{
	struct op_pack_state *s = c;
	long v;

	if (argc == 0) {
		snprintf(out, n, " id=%d", s->cur.id);
		return NULL;
	}
	if (argc != 1 || op_parse_int(argv[0], 0, 7, &v)) {
		return "usage: id [0-7]";
	}
	s->cur.id = v;
	return NULL;
}

/* Highest copy-B carrier for a region (AIR-5, ADR-0016), same as host/channel_plan.py FB_MAX: EN 300 328
 * (uk, eu) keeps a 2482 MHz BLE-2M carrier inside 2400-2483.5 at 9 dBm EIRP; us (15.205) and jp stop at 2480. */
int op_fb_max(const char *region)
{
	return (!strcmp(region, "uk") || !strcmp(region, "eu")) ? 2482 : 2480;
}

static const char *c_chan(void *c, int argc, char **argv, char *out, size_t n)
{
	struct op_pack_state *s = c;
	long a, b;

	if (argc == 0) {
		snprintf(out, n, " chan=%d,%d", s->cur.ch_a, s->cur.ch_b);
		return NULL;
	}
	if (argc != 2 || op_parse_int(argv[0], 2402, 2440, &a) ||
	    op_parse_int(argv[1], 2402, op_fb_max(s->cur.region), &b) || b < a + 40) {
		return "usage: chan [<fA> <fB>] fA 2402-2440, fB >= fA+40, fB <= 2482 uk/eu, 2480 us/jp";
	}
	s->cur.ch_a = a;
	s->cur.ch_b = b;
	return NULL;
}

static const char *c_power(void *c, int argc, char **argv, char *out, size_t n)
{
	struct op_pack_state *s = c;
	long v;

	if (argc == 0) {
		snprintf(out, n, " power=%d", s->cur.power_dbm);
		return NULL;
	}
	if (argc != 1 || op_parse_int(argv[0], -40, 3, &v)) {
		return "usage: power [-40..3 dBm]";
	}
	s->cur.power_dbm = v;
	return NULL;
}

static const char *c_region(void *c, int argc, char **argv, char *out, size_t n)
{
	struct op_pack_state *s = c;

	if (argc == 0) {
		snprintf(out, n, " region=%s", s->cur.region);
		return NULL;
	}
	if (argc != 1 || (strcmp(argv[0], "uk") && strcmp(argv[0], "us") && strcmp(argv[0], "eu") &&
			  strcmp(argv[0], "jp"))) {
		return "usage: region [uk|us|eu|jp]";
	}
	if (s->cur.ch_b > op_fb_max(argv[0])) {
		return "fB above 2480 not allowed there: set chan first"; /* ADR-0016: 2482 is uk/eu only */
	}
	strcpy(s->cur.region, argv[0]);
	return NULL;
}

/* Time diversity (ADR-0017): a configuration-time setting, like chan. The frame source reads it every frame. */
static const char *c_td(void *c, int argc, char **argv, char *out, size_t n)
{
	struct op_pack_state *s = c;
	int v;

	if (argc == 0) {
		snprintf(out, n, " td=%s", s->cur.td ? "on" : "off");
		return NULL;
	}
	if (argc != 1 || (v = op_parse_onoff(argv[0])) < 0) {
		return "usage: td [on|off]";
	}
	s->cur.td = v;
	return NULL;
}

static const char *c_save(void *c, int argc, char **argv, char *out, size_t n)
{
	struct op_pack_state *s = c;

	if (s->persist && s->persist(&s->cur)) {
		return "save failed";
	}
	s->saved = s->cur;
	s->saves++;
	return NULL;
}

int op_pack_cfg_valid(const struct op_pack_cfg *c)
{
	if (c->id < 0 || c->id > 7 || c->power_dbm < -40 || c->power_dbm > 3 || (c->td != 0 && c->td != 1)) {
		return 0;
	}
	if (strcmp(c->region, "uk") && strcmp(c->region, "us") && strcmp(c->region, "eu") &&
	    strcmp(c->region, "jp")) {
		return 0;
	}
	return c->ch_a >= 2402 && c->ch_a <= 2440 && c->ch_b >= c->ch_a + 40 && c->ch_b <= op_fb_max(c->region);
}

const struct op_cmd op_pack_cmds[] = {
	{"info", c_info},   {"id", c_id},         {"chan", c_chan},
	{"power", c_power}, {"region", c_region}, {"td", c_td},
	{"save", c_save},
};
const size_t op_pack_ncmds = sizeof(op_pack_cmds) / sizeof(op_pack_cmds[0]);

void op_pack_state_init(struct op_pack_state *s, int id, int ch_a, int ch_b)
{
	memset(s, 0, sizeof(*s));
	s->cur.id = id;
	s->cur.ch_a = ch_a;
	s->cur.ch_b = ch_b;
	s->cur.power_dbm = 0;
	strcpy(s->cur.region, "uk"); /* default region UK (ADR-0015) */
	s->saved = s->cur;
}
