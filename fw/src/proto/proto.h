/* Text line protocol (host/PROTOCOL.md for the receiver, fw/PROTOCOL.md for both) and the AIR-3 status word.
 * Pure C, no Zephyr: unit-tested on native_sim (fw/tests/proto).
 */
#pragma once
#include <stdint.h>
#include <stddef.h>

#define OP_FW_VERSION "0.1.0"
#define OP_PROTO_MAX_ARGS 5
#define OP_PROTO_LINE_MAX 96
#define OP_PROTO_REPLY_MAX 512 /* `scan` is the longest reply (~380 B) */

/* ---- AIR-3 status u16 (PK-10): bat 7 b | peak 6 b | flags 3 b ---- */
#define OP_ST_CLIP   0x1
#define OP_ST_LOWBAT 0x2
#define OP_ST_TEMP   0x4

struct op_telem {
	uint8_t bat_pct;  /* 0..100 */
	int8_t peak_dbfs; /* -63..0 */
	uint8_t flags;    /* OP_ST_* */
};

/* bits 0-6 battery percent, bits 7-12 peak = 63 + dBFS (63 = full scale), bits 13-15 flags (clip, lowbat, temp).
 * Inputs are clamped.
 */
uint16_t op_status_pack(const struct op_telem *t);
void op_status_unpack(uint16_t w, struct op_telem *t);

/* ---- line parser + command table ---- */
struct op_cmd {
	const char *name;
	/* Write the text after "ok" (may be empty, else start with a space) into out. Return NULL, or an error
	 * reason (reply becomes "err <reason>").
	 */
	const char *(*fn)(void *ctx, int argc, char **argv, char *out, size_t outsz);
};

/* Parse one line (modified in place), dispatch, write one reply line (with "\n") into out.
 * Returns the reply length. Blank lines return 0 (no reply).
 */
size_t op_proto_exec(const struct op_cmd *tbl, size_t n, void *ctx, char *line, char *out, size_t outsz);

/* `dfu` (both roles). op_dfu_hook is set by the platform glue (proto_uart.c) when MCUboot serial recovery is built in;
 * it schedules the reset (the reply must go out first) and returns 0. */
extern int (*op_dfu_hook)(void);
const char *op_c_dfu(void *c, int argc, char **argv, char *out, size_t outsz);

/* Integer args: whole string must parse and lie in [lo, hi]. */
int op_parse_int(const char *s, long lo, long hi, long *v);
/* Decimal dB like "-3.5" -> tenths (-35), within +-limit_tenths. */
int op_parse_tenths(const char *s, int limit_tenths, int *tenths);

/* ---- receiver telemetry (#24 counters, RX-9) ---- */
/* Loss over fixed windows of OP_LOSS_WIN frames (1 s): the last full window, or the running one before the first
 * completes. Pure C. */
#define OP_LOSS_WIN 1000
struct op_loss_win {
	uint32_t n, lost; /* current window */
	int last;         /* permille of the last full window, -1 until one completes */
};
void op_loss_win_init(struct op_loss_win *w);
void op_loss_win_frame(struct op_loss_win *w, int lost);
int op_loss_win_permille(const struct op_loss_win *w);

/* What the app core's merge/PLC/jitter slot know (fw/src/rx_app/rx_app.c). Counts are cumulative since boot. */
struct op_rx_snap {
	int locked;           /* frames arriving now */
	int rssi_dbm;         /* last valid frame, 0 before one */
	uint16_t status_word; /* AIR-3 status of the last valid frame (PK-10) */
	int loss_permille;    /* op_loss_win */
	int td;               /* last frame came from a time-diversity pack */
	uint32_t frames, valid, lost, plc, a_ok, b_ok, skips, td_rec;
	uint32_t under, over; /* jitter slot slips */
	int fill_milli;       /* jitter slot fill at the last arrival, milli-samples */
	int ppb;              /* DAC clock correction applied (clock recovery offset) */
};

/* ---- receiver (host/PROTOCOL.md) ---- */
struct op_rx_state {
	int pack, fa, fb; /* pairing, 0 = unpaired */
	int trim_tenths;
	/* telemetry source, filled by the platform (rx_app.c via op_rx_state_from_snap; the unit test sets fields) */
	void (*sample)(struct op_rx_state *s);
	int locked, rssi_dbm;
	int loss_permille;
	int td;      /* the pack sends time-diversity packets (81 B payload, ADR-0017), from the merge */
	int td_plan; /* what the booth says this pack should send (`td on|off`), 0 until set */
	struct op_telem telem;
	struct op_rx_snap snap; /* counters behind `stats` */
};
extern const struct op_cmd op_rx_cmds[];
extern const size_t op_rx_ncmds;
void op_rx_state_from_snap(struct op_rx_state *s, const struct op_rx_snap *n);

/* ---- pack config (PK-9) ---- */
struct op_pack_cfg {
	int id;         /* 0..7 */
	int ch_a, ch_b; /* MHz */
	int power_dbm;  /* -40..3 */
	char region[4]; /* uk (default) | us | eu | jp */
	int td;         /* time diversity (AIR-3 td_audio, ADR-0017): 0 (default) | 1 */
};
struct op_pack_state {
	struct op_pack_cfg cur, saved; /* saved: the last `save` (RAM copy; flash via persist) */
	int saves;
	/* `save` writes cur through this (NVS, op_store.c); NULL = RAM only. Nonzero return = `err save failed`. */
	int (*persist)(const struct op_pack_cfg *cfg);
};
/* Every field inside the limits the commands enforce (a record read back from flash is checked with this). */
int op_pack_cfg_valid(const struct op_pack_cfg *c);
extern const struct op_cmd op_pack_cmds[];
extern const size_t op_pack_ncmds;
void op_pack_state_init(struct op_pack_state *s, int id, int ch_a, int ch_b);
int op_fb_max(const char *region); /* 2482 uk/eu, 2480 us/jp (AIR-5, ADR-0016) */
/* `td` argument: "on" -> 1, "off" -> 0, else -1. */
int op_parse_onoff(const char *s);
