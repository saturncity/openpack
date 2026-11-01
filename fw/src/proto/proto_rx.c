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
	snprintf(out, n, " locked=%d rssi=%d loss=%d.%03d batt=%u peak=%d clip=%d temp=%d td=%d", s->locked,
		 s->rssi_dbm, s->loss_permille / 1000, s->loss_permille % 1000, s->telem.bat_pct,
		 s->telem.peak_dbfs, !!(s->telem.flags & OP_ST_CLIP), !!(s->telem.flags & OP_ST_TEMP), !!s->td);
	return NULL;
}

static const char *c_pair(void *c, int argc, char **argv, char *out, size_t n)
{
	struct op_rx_state *s = c;
	long p, a, b;

	if (argc != 3) {
		return "usage: pair <pack> <fA> <fB>";
	}
	/* host/channel_plan.py limits (AIR-5). fB up to 2482 in any region: receiving is not regulated, the host
	 * validates the plan against its region and the pack enforces its own (ADR-0016). */
	if (op_parse_int(argv[0], 1, 8, &p) || op_parse_int(argv[1], 2402, 2440, &a) ||
	    op_parse_int(argv[2], 2402, 2482, &b) || b < a + 40) {
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

/* Time diversity the booth expects from this pack (ADR-0017). The receiver needs no setting, it tells TD
 * packets by length; `status td=` is what the pack actually sends, so the host can flag a mismatch. */
static const char *c_td(void *c, int argc, char **argv, char *out, size_t n)
{
	struct op_rx_state *s = c;
	int v;

	if (argc == 0) {
		snprintf(out, n, " td=%s", s->td_plan ? "on" : "off");
		return NULL;
	}
	if (argc != 1 || (v = op_parse_onoff(argv[0])) < 0) {
		return "usage: td [on|off]";
	}
	s->td_plan = v;
	return NULL;
}

/* Diagnostic counters (not in host/PROTOCOL.md; the host ignores them): merge, PLC, jitter slot, clock recovery. */
static const char *c_stats(void *c, int argc, char **argv, char *out, size_t n)
{
	struct op_rx_state *s = c;
	const struct op_rx_snap *k;

	if (s->sample) {
		s->sample(s);
	}
	k = &s->snap;
	snprintf(out, n,
		 " frames=%u valid=%u lost=%u plc=%u a_ok=%u b_ok=%u skips=%u td_rec=%u under=%u over=%u "
		 "fill_milli=%d ppb=%d",
		 (unsigned)k->frames, (unsigned)k->valid, (unsigned)k->lost, (unsigned)k->plc, (unsigned)k->a_ok,
		 (unsigned)k->b_ok, (unsigned)k->skips, (unsigned)k->td_rec, (unsigned)k->under,
		 (unsigned)k->over, k->fill_milli, k->ppb);
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
	{"td", c_td},       {"stats", c_stats},
};
const size_t op_rx_ncmds = sizeof(op_rx_cmds) / sizeof(op_rx_cmds[0]);

void op_loss_win_init(struct op_loss_win *w)
{
	w->n = w->lost = 0;
	w->last = -1;
}

void op_loss_win_frame(struct op_loss_win *w, int lost)
{
	w->n++;
	w->lost += !!lost;
	if (w->n >= OP_LOSS_WIN) {
		w->last = (int)(w->lost * 1000 / w->n);
		w->n = w->lost = 0;
	}
}

int op_loss_win_permille(const struct op_loss_win *w)
{
	if (w->last >= 0) {
		return w->last;
	}
	return w->n ? (int)(w->lost * 1000 / w->n) : 0;
}

/* Telemetry for `status`: the app core's snapshot, the pack's AIR-3 status word decoded (PK-10). */
void op_rx_state_from_snap(struct op_rx_state *s, const struct op_rx_snap *n)
{
	s->snap = *n;
	s->locked = n->locked;
	s->rssi_dbm = n->rssi_dbm;
	s->loss_permille = n->loss_permille;
	s->td = n->td;
	op_status_unpack(n->status_word, &s->telem);
}
