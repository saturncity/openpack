/* Pack config commands over the console / USB CDC (PK-9). A command with no argument reads the value. */
#include <stdio.h>
#include <string.h>
#include "proto.h"

static const char *c_info(void *c, int argc, char **argv, char *out, size_t n)
{
	struct op_pack_state *s = c;

	snprintf(out, n, " fw=%s role=pack id=%d chan=%d,%d power=%d region=%s", OP_FW_VERSION, s->cur.id,
		 s->cur.ch_a, s->cur.ch_b, s->cur.power_dbm, s->cur.region);
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

static const char *c_chan(void *c, int argc, char **argv, char *out, size_t n)
{
	struct op_pack_state *s = c;
	long a, b;

	if (argc == 0) {
		snprintf(out, n, " chan=%d,%d", s->cur.ch_a, s->cur.ch_b);
		return NULL;
	}
	if (argc != 2 || op_parse_int(argv[0], 2402, 2440, &a) || op_parse_int(argv[1], 2402, 2480, &b) ||
	    b < a + 40) {
		return "usage: chan [<fA> <fB>] fA 2402-2440, fB >= fA+40";
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
	if (argc != 1 || (strcmp(argv[0], "us") && strcmp(argv[0], "eu") && strcmp(argv[0], "jp"))) {
		return "usage: region [us|eu|jp]";
	}
	strcpy(s->cur.region, argv[0]);
	return NULL;
}

static const char *c_save(void *c, int argc, char **argv, char *out, size_t n)
{
	struct op_pack_state *s = c;

	s->saved = s->cur; /* RAM only; NVS is a follow-up */
	s->saves++;
	return NULL;
}

const struct op_cmd op_pack_cmds[] = {
	{"info", c_info},   {"id", c_id},         {"chan", c_chan},
	{"power", c_power}, {"region", c_region}, {"save", c_save},
};
const size_t op_pack_ncmds = sizeof(op_pack_cmds) / sizeof(op_pack_cmds[0]);

void op_pack_state_init(struct op_pack_state *s, int id, int ch_a, int ch_b)
{
	memset(s, 0, sizeof(*s));
	s->cur.id = id;
	s->cur.ch_a = ch_a;
	s->cur.ch_b = ch_b;
	s->cur.power_dbm = 0;
	strcpy(s->cur.region, "us");
	s->saved = s->cur;
}
