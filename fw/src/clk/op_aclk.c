/* RX-7 audio clock HAL, nRF5340 app core (DK and bsim), ADR-0013.
 *
 * Correction: HFCLKAUDIO.FREQUENCY = nominal 12.288 MHz value + steps (DK: tunes the I2S MCK; bsim:
 * the register exists in the model but drives nothing). Played count: until the I2S backend lands
 * (op_audio_i2s.c is a stub) and on bsim, a software DAC clock: TIMER2 free-runs at 1 MHz from the
 * device's own crystal (bsim -xo_drift applies), and the DAC plays 48 samples/ms scaled by the
 * applied correction. On silicon the I2S sample counter (TXPTRUPD count x block) replaces it.
 */
#include <zephyr/kernel.h>
#include <hal/nrf_timer.h>
#include <hal/nrf_clock.h>
#include "op_clk.h"

#define TMR          NRF_TIMER2
#define CC_NOW       NRF_TIMER_CC_CHANNEL0
#define FREQ_NOMINAL 39846 /* (4 + v / 2^16) * 32 MHz / 12 = 12.288 MHz */
#define FRAC_BITS    40
/* 48 samples per 1000 us, Q40 per us, rounded: 0.048 * 2^40 */
#define RATE_Q40     52776558133LL

static uint32_t last_us;
static uint64_t played_int, played_frac; /* samples, and Q40 fraction */
static int64_t rate_q40 = RATE_Q40;
static int32_t applied;
static struct k_spinlock lock;

static uint32_t now_us(void)
{
	nrf_timer_task_trigger(TMR, nrf_timer_capture_task_get(CC_NOW));
	return nrf_timer_cc_get(TMR, CC_NOW);
}

static void advance(void)
{
	uint32_t t = now_us();
	uint64_t x = played_frac + (uint64_t)(t - last_us) * (uint64_t)rate_q40;

	last_us = t;
	played_int += x >> FRAC_BITS;
	played_frac = x & ((1ULL << FRAC_BITS) - 1);
}

int op_aclk_start(void)
{
	nrf_timer_mode_set(TMR, NRF_TIMER_MODE_TIMER);
	nrf_timer_bit_width_set(TMR, NRF_TIMER_BIT_WIDTH_32);
	nrf_timer_prescaler_set(TMR, NRF_TIMER_FREQ_1MHz);
	nrf_timer_task_trigger(TMR, NRF_TIMER_TASK_CLEAR);
	nrf_timer_task_trigger(TMR, NRF_TIMER_TASK_START);
	last_us = now_us();
	played_int = played_frac = 0;
	applied = 0;
	rate_q40 = RATE_Q40;
#if NRF_CLOCK_HAS_HFCLKAUDIO
	nrf_clock_hfclkaudio_config_set(NRF_CLOCK, FREQ_NOMINAL);
#endif
	return 0;
}

int32_t op_aclk_set_ppb(int32_t ppb)
{
	int32_t steps;
	int32_t q = op_aclk_quant(ppb, &steps);
	k_spinlock_key_t key = k_spin_lock(&lock);

	if (q != applied) {
		advance();
		applied = q;
		rate_q40 = RATE_Q40 + RATE_Q40 / 1000000 * q / 1000;
#if NRF_CLOCK_HAS_HFCLKAUDIO
		nrf_clock_hfclkaudio_config_set(NRF_CLOCK, (uint16_t)(FREQ_NOMINAL + steps));
#endif
	}
	k_spin_unlock(&lock, key);
	return q;
}

uint64_t op_aclk_played_q16(void)
{
	k_spinlock_key_t key = k_spin_lock(&lock);
	uint64_t p;

	advance();
	p = (played_int << 16) | (played_frac >> (FRAC_BITS - 16));
	k_spin_unlock(&lock, key);
	return p;
}
