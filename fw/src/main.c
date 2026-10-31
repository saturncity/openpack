/* OpenPack: role (FW-1) x core (FW-2). Pack: app core sources frames, net core schedules them on air. */
#include <zephyr/kernel.h>
#include "op_frame.h"
#include "op_rx.h"

#define ROLE (IS_ENABLED(CONFIG_OP_ROLE_PACK) ? "pack" : "rx")
#define NET  IS_ENABLED(CONFIG_SOC_COMPATIBLE_NRF5340_CPUNET)
#define CORE (NET ? "net" : IS_ENABLED(CONFIG_SOC_COMPATIBLE_NRF5340_CPUAPP) ? "app" : "host")

int main(void)
{
	printk("OpenPack role=%s core=%s t_gap_us=%d dac_block=%d rx_window_us=%d\n", ROLE, CORE,
	       CONFIG_OP_T_GAP_US, CONFIG_OP_DAC_BLOCK_SAMPLES, CONFIG_OP_RX_WINDOW_US);
#if defined(CONFIG_OP_NRF5340) && defined(CONFIG_OP_ROLE_PACK)
	int err;

	if (NET) {
		err = op_sched_start();
		if (err == 0) {
			err = op_ipc_init(op_sched_put);
		}
	} else {
		err = op_ipc_init(NULL);
		if (err == 0) {
			err = op_framesrc_start();
		}
	}
	printk("OpenPack %s pipeline %s (%d)\n", CORE, err ? "FAILED" : "up", err);
#elif defined(CONFIG_OP_NRF5340) && defined(CONFIG_OP_ROLE_RX)
	int err = NET ? op_ipc_init(NULL) : op_rx_app_start();

	err = (err == 0 && NET) ? op_rx_start() : err;
	printk("OpenPack %s rx pipeline %s (%d)\n", CORE, err ? "FAILED" : "up", err);
#endif
	return 0;
}
