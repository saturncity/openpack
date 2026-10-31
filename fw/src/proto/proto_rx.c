/* Receiver commands, wire format host/PROTOCOL.md. */
#include <stdio.h>
#include <string.h>
#include "proto.h"

static const char *c_info(void *c, int argc, char **argv, char *out, size_t n)
{
	snprintf(out, n, " fw=%s", OP_FW_VERSION);
	return NULL;
}

static const char *c_status(void *c, int argc, char **argv, char *out, size_t n)
{
	struct op_rx_state *s = c;

	if (s->sample) {
		s->sample(s);
	}
	snprintf(out, n, " locked=%d rssi=%d loss=%d.%03d batt=%u peak=%d clip=%d temp=%d", s->locked,
		 s->rssi_dbm, s->loss_permille / 1000, s->loss_permille % 1000, s->telem.bat_pct,
		 s->telem.peak_dbfs, !!(s->telem.flags & OP_ST_CLIP), !!(s->telem.flags & OP_ST_TEMP));
	return NULL;
}

static const char *c_pair(void *c, int argc, char **argv, char *out, size_t n)
{
	struct op_rx_state *s = c;
	long p, a, b;

	if (argc != 3) {
		return "usage: pair <pack> <fA> <fB>";
	}
	/* same limits as host/channel_plan.py (AIR-5) */
	if (op_parse_int(argv[0], 1, 8, &p) || op_parse_int(argv[1], 2402, 2440, &a) ||
	    op_parse_int(argv[2], 2402, 2480, &b) || b < a + 40) {
		return "bad pairing";
	}
	s->pack = p;
	s->fa = a;
	s->fb = b;
	return NULL;
}

static const char *c_trim(void *c, int argc, char **argv, char *out, size_t n)
{
	struct op_rx_state *s = c;
	int t;

	if (argc != 1 || op_parse_tenths(argv[0], 240, &t)) {
		return "usage: trim <dB> (+-24)";
	}
	s->trim_tenths = t;
	return NULL;
}

static const char *c_scan(void *c, int argc, char **argv, char *out, size_t n)
{
	/* stub until the radio is up (#23): empty band at -100 dBm */
	for (int f = 2400; f <= 2482; f += 2) {
		size_t l = strlen(out);

		snprintf(out + l, n - l, " %d:-100", f);
	}
	return NULL;
}

static const char *c_dfu(void *c, int argc, char **argv, char *out, size_t n)
{
	return "dfu not implemented"; /* MCUboot serial DFU, not this task */
}

const struct op_cmd op_rx_cmds[] = {
	{"info", c_info}, {"status", c_status}, {"pair", c_pair},
	{"trim", c_trim}, {"scan", c_scan},     {"dfu", c_dfu},
};
const size_t op_rx_ncmds = sizeof(op_rx_cmds) / sizeof(op_rx_cmds[0]);

/* Stub telemetry until #23/#24: deterministic, exercises every field. */
void op_rx_stub_sample(struct op_rx_state *s)
{
	static unsigned k;

	k++;
	s->locked = 1;
	s->rssi_dbm = -50 - (int)(k % 5);
	s->loss_permille = 0;
	s->telem.bat_pct = 87;
	s->telem.peak_dbfs = -12;
	s->telem.flags = 0;
}
