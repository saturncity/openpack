/* AIR-4 pack frame scheduler (net core). TIMER0 at 1 MHz, period OP_FRAME_US (COMPARE0 + CLEAR short).
 * TIMER0 COMPARE0 (t0, copy A) and COMPARE1 (copy B) both publish one DPPI channel that RADIO TXEN
 * subscribes to, so both TX starts are hardware-timed; the CPU only retunes and reloads in the
 * RADIO DISABLED interrupt, never busy-waits (FW-2).
 *
 * Timing (from TXEN of copy A = t0; ramp-up R = 40 us fast mode (41 in bsim); air time T = packet bits / 2 Mbit/s):
 *   copy A on air  [t0+R,           t0+R+T]          channel A
 *   copy B TXEN at t0+T+T_GAP, on air [t0+R+T+T_GAP, t0+R+2T+T_GAP]  channel B
 * Copy B starts on air exactly T_GAP after copy A ends: B.start - A.end = (CC1 + R) - (R + T) = T_GAP.
 * The retune (DISABLED ISR -> frequency write) has T_GAP - R = 60 us at the default T_GAP.
 * Both copies end before t0 + OP_RX_WINDOW start (AIR-4 reserved RX slot, idle in v1). The payload is
 * 42 B, or 81 B with time diversity on (AIR-3 td_audio, composed by the app core, ADR-0017); T and the
 * copy B start follow the length of the frame being sent. 81 B copies end at t0 + 877 us: a TD pack
 * forfeits the RX slot (the TD build sets OP_RX_WINDOW_US = 0).
 *
 * Payload: the newest IPC frame (op_sched_put) is latched by TIMER0 COMPARE3 at LATCH_US =
 * t0 - OP_PACK_LATCH_LEAD_US, just before the t0 it goes on air at (#98): after copy B's EasyDMA is
 * done (both lengths) and OP_PACK_LATCH_LEAD_US + ramp-up before copy A's EasyDMA read. The latch is
 * the same for 42 B and 81 B. At start the net core tells the app core where that latch is
 * (op_sched_sync), and the app core places its audio frame clock OP_PACK_FRAME_LEAD_US before it, so
 * every frame lands in its own slot and audio frame done -> TXEN = the two leads (#87, ADR-0020).
 *
 * All peripheral access is via the nrfx HAL (the bsim models only see HAL writes, ADR-0009).
 */
#include <string.h>
#include <zephyr/kernel.h>
#include <zephyr/irq.h>
#include <zephyr/sys/byteorder.h>
#include <zephyr/drivers/clock_control/nrf_clock_control.h>
#include <hal/nrf_radio.h>
#include <hal/nrf_timer.h>
#include <hal/nrf_dppi.h>
#include "op_frame.h"
#if defined(CONFIG_OP_TEST_SCHED_REPORT)
#include "nsi_hw_scheduler.h" /* bsim: device time, for run.py (a) frame clock -> TXEN */
#endif

#define DPPI_CH 0 /* the net core runs no BT controller, nothing else allocates DPPI */
#define RAMP_US 40
/* AIR-2: preamble 2 + address 4 + S0 1 + length 1 + payload + CRC 3, 4 us/byte at 2 Mbit/s. */
#define AIR_US(len)  ((2 + 4 + 1 + 1 + (len) + 3) * 4)
#define CC_B_US(len) (AIR_US(len) + CONFIG_OP_T_GAP_US)

BUILD_ASSERT(CONFIG_OP_T_GAP_US > RAMP_US, "retune needs T_GAP > ramp-up");
BUILD_ASSERT(RAMP_US + 2 * AIR_US(OP_FRAME_LEN) + CONFIG_OP_T_GAP_US <= OP_FRAME_US - CONFIG_OP_RX_WINDOW_US,
	     "both copies must end before the reserved RX slot (AIR-4)");
BUILD_ASSERT(RAMP_US + 2 * AIR_US(OP_PAYLOAD_MAX) + CONFIG_OP_T_GAP_US <=
		     OP_FRAME_US - (IS_ENABLED(CONFIG_OP_TIME_DIVERSITY) ? CONFIG_OP_RX_WINDOW_US : 0),
	     "time diversity: both 81 B copies must fit the frame (ADR-0017)");

/* Payload latch (#98): TIMER0 COMPARE3, in TIMER0 us after t0, OP_PACK_LATCH_LEAD_US before the
 * next t0. Copy B (81 B: t0 + 877) has left EasyDMA; copy A's read starts at t0 + ramp-up.
 */
#define LATCH_US (OP_FRAME_US - CONFIG_OP_PACK_LATCH_LEAD_US)
#define CC_LATCH NRF_TIMER_CC_CHANNEL3
BUILD_ASSERT(RAMP_US + 2 * AIR_US(OP_PAYLOAD_MAX) + CONFIG_OP_T_GAP_US < LATCH_US,
	     "the latch must follow the end of copy B at every length");

static uint8_t pkt[2 + OP_PAYLOAD_MAX]; /* S0, LENGTH, payload */
static uint8_t pending[OP_PAYLOAD_MAX];
static uint8_t pending_len;
static bool fresh, on_b, armed;
/* Before the app core's first frame: an empty payload of the boot td setting's length. */
#define BOOT_LEN (IS_ENABLED(CONFIG_OP_TIME_DIVERSITY) ? OP_PAYLOAD_MAX : OP_FRAME_LEN)
static uint32_t underrun, overrun, cc_b = CC_B_US(BOOT_LEN);
static int32_t margin_min = INT32_MAX, margin_max = INT32_MIN; /* latch - arrival, us */
static uint32_t t0_hw_mod; /* test only: device time of the next t0, mod OP_FRAME_US */

#define CC_NOW NRF_TIMER_CC_CHANNEL2 /* capture only */

/* TIMER0 us since the last t0 (0..OP_FRAME_US-1). */
static uint32_t phase_us(void)
{
	nrf_timer_task_trigger(NRF_TIMER0, nrf_timer_capture_task_get(CC_NOW));
	return nrf_timer_cc_get(NRF_TIMER0, CC_NOW);
}

/* us until the next latch, 1..OP_FRAME_US */
static int32_t to_latch_us(void)
{
	return OP_FRAME_US - (int32_t)((phase_us() + OP_FRAME_US - LATCH_US) % OP_FRAME_US);
}

void op_sched_put(const uint8_t *payload, size_t len)
{
	if (len != OP_FRAME_LEN && len != OP_PAYLOAD_MAX) {
		return;
	}
	unsigned int key = irq_lock();
	/* Margin to this frame's own latch: the app core aims for OP_PACK_FRAME_LEAD_US (pack.c); the
	 * deviation from that is taken within +-half a frame, so a late frame shows as negative.
	 */
	int32_t dev = (to_latch_us() - CONFIG_OP_PACK_FRAME_LEAD_US + OP_FRAME_US + OP_FRAME_US / 2) %
			      OP_FRAME_US - OP_FRAME_US / 2;
	int32_t m = CONFIG_OP_PACK_FRAME_LEAD_US + dev;

	if (fresh) {
		overrun++;
	}
	memcpy(pending, payload, len);
	pending_len = len;
	fresh = true;
	margin_min = MIN(margin_min, m);
	margin_max = MAX(margin_max, m);
	irq_unlock(key);
}

/* #87: tell the app core where the latch is, so it places its audio frame clock
 * CONFIG_OP_PACK_FRAME_LEAD_US before it (src/app/pack.c). Message: u16 LE us to the next latch.
 */
int op_sched_sync(void)
{
	uint8_t m[OP_SYNC_LEN];

	sys_put_le16((uint16_t)to_latch_us(), m);
	return op_ipc_send(m, sizeof(m));
}

/* Runs in the TIMER0 ISR at the latch: next frame's payload. A missing frame repeats the last one.
 * Copy B of the next frame starts AIR_US(len) + T_GAP after t0; COMPARE1 is not due until then.
 */
static void load(void)
{
	if (fresh) {
		memcpy(&pkt[2], pending, pending_len);
		pkt[1] = pending_len;
		cc_b = CC_B_US(pending_len);
		if (armed) {
			nrf_timer_cc_set(NRF_TIMER0, NRF_TIMER_CC_CHANNEL1, cc_b);
		}
		fresh = false;
	} else {
		underrun++;
	}
}

static void radio_isr(const void *arg)
{
	nrf_radio_event_clear(NRF_RADIO, NRF_RADIO_EVENT_DISABLED);
	nrf_radio_event_clear(NRF_RADIO, NRF_RADIO_EVENT_END);
	on_b = !on_b;
	if (on_b) {
		nrf_radio_frequency_set(NRF_RADIO, OP_CH_B_MHZ);
	} else {
		nrf_radio_frequency_set(NRF_RADIO, OP_CH_A_MHZ);
	}
}

/* COMPARE3: the payload latch, every frame. COMPARE0, first frame only: COMPARE1 would otherwise fire
 * at CC_B_US before the first COMPARE0 (t0) and send copy B ahead of copy A. CC1 starts unreachable
 * and is armed here, at t0, CC_B_US before it is due.
 */
static void timer_isr(const void *arg)
{
	if (nrf_timer_event_check(NRF_TIMER0, NRF_TIMER_EVENT_COMPARE3)) {
		nrf_timer_event_clear(NRF_TIMER0, NRF_TIMER_EVENT_COMPARE3);
		load();
#if defined(CONFIG_OP_TEST_SCHED_REPORT)
		t0_hw_mod = (uint32_t)((nsi_hws_get_time() + OP_FRAME_US - phase_us()) % OP_FRAME_US);
#endif
	}
	if (nrf_timer_event_check(NRF_TIMER0, NRF_TIMER_EVENT_COMPARE0)) {
		nrf_timer_event_clear(NRF_TIMER0, NRF_TIMER_EVENT_COMPARE0);
		nrf_timer_cc_set(NRF_TIMER0, NRF_TIMER_CC_CHANNEL1, cc_b);
		armed = true;
		nrf_timer_int_disable(NRF_TIMER0, NRF_TIMER_INT_COMPARE0_MASK);
	}
}

static void radio_init(void)
{
	/* AIR-2 + ADR-0009: BLE 2M PDU layout, raw (no link layer). */
	const nrf_radio_packet_conf_t conf = {
		.s0len = 1,
		.lflen = 8,
		.plen = NRF_RADIO_PREAMBLE_LENGTH_16BIT,
		.maxlen = OP_PAYLOAD_MAX,
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
	nrf_radio_txaddress_set(NRF_RADIO, 0);
	nrf_radio_crc_configure(NRF_RADIO, 3, NRF_RADIO_CRC_ADDR_SKIP, 0x00065B);
	nrf_radio_crcinit_set(NRF_RADIO, 0x555555);
	nrf_radio_datawhiteiv_set(NRF_RADIO, 0x40);
	nrf_radio_txpower_set(NRF_RADIO, NRF_RADIO_TXPOWER_0DBM); /* FEM gain later (AIR-6) */
	nrf_radio_packetptr_set(NRF_RADIO, pkt);
	nrf_radio_frequency_set(NRF_RADIO, OP_CH_A_MHZ);
	nrf_radio_shorts_set(NRF_RADIO, NRF_RADIO_SHORT_READY_START_MASK | NRF_RADIO_SHORT_END_DISABLE_MASK);
	nrf_radio_int_enable(NRF_RADIO, NRF_RADIO_INT_DISABLED_MASK);
	nrf_radio_subscribe_set(NRF_RADIO, NRF_RADIO_TASK_TXEN, DPPI_CH);
}

/* Test only (CONFIG_OP_PACK_TEST_RUN_MS): the pack goes silent, as if powered off (RX-10 bsim (e)). */
static void test_stop(struct k_timer *t)
{
	nrf_timer_task_trigger(NRF_TIMER0, NRF_TIMER_TASK_STOP);
	printk("SCHED stop (test, after %d ms)\n", CONFIG_OP_PACK_TEST_RUN_MS);
}

static K_TIMER_DEFINE(test_stop_timer, test_stop, NULL);

/* Test only (CONFIG_OP_TEST_SCHED_REPORT, bsim): once per second, how early the app core's frames
 * reached the latch (margin = latch - arrival, us; tests/bsim/sched/check.py), the counters, and the
 * device time of t0 mod 1 ms (with the app core's PACK_FCLK line: frame clock -> TXEN, run.py (a)).
 */
static void report(struct k_work *w)
{
	unsigned int key = irq_lock();
	int32_t lo = margin_min, hi = margin_max;

	margin_min = INT32_MAX;
	margin_max = INT32_MIN;
	irq_unlock(key);
	if (lo <= hi) { /* no line for a second without frames */
		printk("PACK_IPC margin_us_min=%d margin_us_max=%d overruns=%u underruns=%u "
		       "t0_hw_mod_us=%u\n",
		       lo, hi, overrun, underrun, t0_hw_mod);
	}
}

static K_WORK_DEFINE(report_work, report);

static void report_expiry(struct k_timer *t)
{
	k_work_submit(&report_work);
}

static K_TIMER_DEFINE(report_timer, report_expiry, NULL);

int op_sched_start(void)
{
	int err = nrf_clock_control_request_sync(DEVICE_DT_GET(DT_NODELABEL(hfclk)), NULL, K_MSEC(100));

	if (err != 0) {
		return err;
	}
	pkt[0] = 0; /* S0: format version 0 (ADR-0009) */
	pkt[1] = BOOT_LEN;
	radio_init();
	IRQ_CONNECT(RADIO_IRQn, 0, radio_isr, NULL, 0);
	irq_enable(RADIO_IRQn);

	nrf_timer_mode_set(NRF_TIMER0, NRF_TIMER_MODE_TIMER);
	nrf_timer_bit_width_set(NRF_TIMER0, NRF_TIMER_BIT_WIDTH_32);
	nrf_timer_prescaler_set(NRF_TIMER0, 4); /* 16 MHz / 2^4 = 1 MHz */
	nrf_timer_cc_set(NRF_TIMER0, NRF_TIMER_CC_CHANNEL0, OP_FRAME_US);
	nrf_timer_cc_set(NRF_TIMER0, NRF_TIMER_CC_CHANNEL1, UINT32_MAX); /* armed at t0, timer_isr */
	nrf_timer_cc_set(NRF_TIMER0, CC_LATCH, LATCH_US);
	nrf_timer_int_enable(NRF_TIMER0, NRF_TIMER_INT_COMPARE0_MASK | NRF_TIMER_INT_COMPARE3_MASK);
	IRQ_CONNECT(TIMER0_IRQn, 0, timer_isr, NULL, 0);
	irq_enable(TIMER0_IRQn);
	nrf_timer_shorts_enable(NRF_TIMER0, NRF_TIMER_SHORT_COMPARE0_CLEAR_MASK);
	nrf_timer_publish_set(NRF_TIMER0, NRF_TIMER_EVENT_COMPARE0, DPPI_CH);
	nrf_timer_publish_set(NRF_TIMER0, NRF_TIMER_EVENT_COMPARE1, DPPI_CH);
	nrf_dppi_channels_enable(NRF_DPPIC, BIT(DPPI_CH));
	nrf_timer_task_trigger(NRF_TIMER0, NRF_TIMER_TASK_START);
	if (CONFIG_OP_PACK_TEST_RUN_MS > 0) {
		k_timer_start(&test_stop_timer, K_MSEC(CONFIG_OP_PACK_TEST_RUN_MS), K_NO_WAIT);
	}
	if (IS_ENABLED(CONFIG_OP_TEST_SCHED_REPORT)) {
		k_timer_start(&report_timer, K_SECONDS(1), K_SECONDS(1));
	}
	printk("SCHED start pack_id=%d fA=%d fB=%d air_us=%d cc_b_us=%d td_air_us=%d td_cc_b_us=%d "
	       "latch_us=%d\n",
	       OP_PACK_ID, OP_CH_A_MHZ, OP_CH_B_MHZ, AIR_US(OP_FRAME_LEN), CC_B_US(OP_FRAME_LEN),
	       AIR_US(OP_PAYLOAD_MAX), CC_B_US(OP_PAYLOAD_MAX), LATCH_US);
	return 0;
}

uint32_t op_sched_underruns(void)
{
	return underrun;
}

uint32_t op_sched_overruns(void)
{
	return overrun;
}
