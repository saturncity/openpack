/* Test only (CONFIG_OP_TEST_APP_LOAD_PERIOD_US > 0, #87): an unrelated app-core thread that wakes
 * every OP_TEST_APP_LOAD_PERIOD_US and busy-works OP_TEST_APP_LOAD_BUSY_US. FW-2: the pack must not
 * skip a frame under any load that leaves the frame thread its deadline (tests/bsim/sched).
 */
#include <zephyr/kernel.h>

static void load(void *a, void *b, void *c)
{
	printk("LOAD period_us=%d busy_us=%d prio=%d\n", CONFIG_OP_TEST_APP_LOAD_PERIOD_US,
	       CONFIG_OP_TEST_APP_LOAD_BUSY_US, CONFIG_OP_TEST_APP_LOAD_PRIO);
	for (;;) {
		k_usleep(CONFIG_OP_TEST_APP_LOAD_PERIOD_US);
		k_busy_wait(CONFIG_OP_TEST_APP_LOAD_BUSY_US);
	}
}

K_THREAD_DEFINE(op_test_load, 1024, load, NULL, NULL, NULL, CONFIG_OP_TEST_APP_LOAD_PRIO, 0, 0);
