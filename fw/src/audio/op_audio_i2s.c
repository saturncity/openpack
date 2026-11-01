/* I2S backend (FW-3), nRF5340 app core.
 *
 * Pack (#97): PCM1840 capture and the audio frame clock. I2S0 is master (the PCM1840 is a slave,
 * ADR-0012), clocked from HFCLKAUDIO (ACLK, bypass): MCK = 12.288 MHz, LRCK = MCK / 256 = 48 kHz,
 * 16-bit left channel, 48-sample (1 ms) double buffers. RXPTRUPD fires when the hardware has
 * latched the next buffer pointer, i.e. once per 48 samples: from the second one on, each marks one
 * completed frame, and that is the frame clock (frame_cb, from the I2S interrupt). The rate is
 * steered in whole HFCLKAUDIO.FREQUENCY steps (op_audio_i2s_aclk_steps, 3311 ppb each).
 * Pins (ADR-0012): BCLK P0.24, FSYNC P0.23, SDIN P0.20.
 * Bring-up on the DK and the pack is Phase 5; bsim has no I2S or HFCLKAUDIO model (WAV backend).
 *
 * Receiver: DAC output (write_block) is still a stub until Phase 5.
 */
#include <errno.h>
#include <string.h>
#include <zephyr/kernel.h>
#include <zephyr/irq.h>
#include "op_audio.h"

#if defined(CONFIG_OP_ROLE_PACK) && defined(CONFIG_SOC_COMPATIBLE_NRF5340_CPUAPP)
#include <hal/nrf_i2s.h>
#include <hal/nrf_clock.h>

#define I2S          NRF_I2S0
#define PIN_SCK      24 /* P0.24 */
#define PIN_LRCK     23 /* P0.23 */
#define PIN_SDIN     20 /* P0.20 */
#define FREQ_NOMINAL 39846 /* (4 + v / 2^16) * 32 MHz / 12 = 12.288 MHz + 0.371 ppm */
#define WORDS        (OP_AUDIO_FRAME_SAMPLES / 2) /* 16-bit mono: 2 samples per RX word */

static uint32_t buf[2][WORDS];
static volatile const uint32_t *done;
static uint32_t nptr;
static void (*frame_cb)(void);
static uint16_t freq = FREQ_NOMINAL;

static void i2s_isr(const void *arg)
{
	if (!nrf_i2s_event_check(I2S, NRF_I2S_EVENT_RXPTRUPD)) {
		return;
	}
	nrf_i2s_event_clear(I2S, NRF_I2S_EVENT_RXPTRUPD);
	/* 1st: buf[0] latched, being filled. nth (n >= 2): buf[(n - 1) & 1] latched, buf[n & 1] done. */
	if (++nptr == 1) {
		nrf_i2s_rx_buffer_set(I2S, buf[1]);
		return;
	}
	done = buf[nptr & 1];
	nrf_i2s_rx_buffer_set(I2S, buf[nptr & 1]); /* refilled from the next RXPTRUPD on, 1 ms away */
	if (frame_cb != NULL) {
		frame_cb();
	}
}

int op_audio_start(void)
{
	const nrf_i2s_config_t cfg = {
		.mode = NRF_I2S_MODE_MASTER,
		.format = NRF_I2S_FORMAT_I2S,
		.alignment = NRF_I2S_ALIGN_LEFT,
		.sample_width = NRF_I2S_SWIDTH_16BIT,
		.channels = NRF_I2S_CHANNELS_LEFT,
		.mck_setup = NRF_I2S_MCK_32MDIV8, /* enables the MCK generator; bypassed to ACLK below */
		.ratio = NRF_I2S_RATIO_256X,
	};
	const nrf_i2s_pins_t pins = {
		.sck_pin = PIN_SCK,
		.lrck_pin = PIN_LRCK,
		.mck_pin = NRF_I2S_PIN_NOT_CONNECTED,
		.sdout_pin = NRF_I2S_PIN_NOT_CONNECTED,
		.sdin_pin = PIN_SDIN,
	};

	nrf_clock_hfclkaudio_config_set(NRF_CLOCK, freq);
	nrf_clock_task_trigger(NRF_CLOCK, NRF_CLOCK_TASK_HFCLKAUDIOSTART);
	for (int i = 0; i < 1000 && !nrf_clock_is_running(NRF_CLOCK, NRF_CLOCK_DOMAIN_HFCLKAUDIO, NULL);
	     i++) {
		k_busy_wait(10);
	}
	if (!nrf_clock_is_running(NRF_CLOCK, NRF_CLOCK_DOMAIN_HFCLKAUDIO, NULL)) {
		return -EIO;
	}
	nrf_i2s_pins_set(I2S, &pins);
	nrf_i2s_configure(I2S, &cfg);
	nrf_i2s_clk_configure(I2S, NRF_I2S_CLKSRC_ACLK, true);
	nrf_i2s_transfer_set(I2S, WORDS, buf[0], NULL);
	nrf_i2s_event_clear(I2S, NRF_I2S_EVENT_RXPTRUPD);
	nrf_i2s_int_enable(I2S, NRF_I2S_INT_RXPTRUPD_MASK);
	IRQ_CONNECT(I2S0_IRQn, 1, i2s_isr, NULL, 0);
	irq_enable(I2S0_IRQn);
	nrf_i2s_enable(I2S);
	return 0;
}

int op_audio_i2s_rx_start(void (*cb)(void))
{
	frame_cb = cb;
	nrf_i2s_task_trigger(I2S, NRF_I2S_TASK_START);
	return 0;
}

void op_audio_i2s_aclk_steps(int32_t steps)
{
	uint16_t f = (uint16_t)(FREQ_NOMINAL + steps);

	if (f != freq) {
		freq = f;
		nrf_clock_hfclkaudio_config_set(NRF_CLOCK, f);
	}
}

int op_audio_read_frame(int16_t *frame)
{
	const volatile uint32_t *d = done;

	if (d == NULL) {
		return -ENODATA;
	}
	memcpy(frame, (const void *)d, OP_AUDIO_FRAME_SAMPLES * sizeof(int16_t));
	return 0;
}

int op_audio_write_block(const int16_t *block)
{
	(void)block;
	return -ENOTSUP;
}

#else /* receiver (DAC output lands in Phase 5), net core (no I2S) */

int op_audio_start(void) { return -ENOTSUP; }
int op_audio_read_frame(int16_t *frame) { (void)frame; return -ENOTSUP; }
int op_audio_write_block(const int16_t *block) { (void)block; return -ENOTSUP; }

#endif
