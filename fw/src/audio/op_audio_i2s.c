/* I2S backend (FW-3), nRF5340 app core. I2S0 is master, clocked from HFCLKAUDIO (ACLK, bypass): MCK = 12.288 MHz,
 * LRCK = MCK / 256 = 48 kHz, 16-bit samples in the left slot (BCK = 32 fs), two 16-bit samples per 32-bit DMA word.
 *
 * Pins: the board's i2s0 pinctrl (openpack_pack / openpack_rx, generated from the netlist, #118). The DK has none and
 * uses the board pins of its role: pack ADR-0012 (BCLK P0.24, FSYNC P0.23, SDIN P0.20), receiver ADR-0014 (BCK P0.24,
 * LRCK P0.23, SDOUT P0.13).
 *
 * Pack (#97): PCM1840 capture and the audio frame clock. 48-sample (1 ms) double buffers. RXPTRUPD fires when the
 * hardware has latched the next buffer pointer, i.e. once per 48 samples: from the second one on, each marks one
 * completed frame, and that is the frame clock (frame_cb, from the I2S interrupt). The rate is steered in whole
 * HFCLKAUDIO.FREQUENCY steps (op_audio_i2s_aclk_steps, 3311 ppb each). The PCM1840 leaves shutdown (SHDNZ high) once
 * HFCLKAUDIO runs; its 10 uF input caps settle in about 0.1 s (ADR-0012 item 9).
 *
 * Receiver (#118): PCM5102A output (3-wire, BCK PLL: no MCK pin). write_block queues OP_AUDIO_BLOCK_SAMPLES into a
 * FIFO (op_i2s_ring.c); TXPTRUPD, once per DMA block of the same size, refills the next DMA buffer from it. The rate is
 * HFCLKAUDIO, steered by op_aclk.c (RX-7). op_aclk's played count is still its TIMER2 model of this clock (ADR-0013);
 * op_audio_i2s_tx_out() is the hardware count for the Phase 5 switch-over.
 * Bring-up on silicon is Phase 5; bsim has no I2S or HFCLKAUDIO model (WAV backend).
 */
#include <errno.h>
#include <string.h>
#include <zephyr/kernel.h>
#include <zephyr/irq.h>
#include <zephyr/devicetree.h>
#include "op_audio.h"

#if defined(CONFIG_SOC_COMPATIBLE_NRF5340_CPUAPP)
#include <hal/nrf_i2s.h>
#include <hal/nrf_clock.h>
#include <zephyr/drivers/gpio.h>
#include <zephyr/drivers/pinctrl.h>

#define I2S          NRF_I2S0
#define I2S_NODE     DT_NODELABEL(i2s0)
#define USER_NODE    DT_PATH(zephyr_user)
#define FREQ_NOMINAL 39846 /* (4 + v / 2^16) * 32 MHz / 12 = 12.288 MHz + 0.371 ppm */

#if DT_NODE_HAS_PROP(I2S_NODE, pinctrl_0)
PINCTRL_DT_DEFINE(I2S_NODE);
#endif

static uint16_t freq = FREQ_NOMINAL;

static int aclk_start(void)
{
	nrf_clock_hfclkaudio_config_set(NRF_CLOCK, freq);
	nrf_clock_task_trigger(NRF_CLOCK, NRF_CLOCK_TASK_HFCLKAUDIOSTART);
	for (int i = 0; i < 1000 && !nrf_clock_is_running(NRF_CLOCK, NRF_CLOCK_DOMAIN_HFCLKAUDIO, NULL); i++) {
		k_busy_wait(10);
	}
	return nrf_clock_is_running(NRF_CLOCK, NRF_CLOCK_DOMAIN_HFCLKAUDIO, NULL) ? 0 : -EIO;
}

/* Pins from the board's pinctrl, else the DK fallback. */
static int pins_apply(uint32_t sck, uint32_t lrck, uint32_t sdout, uint32_t sdin)
{
#if DT_NODE_HAS_PROP(I2S_NODE, pinctrl_0)
	ARG_UNUSED(sck); ARG_UNUSED(lrck); ARG_UNUSED(sdout); ARG_UNUSED(sdin);
	return pinctrl_apply_state(PINCTRL_DT_DEV_CONFIG_GET(I2S_NODE), PINCTRL_STATE_DEFAULT);
#else
	const nrf_i2s_pins_t pins = {
		.sck_pin = sck,
		.lrck_pin = lrck,
		.mck_pin = NRF_I2S_PIN_NOT_CONNECTED,
		.sdout_pin = sdout,
		.sdin_pin = sdin,
	};

	nrf_i2s_pins_set(I2S, &pins);
	return 0;
#endif
}

static void i2s_configure(void)
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

	nrf_i2s_configure(I2S, &cfg);
	nrf_i2s_clk_configure(I2S, NRF_I2S_CLKSRC_ACLK, true);
}

void op_audio_i2s_aclk_steps(int32_t steps)
{
	uint16_t f = (uint16_t)(FREQ_NOMINAL + steps);

	if (f != freq) {
		freq = f;
		nrf_clock_hfclkaudio_config_set(NRF_CLOCK, f);
	}
}
#endif /* CPUAPP */

#if defined(CONFIG_OP_ROLE_PACK) && defined(CONFIG_SOC_COMPATIBLE_NRF5340_CPUAPP)

#define WORDS (OP_AUDIO_FRAME_SAMPLES / 2) /* 16-bit mono: 2 samples per RX word */

static uint32_t buf[2][WORDS];
static volatile const uint32_t *done;
static uint32_t nptr;
static void (*frame_cb)(void);

#if DT_NODE_HAS_PROP(USER_NODE, shdnz_gpios)
static const struct gpio_dt_spec shdnz = GPIO_DT_SPEC_GET(USER_NODE, shdnz_gpios);
#endif

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
	int err = aclk_start();

	if (err == 0) {
		err = pins_apply(24, 23, NRF_I2S_PIN_NOT_CONNECTED, 20); /* DK fallback: ADR-0012 */
	}
	if (err != 0) {
		return err;
	}
#if DT_NODE_HAS_PROP(USER_NODE, shdnz_gpios)
	err = gpio_pin_configure_dt(&shdnz, GPIO_OUTPUT_ACTIVE); /* PCM1840 out of shutdown: clocks are running */
	if (err != 0) {
		return err;
	}
#endif
	i2s_configure();
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

void op_audio_i2s_stop(void)
{
	nrf_i2s_task_trigger(I2S, NRF_I2S_TASK_STOP);
#if DT_NODE_HAS_PROP(USER_NODE, shdnz_gpios)
	(void)gpio_pin_set_dt(&shdnz, 0); /* PCM1840 back into shutdown */
#endif
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

#elif defined(CONFIG_OP_ROLE_RX) && defined(CONFIG_SOC_COMPATIBLE_NRF5340_CPUAPP)
#include "op_i2s_ring.h"

#define BLK   OP_AUDIO_BLOCK_SAMPLES
#define WORDS (BLK / 2)
BUILD_ASSERT(BLK % 2 == 0, "16-bit mono I2S packs 2 samples per word: OP_DAC_BLOCK_SAMPLES must be even");
BUILD_ASSERT(2 * BLK <= OP_I2S_RING_CAP, "FIFO holds at least two DMA blocks");

static uint32_t buf[2][WORDS];
static uint32_t nptr;
static struct op_i2s_ring ring;

static void i2s_isr(const void *arg)
{
	if (!nrf_i2s_event_check(I2S, NRF_I2S_EVENT_TXPTRUPD)) {
		return;
	}
	nrf_i2s_event_clear(I2S, NRF_I2S_EVENT_TXPTRUPD);
	/* nth TXPTRUPD: buf[(n - 1) & 1] latched and being sent, so buf[n & 1] is free: refill it and queue it. */
	uint32_t *b = buf[++nptr & 1];

	op_i2s_ring_get(&ring, (int16_t *)b, BLK);
	nrf_i2s_tx_buffer_set(I2S, b);
}

int op_audio_start(void)
{
	int err = aclk_start();

	if (err == 0) {
		err = pins_apply(24, 23, 13, NRF_I2S_PIN_NOT_CONNECTED); /* DK fallback: ADR-0014 */
	}
	if (err != 0) {
		return err;
	}
	op_i2s_ring_init(&ring, 2 * BLK);
	memset(buf, 0, sizeof(buf));
	nptr = 0;
	i2s_configure();
	nrf_i2s_transfer_set(I2S, WORDS, NULL, buf[0]);
	nrf_i2s_event_clear(I2S, NRF_I2S_EVENT_TXPTRUPD);
	nrf_i2s_int_enable(I2S, NRF_I2S_INT_TXPTRUPD_MASK);
	IRQ_CONNECT(I2S0_IRQn, 1, i2s_isr, NULL, 0);
	irq_enable(I2S0_IRQn);
	nrf_i2s_enable(I2S);
	nrf_i2s_task_trigger(I2S, NRF_I2S_TASK_START);
	return 0;
}

int op_audio_read_frame(int16_t *frame)
{
	(void)frame;
	return -ENOTSUP;
}

int op_audio_write_block(const int16_t *block)
{
	return op_i2s_ring_put(&ring, block, BLK) == 0 ? 0 : -ENOBUFS;
}

uint32_t op_audio_i2s_tx_out(void)
{
	return ring.out;
}

#else /* net core (no I2S) */

int op_audio_start(void) { return -ENOTSUP; }
int op_audio_read_frame(int16_t *frame) { (void)frame; return -ENOTSUP; }
int op_audio_write_block(const int16_t *block) { (void)block; return -ENOTSUP; }

#endif
