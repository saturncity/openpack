/* Skeleton: log the role and core. Radio, codec, audio arrive in later tickets. */
#include <zephyr/kernel.h>

#define ROLE (IS_ENABLED(CONFIG_OP_ROLE_PACK) ? "pack" : "rx")
#define CORE (IS_ENABLED(CONFIG_SOC_NRF5340_CPUNET) ? "net" : IS_ENABLED(CONFIG_SOC_NRF5340_CPUAPP) ? "app" : "host")

int main(void)
{
	printk("OpenPack role=%s core=%s t_gap_us=%d dac_block=%d rx_window_us=%d\n", ROLE, CORE,
	       CONFIG_OP_T_GAP_US, CONFIG_OP_DAC_BLOCK_SAMPLES, CONFIG_OP_RX_WINDOW_US);
	return 0;
}
