/* #107: nRF21540 static pins on the BT40NE net core. TX_EN/RX_EN are left low here: the pack's radio TXEN is
 * hardware-timed (sched.c) and a timed TX_EN is AIR-6 work. TODO(#107): without TX_EN the PA is off, so the pack
 * cannot radiate through the FEM until AIR-6 lands; that is a bench-phase item, not a bsim one.
 * ANT_SEL level: see CONFIG_OP_FEM_ANT_SEL_UFL. docs/analysis/module-antenna.md section 4 asks that the port be
 * re-selected after every wake, so this runs at boot and op_fem_init() may be called again after a PDN cycle. */
#include <errno.h>
#include <zephyr/kernel.h>
#include <zephyr/device.h>
#include <zephyr/init.h>
#include <zephyr/drivers/gpio.h>
#include "op_fem.h"

#define FEM DT_NODELABEL(nrf_radio_fem)

static const struct gpio_dt_spec pdn = GPIO_DT_SPEC_GET(FEM, pdn_gpios);
static const struct gpio_dt_spec mode = GPIO_DT_SPEC_GET(FEM, mode_gpios);
static const struct gpio_dt_spec ant_sel = GPIO_DT_SPEC_GET(FEM, ant_sel_gpios);
static const struct gpio_dt_spec tx_en = GPIO_DT_SPEC_GET(FEM, tx_en_gpios);
static const struct gpio_dt_spec rx_en = GPIO_DT_SPEC_GET(FEM, rx_en_gpios);

int op_fem_init(void)
{
	int err = 0;

	err |= gpio_pin_configure_dt(&tx_en, GPIO_OUTPUT_INACTIVE);
	err |= gpio_pin_configure_dt(&rx_en, GPIO_OUTPUT_INACTIVE);
	err |= gpio_pin_configure_dt(&ant_sel, CONFIG_OP_FEM_ANT_SEL_UFL ? GPIO_OUTPUT_ACTIVE : GPIO_OUTPUT_INACTIVE);
	err |= gpio_pin_configure_dt(&mode, GPIO_OUTPUT_ACTIVE); /* POUTB, ~10 dB gain */
	err |= gpio_pin_configure_dt(&pdn, GPIO_OUTPUT_ACTIVE);  /* powered up */
	return err ? -EIO : 0;
}

static int fem_sys_init(void)
{
	return op_fem_init();
}

SYS_INIT(fem_sys_init, POST_KERNEL, CONFIG_KERNEL_INIT_PRIORITY_DEFAULT);
