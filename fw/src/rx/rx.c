/* Receiver net core: RX-2 acquisition, RX-3 tracking, RX-4 copy merge, RX-5 antenna choice.
 *
 * Acquisition (RX-2): TIMER0 free-runs from 0, RADIO listens on channel A back to back (END ->
 * DISABLE, re-RXEN in the DISABLED ISR) until a CRC-valid AIR-3 frame arrives with this pack's
 * access address. Only copy A is on channel A, so that packet fixes the frame phase.
 *
 * Tracking (RX-3, AIR-4): TIMER0 at 1 MHz, period OP_FRAME_US (COMPARE0 + CLEAR short), frame 0 =
 * LEAD_US before copy A's expected start. Both RX starts are hardware-timed: COMPARE0 (window A) and
 * COMPARE1 (window B) publish one DPPI channel that RADIO RXEN subscribes to. RADIO ADDRESS
 * publishes a second channel that TIMER0 CAPTURE5 subscribes to, so every copy is time-stamped
 * in hardware. Frame timeline (us, defaults T_GAP 100, window W 50, ramp R 40, air T 212):
 *   0    RXEN on A          (copy A expected on air at LEAD = R + W = 90, ADDRESS at 114)
 *   166  close A if no ADDRESS yet (expected ADDRESS + W + 2)
 *   312  RXEN on B          (copy B expected at 90 + T + T_GAP = 402)
 *   478  close B if no ADDRESS yet
 *   674  deadline: merge (RX-4, first CRC-valid copy wins), hand one frame to the app core,
 *        re-centre the next frame on the measured ADDRESS time, count misses
 * A copy is accepted only if its ADDRESS falls inside +-W of the expected time. Each valid copy
 * moves the next frame boundary by its timing error (1 us steps), which follows +-40 ppm crystal
 * offset (0.04 us/frame) with no drift out of the window. After OP_RX_MISS_LIMIT consecutive frames
 * with no valid copy the receiver re-acquires (pack reboot, RX-10).
 *
 * All peripheral access is via the nrfx HAL (the bsim models only see HAL writes, ADR-0009).
 * DISABLE is only sent in a non-DISABLED state: in DISABLED it raises a second DISABLED event.
 */
#include <string.h>
#include <zephyr/kernel.h>
#include <zephyr/irq.h>
#include <zephyr/drivers/clock_control/nrf_clock_control.h>
#include <hal/nrf_radio.h>
#include <hal/nrf_timer.h>
#include <hal/nrf_dppi.h>
#include "op_rx.h"

#define DPPI_RXEN 0 /* TIMER0 COMPARE0/1 -> RADIO RXEN */
#define DPPI_ADDR 1 /* RADIO ADDRESS -> TIMER0 CAPTURE5 */
#define CC_CAP    NRF_TIMER_CC_CHANNEL5
#define CC_NOW    NRF_TIMER_CC_CHANNEL6
#define RAMP_US   40 /* RXEN -> READY, fast ramp-up */
#define W_US      CONFIG_OP_RX_TRACK_WIN_US
#define AIR_US    ((2 + 4 + 1 + 1 + OP_FRAME_LEN + 3) * 4) /* AIR-2 packet at 4 us/byte */
#define ADDR_US   ((2 + 4) * 4) /* copy start -> ADDRESS event: preamble + access address */
#define LEAD_US   (RAMP_US + W_US)
#define B_OFS_US  (AIR_US + CONFIG_OP_T_GAP_US) /* copy B start - copy A start (AIR-4) */
#define EXP_A_US  (LEAD_US + ADDR_US)           /* expected ADDRESS of copy A */
#define CC_B_US   B_OFS_US                      /* RXEN for window B */
#define CLOSE_A   (EXP_A_US + W_US + 2)
#define CLOSE_B   (CC_B_US + CLOSE_A)
#define DEADLINE  (CC_B_US + LEAD_US + AIR_US + W_US + 10)
#define NEVER     UINT32_MAX

BUILD_ASSERT(CC_B_US > CLOSE_A, "window B must open after window A closes");
BUILD_ASSERT(DEADLINE + W_US < OP_FRAME_US, "deadline and re-centring must fit in one frame");

struct win {
	bool ok;
	uint32_t cap; /* TIMER0 at ADDRESS */
	int8_t rssi;
	uint8_t ant;
};

struct ev {
	uint8_t kind; /* 0 frame, 1 lock, 2 re-acquire */
	uint32_t t_us;
	struct op_rx_msg m;
};

K_MSGQ_DEFINE(evq, sizeof(struct ev), 16, 4);

static uint8_t buf[2][2 + OP_FRAME_LEN]; /* S0, LENGTH, payload per window */
static struct win win[2];
static struct op_ant ant;
static bool tracking;
static uint8_t cur; /* window in progress: 0 = A, 1 = B */
static uint8_t epoch;
static uint32_t frame, misses, dropped;

__weak void op_rx_ant_select(uint8_t a)
{
	ARG_UNUSED(a);
}

static uint32_t now_us(void)
{
	return (uint32_t)k_ticks_to_us_floor64(k_uptime_ticks());
}

static void post(uint8_t kind, const struct op_rx_msg *m)
{
	struct ev e = {.kind = kind, .t_us = now_us()};

	if (m != NULL) {
		e.m = *m;
	}
	e.m.epoch = epoch;
	if (k_msgq_put(&evq, &e, K_NO_WAIT) != 0) {
		dropped++;
	}
}

static void listen(uint8_t w)
{
	cur = w;
	nrf_radio_frequency_set(NRF_RADIO, w ? OP_CH_B_MHZ : OP_CH_A_MHZ);
	nrf_radio_packetptr_set(NRF_RADIO, buf[w]);
	win[w].ant = op_ant_pick(&ant, w, frame);
	op_rx_ant_select(win[w].ant);
}

static void set_cc(uint32_t p, uint32_t b, uint32_t ca, uint32_t cb, uint32_t d)
{
	nrf_timer_cc_set(NRF_TIMER0, NRF_TIMER_CC_CHANNEL0, p);
	nrf_timer_cc_set(NRF_TIMER0, NRF_TIMER_CC_CHANNEL1, b);
	nrf_timer_cc_set(NRF_TIMER0, NRF_TIMER_CC_CHANNEL2, ca);
	nrf_timer_cc_set(NRF_TIMER0, NRF_TIMER_CC_CHANNEL3, cb);
	nrf_timer_cc_set(NRF_TIMER0, NRF_TIMER_CC_CHANNEL4, d);
}

/* RX-2: back-to-back RX on channel A, timer free-running from 0. Radio is DISABLED on entry. */
static void acquire(void)
{
	tracking = false;
	nrf_radio_subscribe_clear(NRF_RADIO, NRF_RADIO_TASK_RXEN);
	nrf_timer_shorts_disable(NRF_TIMER0, NRF_TIMER_SHORT_COMPARE0_CLEAR_MASK);
	set_cc(NEVER, NEVER, NEVER, NEVER, NEVER);
	nrf_timer_task_trigger(NRF_TIMER0, NRF_TIMER_TASK_CLEAR);
	listen(0);
	nrf_radio_event_clear(NRF_RADIO, NRF_RADIO_EVENT_ADDRESS);
	nrf_radio_task_trigger(NRF_RADIO, NRF_RADIO_TASK_RXEN);
}

/* Copy A of some frame just ended CRC-valid; its ADDRESS is in CC_CAP. The next copy A has its
 * ADDRESS one frame later, so the next frame boundary is EXP_A_US before that.
 */
static void lock(void)
{
	uint32_t c = nrf_timer_cc_get(NRF_TIMER0, CC_CAP);

	set_cc(c + OP_FRAME_US - EXP_A_US, NEVER, NEVER, NEVER, NEVER);
	nrf_timer_shorts_enable(NRF_TIMER0, NRF_TIMER_SHORT_COMPARE0_CLEAR_MASK);
	nrf_radio_subscribe_set(NRF_RADIO, NRF_RADIO_TASK_RXEN, DPPI_RXEN);
	tracking = true;
	misses = 0;
	epoch++;
	frame = 0;
	memset(win, 0, sizeof(win));
	listen(0);
	post(1, NULL);
}

static void radio_isr(const void *arg)
{
	bool end = nrf_radio_event_check(NRF_RADIO, NRF_RADIO_EVENT_END);
	bool ok = end && nrf_radio_crc_status_check(NRF_RADIO) && buf[cur][1] == OP_FRAME_LEN;

	nrf_radio_event_clear(NRF_RADIO, NRF_RADIO_EVENT_DISABLED);
	nrf_radio_event_clear(NRF_RADIO, NRF_RADIO_EVENT_END);
	nrf_radio_event_clear(NRF_RADIO, NRF_RADIO_EVENT_ADDRESS);
	if (!tracking) {
		if (ok) {
			lock();
		} else {
			nrf_radio_task_trigger(NRF_RADIO, NRF_RADIO_TASK_RXEN);
		}
		return;
	}
	struct win *w = &win[cur];
	uint32_t c = nrf_timer_cc_get(NRF_TIMER0, CC_CAP);
	int32_t exp = cur ? EXP_A_US + B_OFS_US : EXP_A_US;
	int32_t err = (int32_t)c - exp;

	w->ok = ok && err >= -W_US && err <= W_US;
	w->cap = c;
	w->rssi = ok ? -(int8_t)nrf_radio_rssi_sample_get(NRF_RADIO) : 0;
	if (cur == 0) {
		listen(1);
		/* A copy arriving late inside its window can end after COMPARE1 (RXEN dropped while in RX). */
		nrf_timer_task_trigger(NRF_TIMER0, nrf_timer_capture_task_get(CC_NOW));
		uint32_t now = nrf_timer_cc_get(NRF_TIMER0, CC_NOW);

		if (now >= CC_B_US && now < CLOSE_B) {
			nrf_radio_task_trigger(NRF_RADIO, NRF_RADIO_TASK_RXEN);
		}
	}
}

static void close_window(void)
{
	if (!nrf_radio_event_check(NRF_RADIO, NRF_RADIO_EVENT_ADDRESS) &&
	    nrf_radio_state_get(NRF_RADIO) != NRF_RADIO_STATE_DISABLED) {
		nrf_radio_task_trigger(NRF_RADIO, NRF_RADIO_TASK_DISABLE);
	}
}

/* RX-4 merge at the fixed deadline, re-centring, RX-3 miss count, RX-5 reports. */
static void deadline(void)
{
	struct op_rx_msg m = {0};
	int32_t err = 0;

	if (win[0].ok) {
		memcpy(m.frame, &buf[0][2], OP_FRAME_LEN);
		m.rssi = win[0].rssi;
		err = (int32_t)win[0].cap - EXP_A_US;
	} else if (win[1].ok) {
		memcpy(m.frame, &buf[1][2], OP_FRAME_LEN);
		m.rssi = win[1].rssi;
		err = (int32_t)win[1].cap - (EXP_A_US + B_OFS_US);
	}
	m.flags = (win[0].ok ? OP_RX_A_OK : 0) | (win[1].ok ? OP_RX_B_OK : 0);
	m.flags |= m.flags ? OP_RX_VALID : 0;
	m.epoch = epoch;
	m.ant = win[0].ant | (win[1].ant << 1);
	for (uint8_t c = 0; c < 2; c++) {
		(void)op_ant_report(&ant, c, win[c].ant, win[c].ok, win[c].rssi);
	}
	post(0, &m);
	misses = m.flags ? 0 : misses + 1;
	memset(win, 0, sizeof(win));
	frame++;
	if (misses >= CONFIG_OP_RX_MISS_LIMIT) {
		post(2, NULL);
		acquire();
		return;
	}
	/* Stretch or shrink this frame by the measured error; COMPARE0 restores the period. */
	nrf_timer_cc_set(NRF_TIMER0, NRF_TIMER_CC_CHANNEL0, OP_FRAME_US + err);
	listen(0);
}

static bool take(nrf_timer_event_t ev)
{
	if (!nrf_timer_event_check(NRF_TIMER0, ev)) {
		return false;
	}
	nrf_timer_event_clear(NRF_TIMER0, ev);
	return true;
}

static void timer_isr(const void *arg)
{
	if (take(NRF_TIMER_EVENT_COMPARE0) && tracking) {
		set_cc(OP_FRAME_US, CC_B_US, CLOSE_A, CLOSE_B, DEADLINE);
	}
	if (take(NRF_TIMER_EVENT_COMPARE2) && tracking) {
		close_window();
	}
	if (take(NRF_TIMER_EVENT_COMPARE3) && tracking) {
		close_window();
	}
	if (take(NRF_TIMER_EVENT_COMPARE4) && tracking) {
		deadline();
	}
}

static void radio_init(void)
{
	/* AIR-2 + ADR-0009: BLE 2M PDU layout, raw (no link layer); same as the pack (sched.c). */
	const nrf_radio_packet_conf_t conf = {
		.s0len = 1,
		.lflen = 8,
		.plen = NRF_RADIO_PREAMBLE_LENGTH_16BIT,
		.maxlen = OP_FRAME_LEN,
		.statlen = 0,
		.balen = 3,
		.whiteen = true,
	};
	uint32_t aa = 0x8E89BED6u ^ ((uint32_t)OP_PACK_ID * 0x9E3779B1u);

	nrf_radio_mode_set(NRF_RADIO, NRF_RADIO_MODE_BLE_2MBIT);
	nrf_radio_fast_ramp_up_enable_set(NRF_RADIO, true);
	nrf_radio_packet_configure(NRF_RADIO, &conf);
	nrf_radio_prefix0_set(NRF_RADIO, aa >> 24);
	nrf_radio_base0_set(NRF_RADIO, aa << 8);
	nrf_radio_rxaddresses_set(NRF_RADIO, 1);
	nrf_radio_crc_configure(NRF_RADIO, 3, NRF_RADIO_CRC_ADDR_SKIP, 0x00065B);
	nrf_radio_crcinit_set(NRF_RADIO, 0x555555);
	nrf_radio_datawhiteiv_set(NRF_RADIO, 0x40);
	nrf_radio_shorts_set(NRF_RADIO, NRF_RADIO_SHORT_READY_START_MASK |
						NRF_RADIO_SHORT_END_DISABLE_MASK |
						NRF_RADIO_SHORT_ADDRESS_RSSISTART_MASK);
	nrf_radio_int_enable(NRF_RADIO, NRF_RADIO_INT_DISABLED_MASK);
	nrf_radio_publish_set(NRF_RADIO, NRF_RADIO_EVENT_ADDRESS, DPPI_ADDR);
}

static void timer_init(void)
{
	nrf_timer_mode_set(NRF_TIMER0, NRF_TIMER_MODE_TIMER);
	nrf_timer_bit_width_set(NRF_TIMER0, NRF_TIMER_BIT_WIDTH_32);
	nrf_timer_prescaler_set(NRF_TIMER0, 4); /* 16 MHz / 2^4 = 1 MHz */
	set_cc(NEVER, NEVER, NEVER, NEVER, NEVER);
	nrf_timer_int_enable(NRF_TIMER0, NRF_TIMER_INT_COMPARE0_MASK | NRF_TIMER_INT_COMPARE2_MASK |
						 NRF_TIMER_INT_COMPARE3_MASK | NRF_TIMER_INT_COMPARE4_MASK);
	nrf_timer_publish_set(NRF_TIMER0, NRF_TIMER_EVENT_COMPARE0, DPPI_RXEN);
	nrf_timer_publish_set(NRF_TIMER0, NRF_TIMER_EVENT_COMPARE1, DPPI_RXEN);
	nrf_timer_subscribe_set(NRF_TIMER0, nrf_timer_capture_task_get(CC_CAP), DPPI_ADDR);
	nrf_dppi_channels_enable(NRF_DPPIC, BIT(DPPI_RXEN) | BIT(DPPI_ADDR));
}

/* Thread context: IPC send and log lines stay out of the ISRs. */
static void rx_thread(void *a, void *b, void *c)
{
	struct ev e;

	for (;;) {
		k_msgq_get(&evq, &e, K_FOREVER);
		if (e.kind == 0) {
			(void)op_ipc_send((const uint8_t *)&e.m, sizeof(e.m));
		} else {
			printk("RX %s epoch=%u t_us=%u dropped=%u ant_switches=%u\n",
			       e.kind == 1 ? "lock" : "reacquire", e.m.epoch, e.t_us, dropped, ant.switches);
		}
	}
}

K_THREAD_DEFINE(rx_tid, 1024, rx_thread, NULL, NULL, NULL, 5, 0, 0);

int op_rx_start(void)
{
	int err = nrf_clock_control_request_sync(DEVICE_DT_GET(DT_NODELABEL(hfclk)), NULL, K_MSEC(100));

	if (err != 0) {
		return err;
	}
	op_ant_init(&ant, CONFIG_OP_RX_ANT_PROBE_FRAMES, CONFIG_OP_RX_ANT_HYST_DB);
	radio_init();
	IRQ_CONNECT(RADIO_IRQn, 0, radio_isr, NULL, 0);
	irq_enable(RADIO_IRQn);
	timer_init();
	IRQ_CONNECT(TIMER0_IRQn, 0, timer_isr, NULL, 0);
	irq_enable(TIMER0_IRQn);
	printk("RX start pack_id=%d fA=%d fB=%d win_us=%d exp_a_us=%d cc_b_us=%d deadline_us=%d\n",
	       OP_PACK_ID, OP_CH_A_MHZ, OP_CH_B_MHZ, W_US, EXP_A_US, CC_B_US,
	       DEADLINE);
	nrf_timer_task_trigger(NRF_TIMER0, NRF_TIMER_TASK_START);
	acquire();
	return 0;
}
