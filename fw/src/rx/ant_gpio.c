/* RX-5 antenna switch pin (#118): the PE4259 CTRL on ANT_SEL, a net-core GPIO (ADR-0014: P1.01, low = antenna A).
 * The pin comes from the board's net-core zephyr,user ant-sel-gpios (generated from the netlist) and is handed to
 * the net core by the app core's gpio_fwd node. Called from the radio interrupt for every window (rx.c listen()),
 * so it writes OUT directly. Without the property (DK, bsim) rx.c's weak no-op stays.
 */
#include <zephyr/kernel.h>
#include <zephyr/init.h>
#include <zephyr/devicetree.h>
#include <zephyr/drivers/gpio.h>
#include "op_rx.h"

#if DT_NODE_HAS_PROP(DT_PATH(zephyr_user), ant_sel_gpios)
#include <hal/nrf_gpio.h>

#define ANT_PSEL NRF_DT_GPIOS_TO_PSEL(DT_PATH(zephyr_user), ant_sel_gpios)
BUILD_ASSERT(!(DT_GPIO_FLAGS(DT_PATH(zephyr_user), ant_sel_gpios) & GPIO_ACTIVE_LOW),
	     "ANT_SEL is active high: low = antenna A (ADR-0014)");

void op_rx_ant_select(uint8_t ant)
{
	nrf_gpio_pin_write(ANT_PSEL, ant);
}

static int ant_gpio_init(void)
{
	nrf_gpio_pin_clear(ANT_PSEL); /* antenna A until the first window */
	nrf_gpio_cfg_output(ANT_PSEL);
	return 0;
}

SYS_INIT(ant_gpio_init, POST_KERNEL, 0);
#endif
