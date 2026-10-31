/* AIR-1 probe: RADIO MODE=Ble_2Mbit, raw packet config (not BLE link layer), 1 packet/ms.
 * Steps through carriers; each block prints ok/crcerr/timeout on the RX side. Loss = 1 - ok/n. */
#include <zephyr/kernel.h>
#include <nrfx.h>

static const int carriers[] = {2437, 2442, 2424, 2449, 2473}; /* in-band, in-band edge, gap, gap, gap */
#define N CONFIG_PROBE_PACKETS
#define T0_US 10000
static uint8_t pkt[1 + 20];

static void radio_cfg(int mhz)
{
	NRF_RADIO->MODE = RADIO_MODE_MODE_Ble_2Mbit << RADIO_MODE_MODE_Pos;
	NRF_RADIO->PCNF0 = (8 << RADIO_PCNF0_LFLEN_Pos) | (RADIO_PCNF0_PLEN_16bit << RADIO_PCNF0_PLEN_Pos);
	NRF_RADIO->PCNF1 = (32 << RADIO_PCNF1_MAXLEN_Pos) | (3 << RADIO_PCNF1_BALEN_Pos) |
			   (RADIO_PCNF1_ENDIAN_Big << RADIO_PCNF1_ENDIAN_Pos);
	NRF_RADIO->BASE0 = 0xA5C3E100;
	NRF_RADIO->PREFIX0 = 0x8E;
	NRF_RADIO->TXADDRESS = 0;
	NRF_RADIO->RXADDRESSES = 1;
	NRF_RADIO->CRCCNF = RADIO_CRCCNF_LEN_Three << RADIO_CRCCNF_LEN_Pos;
	NRF_RADIO->CRCPOLY = 0x00065B;
	NRF_RADIO->CRCINIT = 0x555555;
	NRF_RADIO->TXPOWER = RADIO_TXPOWER_TXPOWER_0dBm;
	NRF_RADIO->FREQUENCY = mhz - 2400;
	NRF_RADIO->PACKETPTR = (uint32_t)(uintptr_t)pkt;
	NRF_RADIO->SHORTS = RADIO_SHORTS_READY_START_Msk | RADIO_SHORTS_END_DISABLE_Msk;
}

static bool wait(volatile uint32_t *ev, int us)
{
	for (int i = 0; i < us / 10; i++) {
		if (*ev) {
			return true;
		}
		k_usleep(10);
	}
	return false;
}

int main(void)
{
	int64_t t = T0_US;

	printk("PROBE role=%s mode=Ble_2Mbit raw-config\n", IS_ENABLED(CONFIG_PROBE_ROLE_TX) ? "tx" : "rx");
	for (size_t c = 0; c < ARRAY_SIZE(carriers); c++) {
		int ok = 0, crcerr = 0, timeout = 0;

		radio_cfg(carriers[c]);
		for (int i = 0; i < N; i++, t += 1000) {
			NRF_RADIO->EVENTS_END = 0;
			NRF_RADIO->EVENTS_DISABLED = 0;
			if (IS_ENABLED(CONFIG_PROBE_ROLE_TX)) {
				pkt[0] = 20;
				pkt[1] = i;
				k_sleep(K_TIMEOUT_ABS_US(t + 200));
				NRF_RADIO->TASKS_TXEN = 1;
				wait(&NRF_RADIO->EVENTS_DISABLED, 700);
			} else {
				k_sleep(K_TIMEOUT_ABS_US(t));
				NRF_RADIO->TASKS_RXEN = 1;
				if (wait(&NRF_RADIO->EVENTS_END, 700)) {
					if (NRF_RADIO->CRCSTATUS && pkt[0] == 20 && pkt[1] == (uint8_t)i) {
						ok++;
					} else {
						crcerr++;
					}
				} else {
					timeout++;
					NRF_RADIO->TASKS_DISABLE = 1;
				}
				wait(&NRF_RADIO->EVENTS_DISABLED, 300);
			}
		}
		if (!IS_ENABLED(CONFIG_PROBE_ROLE_TX)) {
			printk("PROBE_RESULT freq=%d n=%d ok=%d crcerr=%d timeout=%d\n", carriers[c], N, ok,
			       crcerr, timeout);
		}
	}
	printk("PROBE_DONE\n");
	return 0;
}
