/* AIR-1 probe: RADIO MODE=Ble_2Mbit, raw packet config (not BLE link layer), 1 packet/ms.
 * Event driven (TIMER0 -> DPPI -> RADIO tasks, DISABLED interrupt): CPU polling made the sim 200x slower.
 * Steps through carriers; the RX side prints ok/crcerr/timeout per carrier. Loss = 1 - ok/n.
 * Frame (1 ms, TIMER0 period): TX starts at +200 us, RX opens at +0 and is forced off at +700 us. */
#include <zephyr/kernel.h>
#include <zephyr/irq.h>
#include <nrfx.h>

static const int carriers[] = {2437, 2442, 2424, 2449, 2473}; /* in-band, in-band edge, gap, gap, gap */
#define NB ARRAY_SIZE(carriers)
#define N CONFIG_PROBE_PACKETS
#define TX IS_ENABLED(CONFIG_PROBE_ROLE_TX)
#define EN (1u << 31)

static uint8_t pkt[1 + 20];
static int blk, cnt;
static int ok[NB], crcerr[NB], timeout[NB];
static K_SEM_DEFINE(done, 0, 1);

static void radio_init(void)
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
	NRF_RADIO->PACKETPTR = (uint32_t)(uintptr_t)pkt;
	NRF_RADIO->SHORTS = RADIO_SHORTS_READY_START_Msk | RADIO_SHORTS_END_DISABLE_Msk;
	NRF_RADIO->INTENSET = RADIO_INTENSET_DISABLED_Msk;
	NRF_RADIO->FREQUENCY = carriers[0] - 2400;
}

static void tisr(const void *arg)
{
	if (NRF_TIMER0->EVENTS_COMPARE[0]) {
		NRF_TIMER0->EVENTS_COMPARE[0] = 0;
		if (!TX) {
			NRF_RADIO->TASKS_RXEN = 1;
		}
	}
	if (NRF_TIMER0->EVENTS_COMPARE[1]) {
		NRF_TIMER0->EVENTS_COMPARE[1] = 0;
		if (TX) {
			NRF_RADIO->TASKS_TXEN = 1;
		}
	}
	if (NRF_TIMER0->EVENTS_COMPARE[2]) {
		NRF_TIMER0->EVENTS_COMPARE[2] = 0;
		if (!TX) {
			NRF_RADIO->TASKS_DISABLE = 1;
		}
	}
}

static void isr(const void *arg)
{
	int end = NRF_RADIO->EVENTS_END;

	NRF_RADIO->EVENTS_DISABLED = 0;
	NRF_RADIO->EVENTS_END = 0;
	/* TX: packet 0 has no RX window, so block 0 is N + 1 packets, later blocks N. RX: N windows per block. */
	int limit = (TX && blk == 0) ? N + 1 : N;

	if (!TX) {
		if (end && NRF_RADIO->CRCSTATUS && pkt[0] == 20 && pkt[1] == 0xA5) {
			ok[blk]++;
		} else if (end) {
			crcerr[blk]++;
		} else {
			timeout[blk]++;
		}
	}
	if (++cnt >= limit) {
		cnt = 0;
		if (++blk == NB) {
			NRF_TIMER0->TASKS_STOP = 1;
			k_sem_give(&done);
		} else {
			NRF_RADIO->FREQUENCY = carriers[blk] - 2400;
		}
	}
}

int main(void)
{
	pkt[0] = 20;
	pkt[1] = 0xA5;
	printk("PROBE role=%s mode=Ble_2Mbit raw-config\n", TX ? "tx" : "rx");
	radio_init();
	IRQ_CONNECT(RADIO_IRQn, 0, isr, NULL, 0);
	irq_enable(RADIO_IRQn);

	NRF_TIMER0->MODE = 0;
	NRF_TIMER0->BITMODE = 3;
	NRF_TIMER0->PRESCALER = 4; /* 16 MHz / 2^4 = 1 MHz */
	NRF_TIMER0->CC[0] = 1000;
	NRF_TIMER0->CC[1] = 200;
	NRF_TIMER0->CC[2] = 700;
	NRF_TIMER0->SHORTS = TIMER_SHORTS_COMPARE0_CLEAR_Msk;
	NRF_TIMER0->INTENSET = TIMER_INTENSET_COMPARE0_Msk | TIMER_INTENSET_COMPARE1_Msk | TIMER_INTENSET_COMPARE2_Msk;
	IRQ_CONNECT(TIMER0_IRQn, 0, tisr, NULL, 0);
	irq_enable(TIMER0_IRQn);
	NRF_TIMER0->TASKS_START = 1;

	k_msleep(5);
	NRF_TIMER0->TASKS_CAPTURE[3] = 1;
	printk("PROBE_DBG timer=%u\n", NRF_TIMER0->CC[3]);
	k_sem_take(&done, K_FOREVER);
	if (!TX) {
		for (size_t c = 0; c < NB; c++) {
			printk("PROBE_RESULT freq=%d n=%d ok=%d crcerr=%d timeout=%d\n", carriers[c], N, ok[c],
			       crcerr[c], timeout[c]);
		}
	}
	printk("PROBE_DONE\n");
	return 0;
}
