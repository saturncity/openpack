/* AIR-1 probe: RADIO MODE=Ble_2Mbit, raw packet config (not BLE link layer), 1 packet/ms.
 * Event driven (TIMER0 compare IRQs trigger RADIO tasks, DISABLED interrupt): CPU polling made the sim
 * 200x slower. Steps through carriers; the RX side prints ok/crcerr/timeout per carrier. Loss = 1 - ok/n.
 * Frame (1 ms, TIMER0 period): TX starts at +200 us, RX opens at +0 and is forced off at +700 us.
 *
 * All peripheral access goes through the nrfx HAL: on nrf*bsim the HAL replacement calls the HW model's
 * register side effects (tasks, event clears). Plain NRF_X->TASKS_Y = 1 writes do nothing in the sim.
 */
#include <zephyr/kernel.h>
#include <zephyr/irq.h>
#include <zephyr/drivers/clock_control/nrf_clock_control.h>
#include <hal/nrf_radio.h>
#include <hal/nrf_timer.h>

static const uint16_t carriers[] = {2437, 2442, 2424, 2449, 2473}; /* in-band, in-band edge, gap x3 */
#define NB ARRAY_SIZE(carriers)
#define N  CONFIG_PROBE_PACKETS
#define TX IS_ENABLED(CONFIG_PROBE_ROLE_TX)

static uint8_t pkt[2 + 20]; /* S0, LENGTH, payload */
static int blk, cnt;
static int ok[NB], crcerr[NB], timeout[NB];
static K_SEM_DEFINE(done, 0, 1);

static void radio_init(void)
{
	const nrf_radio_packet_conf_t conf = {
		/* AIR-2 + ADR-0009: S0 header byte, 8-bit length, LE, whitening (the only 2 Mbit layout
		 * the bsim RADIO model accepts; identical on silicon).
		 */
		.s0len = 1,
		.lflen = 8,
		.plen = NRF_RADIO_PREAMBLE_LENGTH_16BIT,
		.maxlen = 32,
		.balen = 3,
		.whiteen = true,
	};

	nrf_radio_mode_set(NRF_RADIO, NRF_RADIO_MODE_BLE_2MBIT);
	nrf_radio_packet_configure(NRF_RADIO, &conf);
	nrf_radio_base0_set(NRF_RADIO, 0xA5C3E100);
	nrf_radio_prefix0_set(NRF_RADIO, 0x8E);
	nrf_radio_txaddress_set(NRF_RADIO, 0);
	nrf_radio_rxaddresses_set(NRF_RADIO, 1);
	nrf_radio_crc_configure(NRF_RADIO, 3, NRF_RADIO_CRC_ADDR_SKIP, 0x00065B);
	nrf_radio_datawhiteiv_set(NRF_RADIO, 0x40);
	nrf_radio_crcinit_set(NRF_RADIO, 0x555555);
	nrf_radio_txpower_set(NRF_RADIO, NRF_RADIO_TXPOWER_0DBM);
	nrf_radio_packetptr_set(NRF_RADIO, pkt);
	nrf_radio_shorts_set(NRF_RADIO, NRF_RADIO_SHORT_READY_START_MASK | NRF_RADIO_SHORT_END_DISABLE_MASK);
	nrf_radio_int_enable(NRF_RADIO, NRF_RADIO_INT_DISABLED_MASK);
	nrf_radio_frequency_set(NRF_RADIO, carriers[0]);
}

static bool take(nrf_timer_event_t ev)
{
	if (!nrf_timer_event_check(NRF_TIMER0, ev)) {
		return false;
	}
	nrf_timer_event_clear(NRF_TIMER0, ev);
	return true;
}

static void tisr(const void *arg)
{
	if (take(NRF_TIMER_EVENT_COMPARE0) && !TX) {
		nrf_radio_task_trigger(NRF_RADIO, NRF_RADIO_TASK_RXEN);
	}
	if (take(NRF_TIMER_EVENT_COMPARE1) && TX) {
		nrf_radio_task_trigger(NRF_RADIO, NRF_RADIO_TASK_TXEN);
	}
	/* Close the RX window only if no packet ended it: DISABLE in DISABLED state raises a second
	 * DISABLED event, which would count the window twice.
	 */
	if (take(NRF_TIMER_EVENT_COMPARE2) && !TX &&
	    nrf_radio_state_get(NRF_RADIO) != NRF_RADIO_STATE_DISABLED) {
		nrf_radio_task_trigger(NRF_RADIO, NRF_RADIO_TASK_DISABLE);
	}
}

static void isr(const void *arg)
{
	bool end = nrf_radio_event_check(NRF_RADIO, NRF_RADIO_EVENT_END);

	nrf_radio_event_clear(NRF_RADIO, NRF_RADIO_EVENT_DISABLED);
	nrf_radio_event_clear(NRF_RADIO, NRF_RADIO_EVENT_END);
	/* TX: packet 0 has no RX window, so block 0 is N + 1 packets, later blocks N. RX: N windows per block. */
	int limit = (TX && blk == 0) ? N + 1 : N;

	if (!TX) {
		if (end && nrf_radio_crc_status_check(NRF_RADIO) && pkt[1] == 20 && pkt[2] == 0xA5) {
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
			nrf_timer_task_trigger(NRF_TIMER0, NRF_TIMER_TASK_STOP);
			k_sem_give(&done);
		} else {
			nrf_radio_frequency_set(NRF_RADIO, carriers[blk]);
		}
	}
}

int main(void)
{
	pkt[0] = 0;  /* S0 */
	pkt[1] = 20; /* LENGTH */
	pkt[2] = 0xA5;
	printk("PROBE role=%s mode=Ble_2Mbit raw-config\n", TX ? "tx" : "rx");
	/* The radio needs HFCLK; the clock driver owns the CLOCK IRQ, so request it through the driver. */
	int err = nrf_clock_control_request_sync(DEVICE_DT_GET(DT_NODELABEL(hfclk)), NULL, K_MSEC(100));

	if (err != 0) {
		printk("PROBE_FAIL hfclk err=%d\n", err);
		return 0;
	}
	radio_init();
	IRQ_CONNECT(RADIO_IRQn, 0, isr, NULL, 0);
	irq_enable(RADIO_IRQn);

	nrf_timer_mode_set(NRF_TIMER0, NRF_TIMER_MODE_TIMER);
	nrf_timer_bit_width_set(NRF_TIMER0, NRF_TIMER_BIT_WIDTH_32);
	nrf_timer_prescaler_set(NRF_TIMER0, 4); /* 16 MHz / 2^4 = 1 MHz */
	nrf_timer_cc_set(NRF_TIMER0, NRF_TIMER_CC_CHANNEL0, 1000);
	nrf_timer_cc_set(NRF_TIMER0, NRF_TIMER_CC_CHANNEL1, 200);
	nrf_timer_cc_set(NRF_TIMER0, NRF_TIMER_CC_CHANNEL2, 700);
	nrf_timer_shorts_enable(NRF_TIMER0, NRF_TIMER_SHORT_COMPARE0_CLEAR_MASK);
	nrf_timer_int_enable(NRF_TIMER0, NRF_TIMER_INT_COMPARE0_MASK | NRF_TIMER_INT_COMPARE1_MASK |
						 NRF_TIMER_INT_COMPARE2_MASK);
	IRQ_CONNECT(TIMER0_IRQn, 0, tisr, NULL, 0);
	irq_enable(TIMER0_IRQn);
	nrf_timer_task_trigger(NRF_TIMER0, NRF_TIMER_TASK_START);

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
