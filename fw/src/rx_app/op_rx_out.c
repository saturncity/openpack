/* Receiver output un-mute order (ADR-0014, #118). At boot both XSMT_EN (PCM5102A soft mute) and OUT_EN (relay K1)
 * are low: the board's pull-downs already hold them there through reset. Once the I2S clocks run, XSMT goes high;
 * CONFIG_OP_RX_OUT_EN_DELAY_MS after boot (>= 5 s, VCM settled) OUT_EN closes the relay. Without I2S nothing is
 * un-muted. The +12 V supervisor overrides both in hardware. Pins: zephyr,user xsmt-gpios / out-en-gpios (generated
 * from the netlist). Boards without them (DK, bsim) build the no-op.
 */
#include <zephyr/kernel.h>
#include <zephyr/devicetree.h>
#include <zephyr/drivers/gpio.h>
#include "op_rx.h"

#define USER DT_PATH(zephyr_user)

#if DT_NODE_HAS_PROP(USER, xsmt_gpios) && DT_NODE_HAS_PROP(USER, out_en_gpios)
static const struct gpio_dt_spec xsmt = GPIO_DT_SPEC_GET(USER, xsmt_gpios);
static const struct gpio_dt_spec out_en = GPIO_DT_SPEC_GET(USER, out_en_gpios);
static bool unmuted;

static void out_en_work(struct k_work *w)
{
	ARG_UNUSED(w);
	if (unmuted) { /* only after the DAC is un-muted */
		(void)gpio_pin_set_dt(&out_en, 1);
		printk("RXAPP_OUT relay closed at %u ms\n", (uint32_t)k_uptime_get());
	}
}

static K_WORK_DELAYABLE_DEFINE(out_work, out_en_work);

int op_rx_out_start(bool audio_ok)
{
	int err = gpio_pin_configure_dt(&out_en, GPIO_OUTPUT_INACTIVE);

	err = err ? err : gpio_pin_configure_dt(&xsmt, GPIO_OUTPUT_INACTIVE);
	if (err != 0 || !audio_ok) {
		return err;
	}
	err = gpio_pin_set_dt(&xsmt, 1);
	unmuted = err == 0;
	if (unmuted) {
		int64_t left = CONFIG_OP_RX_OUT_EN_DELAY_MS - k_uptime_get();

		(void)k_work_schedule(&out_work, K_MSEC(left > 0 ? left : 0));
	}
	return err;
}
#else
int op_rx_out_start(bool audio_ok)
{
	ARG_UNUSED(audio_ok);
	return 0;
}
#endif
