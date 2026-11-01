/* Receiver role (RX-2..RX-5). Net core: acquisition, tracking, copy merge, antenna choice.
 * App core: consumes one merged frame per 1 ms over the op_frame IPC endpoint (FW-2, net -> app).
 */
#pragma once
#include <stdbool.h>
#include <stdint.h>
#include "op_frame.h"

/* One IPC message per frame period while locked, valid or not (the app core runs PLC on gaps, RX-6). */
#define OP_RX_VALID (1u << 0) /* frame[] holds a CRC-valid copy */
#define OP_RX_A_OK  (1u << 1) /* copy A was CRC-valid */
#define OP_RX_B_OK  (1u << 2) /* copy B was CRC-valid */
#define OP_RX_TD    (1u << 3) /* the pack sends time diversity (81 B): frame is 2 packets late (ADR-0017) */
#define OP_RX_TD_REC (1u << 4) /* both copies lost, frame recovered from packet n+2's td_audio (RX-4) */

/* With OP_RX_TD, A_OK/B_OK/rssi are those of the frame's own packet (n), not of packet n+2. */
struct op_rx_msg {
	uint8_t frame[OP_FRAME_LEN]; /* AIR-3 v1 frame of the winning copy (RX-4: first valid wins) */
	uint8_t flags;
	uint8_t epoch; /* lock count: increments on every (re-)lock, seq restarts are not losses */
	int8_t rssi;   /* dBm of the winning copy, 0 when none */
	uint8_t ant;   /* antenna used: bit 0 copy A window, bit 1 copy B window */
};

int op_rx_start(void);     /* net core */
int op_rx_app_start(void); /* app core */
/* App core: XSMT_EN high now if audio_ok, relay OUT_EN CONFIG_OP_RX_OUT_EN_DELAY_MS after boot (ADR-0014, #118). */
int op_rx_out_start(bool audio_ok);
struct op_rx_snap;
void op_rx_app_snapshot(struct op_rx_snap *n); /* app core: counters for `status` / `stats` (fw/src/proto) */
int op_rx_app_td(void);    /* app core: 1 if the last frame came from a time-diversity pack */

/* RX-1 SPDT antenna switch. Weak no-op until the hw/rx board fixes the GPIO; bsim has one antenna. */
void op_rx_ant_select(uint8_t ant);

/* RX-5 antenna choice, pure C (unit tested in fw/tests/rx_ant). Channel 0 = A, 1 = B; antenna 0/1. */
struct op_ant {
	uint16_t probe;  /* every probe-th frame one window per channel listens on the other antenna */
	int8_t hyst_db;  /* switch threshold */
	uint8_t cur[2];  /* chosen antenna per channel */
	int8_t last[2][2]; /* last-valid RSSI (dBm) per channel x antenna */
	bool seen[2][2];
	bool ok[2][2];     /* the last window on (channel, antenna) held a valid copy */
	int8_t miss_db;    /* miss-triggered switch (ADR-0021): 0 = off; else other within this many dB */
	uint16_t hold;     /* after a miss-triggered switch, windows before the RSSI rule may switch back */
	uint16_t hold_left[2];
	uint32_t switches;
};

void op_ant_init(struct op_ant *s, uint16_t probe_frames, int8_t hyst_db);
/* ADR-0021: on a missed window on the current antenna, switch at once if the other antenna's last window on that
 * channel was valid and its RSSI is no more than miss_db below; then hold it hold_frames windows against the RSSI
 * rule, so an intermittently blocked stronger antenna (a hot 3 MHz neighbour) does not win it straight back. */
void op_ant_set_miss(struct op_ant *s, int8_t miss_db, uint16_t hold_frames);
uint8_t op_ant_pick(const struct op_ant *s, uint8_t ch, uint32_t frame);
/* A window on (ch, ant) ended: rssi of a CRC-valid copy, or valid = false. Returns true on a switch. */
bool op_ant_report(struct op_ant *s, uint8_t ch, uint8_t ant, bool valid, int8_t rssi_dbm);
