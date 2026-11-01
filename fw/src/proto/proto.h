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

/* Integer args: whole string must parse and lie in [lo, hi]. */
int op_parse_int(const char *s, long lo, long hi, long *v);
/* Decimal dB like "-3.5" -> tenths (-35), within +-limit_tenths. */
int op_parse_tenths(const char *s, int limit_tenths, int *tenths);

/* ---- receiver (host/PROTOCOL.md) ---- */
struct op_rx_state {
	int pack, fa, fb; /* pairing, 0 = unpaired */
	int trim_tenths;
	/* telemetry source, filled by the platform (stub until #23/#24) */
	void (*sample)(struct op_rx_state *s);
	int locked, rssi_dbm;
	int loss_permille;
	int td;      /* the pack sends time-diversity packets (81 B payload, ADR-0017), from the merge */
	int td_plan; /* what the booth says this pack should send (`td on|off`), 0 until set */
	struct op_telem telem;
};
extern const struct op_cmd op_rx_cmds[];
extern const size_t op_rx_ncmds;
void op_rx_stub_sample(struct op_rx_state *s);

/* ---- pack config (PK-9) ---- */
struct op_pack_cfg {
	int id;         /* 0..7 */
	int ch_a, ch_b; /* MHz */
	int power_dbm;  /* -40..3 */
	char region[4]; /* uk (default) | us | eu | jp */
	int td;         /* time diversity (AIR-3 td_audio, ADR-0017): 0 (default) | 1 */
};
struct op_pack_state {
	struct op_pack_cfg cur, saved; /* saved is RAM only: NVS persistence not wired (see fw/PROTOCOL.md) */
	int saves;
};
extern const struct op_cmd op_pack_cmds[];
extern const size_t op_pack_ncmds;
void op_pack_state_init(struct op_pack_state *s, int id, int ch_a, int ch_b);
int op_fb_max(const char *region); /* 2482 uk/eu, 2480 us/jp (AIR-5, ADR-0016) */
/* `td` argument: "on" -> 1, "off" -> 0, else -1. */
int op_parse_onoff(const char *s);
