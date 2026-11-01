/* Pack battery monitor, app core (PK-8, ADR-0012, #118). Reads the cell through the board's `vbat` voltage-divider
 * node (SAADC channel + R12/R13 ratio, both generated from the netlist), drives the battery LEDs, and below 3.3 V
 * under load puts the PCM1840 into shutdown, turns the LEDs off and enters System OFF. The slide switch (power
 * cycle) is the only way back. Note: System OFF stops the SoC only; the 5 V boost and both LDOs stay on until the
 * switch is turned off or the cell's protection opens (the board has no firmware-controlled power latch).
 */
#include <zephyr/kernel.h>
#include <zephyr/devicetree.h>
#include <zephyr/drivers/adc.h>
#include <zephyr/drivers/adc/voltage_divider.h>
#include <zephyr/drivers/gpio.h>
#include <zephyr/sys/poweroff.h>
#include "op_batt.h"
#include "op_audio.h"

#define VBAT DT_NODELABEL(vbat)

static const struct voltage_divider_dt_spec div = VOLTAGE_DIVIDER_DT_SPEC_GET(VBAT);
static const struct gpio_dt_spec led_ok = GPIO_DT_SPEC_GET(DT_NODELABEL(led_bat_ok), gpios);
static const struct gpio_dt_spec led_low = GPIO_DT_SPEC_GET(DT_NODELABEL(led_bat_low), gpios);
static struct op_batt mon;
static int16_t raw;
static struct adc_sequence seq = {.buffer = &raw, .buffer_size = sizeof(raw)};

static int sample_mv(int32_t *cell_mv)
{
	int32_t mv;
	int err = adc_read_dt(&div.port, &seq);

	if (err != 0) {
		return err;
	}
	mv = raw;
	err = adc_raw_to_millivolts_dt(&div.port, &mv);
	if (err == 0) {
		*cell_mv = op_batt_cell_mv(mv, div.full_ohms, div.output_ohms);
	}
	return err;
}

static void cutoff(int32_t mv)
{
	printk("BATT cutoff %d mV < %d mV: power off\n", mv, CONFIG_OP_BATT_CUTOFF_MV);
	if (IS_ENABLED(CONFIG_OP_AUDIO_I2S)) {
		op_audio_i2s_stop();
	}
	(void)gpio_pin_set_dt(&led_ok, 0);
	(void)gpio_pin_set_dt(&led_low, 0);
	k_msleep(10); /* let the console drain */
	sys_poweroff();
}

static void tick(struct k_work *w);
static K_WORK_DELAYABLE_DEFINE(work, tick);

static void tick(struct k_work *w)
{
	int32_t mv;

	ARG_UNUSED(w);
	if (sample_mv(&mv) == 0) {
		enum op_batt_state st = op_batt_update(&mon, mv);

		if (st == OP_BATT_CUTOFF) {
			cutoff(mv);
		}
		(void)gpio_pin_set_dt(&led_ok, st == OP_BATT_OK);
		(void)gpio_pin_set_dt(&led_low, st == OP_BATT_LOW);
	}
	(void)k_work_schedule(&work, K_MSEC(CONFIG_OP_BATT_PERIOD_MS));
}

int op_batt_start(void)
{
	int err;

	if (!adc_is_ready_dt(&div.port)) {
		return -ENODEV;
	}
	err = adc_channel_setup_dt(&div.port);
	err = err ? err : adc_sequence_init_dt(&div.port, &seq);
	err = err ? err : gpio_pin_configure_dt(&led_ok, GPIO_OUTPUT_INACTIVE);
	err = err ? err : gpio_pin_configure_dt(&led_low, GPIO_OUTPUT_INACTIVE);
	if (err != 0) {
		return err;
	}
	op_batt_init(&mon, CONFIG_OP_BATT_LOW_MV, CONFIG_OP_BATT_CUTOFF_MV, CONFIG_OP_BATT_HYST_MV,
		     CONFIG_OP_BATT_CUTOFF_SAMPLES);
	printk("BATT_CFG divider %u/%u ohm, low %d mV, cutoff %d mV x%d\n", div.full_ohms, div.output_ohms,
	       CONFIG_OP_BATT_LOW_MV, CONFIG_OP_BATT_CUTOFF_MV, CONFIG_OP_BATT_CUTOFF_SAMPLES);
	tick(NULL);
	return 0;
}
