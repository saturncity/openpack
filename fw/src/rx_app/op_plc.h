/* RX-6 packet-loss concealment, same rule as sim/loss/plc.py (the model ViSQOL scored):
 * lost frames 1..10 of a run repeat the last good frame, frame 11 repeats it with a 1 ms linear
 * fade to 0, then mute until the next good frame, which plays as is. Pure C (fw/tests/rx_plc).
 */
#pragma once
#include <stdint.h>

#define OP_PLC_N          48
#define OP_PLC_MUTE_AFTER 10 /* frames (10 ms) of repeat before the fade */

struct op_plc {
	int16_t last[OP_PLC_N];
	uint32_t run;       /* current run of lost frames */
	uint32_t concealed; /* lost frames handled, total */
};

void op_plc_init(struct op_plc *p);
/* One frame: in = decoded good frame, or NULL for a lost one. Writes the frame to play. */
void op_plc_frame(struct op_plc *p, const int16_t *in, int16_t out[OP_PLC_N]);
