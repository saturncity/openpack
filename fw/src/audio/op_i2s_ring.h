/* Receiver DAC FIFO between the jitter slot's drain (thread, OP_AUDIO_BLOCK_SAMPLES per write_block) and the I2S
 * TXPTRUPD interrupt (one DMA block per call), #118. Single producer, single consumer, no lock.
 *
 * The consumer outputs zeros until `prime` samples are queued (so the first DMA blocks never underrun mid-block), and
 * again after an underrun until the FIFO is primed again: an underrun is a discontinuity either way, and re-priming
 * turns a stutter of tiny gaps into one gap. An overrun drops the newest samples (the jitter slot's PI loop keeps the
 * fill near its target; a drop here means the DAC clock stopped). Counters are cumulative samples.
 * Pure C (unit tested on native_sim, fw/tests/i2s_ring).
 */
#ifndef OP_I2S_RING_H
#define OP_I2S_RING_H

#include <stdbool.h>
#include <stdint.h>

#define OP_I2S_RING_CAP 128 /* samples, power of 2: 2.7 ms at 48 kHz */

struct op_i2s_ring {
	int16_t s[OP_I2S_RING_CAP];
	uint32_t w, r;         /* free-running sample indices; w written by the producer, r by the consumer */
	uint32_t prime;        /* samples queued before output starts */
	bool primed;           /* consumer side */
	uint32_t under, over;  /* samples missing when the FIFO ran dry while playing / samples dropped when full */
	uint32_t out;          /* samples handed to the DAC (zeros included) */
};

void op_i2s_ring_init(struct op_i2s_ring *q, uint32_t prime);
/* Producer: queue n samples. Returns the number dropped (FIFO full). */
uint32_t op_i2s_ring_put(struct op_i2s_ring *q, const int16_t *s, uint32_t n);
/* Consumer: fill dst with n samples, zeros where none are queued (or while priming). */
void op_i2s_ring_get(struct op_i2s_ring *q, int16_t *dst, uint32_t n);
uint32_t op_i2s_ring_fill(const struct op_i2s_ring *q);

#endif /* OP_I2S_RING_H */
