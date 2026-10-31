/* Writes straight to uart0 (not the console): the bsim UART model forwards it to a host pty. */
#include <zephyr/kernel.h>
#include <zephyr/drivers/uart.h>
#include <stdio.h>

int main(void)
{
	const struct device *u = DEVICE_DT_GET(DT_NODELABEL(uart0));
	char line[32];

	printk("PROBE_UART ready=%d\n", device_is_ready(u));
	for (int i = 0; i < 30; i++) {
		int n = snprintf(line, sizeof(line), "PROBE_UART_OK %d\n", i);

		for (int j = 0; j < n; j++) {
			uart_poll_out(u, line[j]);
		}
		k_msleep(100);
	}
	return 0;
}
