#include <zephyr/kernel.h>

int main(void)
{
	for (int i = 0; i < 30; i++) {
		printk("PROBE_UART_OK %d\n", i);
		k_msleep(100);
	}
	return 0;
}
