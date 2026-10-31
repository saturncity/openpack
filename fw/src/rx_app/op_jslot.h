/* Receiver jitter slot (RX-7, ADR-0013): decoded frames from the merge wait here for the DAC.
 * Pure C, no Zephyr deps (unit tested in fw/tests/rx_clk).
 *
 * Samples carry absolute indices: sample i plays when the DAC's played count reaches i. When a
 * frame arrives, fill = written - played (Q16) is measured before the frame is written; the
 * slot keeps that at `target` samples (the latency it adds) via the PI loop (op_clk.h) and has
 * one frame of headroom above the post-write level, so `max` = target + 2 frames.
 * Slips: underrun = the DAC reached a sample that was never written (fill < 0 at arrival);
 * overrun = writing the frame would exceed `max`. Either one re-primes the slot to `target`.
 */
#pragma once
#include <stdbool.h>
#include <stdint.h>

#define OP_JSLOT_FRAME 48  /* samples per frame (AIR-3, 1 ms at 48 kHz) */
#define OP_JSLOT_RING  256 /* storage, power of 2, >= max + one drain period */

struct op_jslot {
	int16_t ring[OP_JSLOT_RING];
	uint64_t wr; /* index of the next sample to write */
	uint64_t rd; /* index of the next sample to hand to the DAC */
	uint16_t target, max;
	bool primed;
	uint32_t under, over, primes;
};

void op_jslot_init(struct op_jslot *s, uint16_t target, uint16_t max);
/* New lock epoch: the next arrival re-primes (not a slip). */
void op_jslot_unprime(struct op_jslot *s);
/* A frame arrived, DAC position played_q16. Returns fill - target (Q16) for the PI loop, 0 when
 * the slot (re-)primed. *fill_q16 (optional) gets the measured fill before any re-prime. */
int32_t op_jslot_arrive(struct op_jslot *s, uint64_t played_q16, int32_t *fill_q16);
/* Write the frame announced by the last op_jslot_arrive. */
void op_jslot_write(struct op_jslot *s, const int16_t pcm[OP_JSLOT_FRAME]);
/* Hand every whole block of n samples the DAC has reached (index < played) to out(); samples
 * never written play as 0. Returns the number of blocks. */
uint32_t op_jslot_drain(struct op_jslot *s, uint64_t played_q16, uint16_t n,
			void (*out)(const int16_t *blk, uint16_t n, void *ctx), void *ctx);
