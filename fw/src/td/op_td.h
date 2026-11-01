/* Time diversity (TD, AIR-3 / RX-4, ADR-0017): packet n also carries frame n-2's codec_state + audio
 * (td_audio, 39 B), so a frame whose two copies both failed is recovered from packet n+2.
 * Pure C, no Zephyr deps (unit tested in fw/tests/td).
 *
 * Pack: op_td_tx() turns each 42 B v1 frame into the on-air payload, 42 B (TD off) or 81 B (TD on).
 * Receiver: op_td_rx() is a two-packet delay line run at the RX-4 deadline of every packet k. It outputs
 * frame k-2: from packet k-2 if a copy was valid, else from packet k's td_audio, else lost (PLC). The
 * output is 2 frames (2000 us) later than TD off, for TD packs only.
 */
#pragma once
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include "op_frame.h"

#define OP_TD_HDR 3  /* AIR-3 seq u8 + status u16, not repeated in td_audio */
#define OP_TD_LEN (OP_FRAME_LEN - OP_TD_HDR) /* 39: codec_state 3 B + audio 36 B of frame n-2 */
#define OP_TD_D   2  /* offset: td_audio of packet n is frame n-2 */
#define OP_FRAME_TD_LEN (OP_FRAME_LEN + OP_TD_LEN) /* 81 B TD payload */
_Static_assert(OP_FRAME_TD_LEN == OP_PAYLOAD_MAX, "AIR-3: 81 B TD payload");

struct op_td_tx {
	uint8_t hist[OP_TD_D][OP_TD_LEN]; /* td_audio of the last OP_TD_D frames, zero before that */
	uint8_t i;
};

void op_td_tx_init(struct op_td_tx *s);
/* Frame n (42 B) -> payload in out: frame n, then (on) frame n-2's td_audio. Returns 42 or 81. The history
 * runs whether TD is on or not, so turning it on never sends stale audio. */
size_t op_td_tx(struct op_td_tx *s, const uint8_t frame[OP_FRAME_LEN], bool on, uint8_t out[OP_FRAME_TD_LEN]);

enum op_td_res {
	OP_TD_NONE, /* fewer than OP_TD_D packets since reset: nothing to play yet */
	OP_TD_OK,   /* frame k-2 from its own packet */
	OP_TD_REC,  /* frame k-2 recovered from packet k's td_audio (RX-4) */
	OP_TD_LOST, /* both packets lost: PLC */
};

struct op_td_rx {
	uint8_t pkt[OP_TD_D][OP_FRAME_TD_LEN];
	uint16_t tag[OP_TD_D]; /* caller data per packet (copy flags, RSSI), handed back with its frame */
	bool ok[OP_TD_D];
	uint8_t i, n;
};

void op_td_rx_init(struct op_td_rx *s);
/* Packet k at its deadline: pkt = 81 B payload of a valid copy, or NULL. Writes frame k-2 (42 B) to out
 * and the tag given with packet k-2 to *tag_out. The recovered frame's seq is packet k's seq - 2. */
enum op_td_res op_td_rx(struct op_td_rx *s, const uint8_t *pkt, uint16_t tag, uint8_t out[OP_FRAME_LEN],
			uint16_t *tag_out);
