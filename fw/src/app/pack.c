/* Pack app core pipeline (FW-2..FW-4): per audio frame (48 samples = 1 ms) op_audio_read_frame ->
 * ADPCM-6 -> AIR-3 payload -> op_ipc_send. The net core puts the newest frame on air (net/sched.c).
 *
 * Pacing is the audio frame clock, an interrupt, never a kernel timeout (#87). A k_timer runs on the
 * 32768 Hz RTC: 1 ms = 33 ticks = 1007 us, so the frame phase sweeps past the net core's latch every
 * 142 frames, and any other thread's timeout due within 3 ticks of a frame (nrf_rtc_timer
 * MIN_CYCLES_FROM_NOW) pushed that frame 61 us late; near the latch the late frame missed its slot
 * and was overwritten by the next one: a repeat, then a seq skip.
 *
 * Frame clock: until the I2S backend lands (Phase 5, I2S RXPTRUPD per 48-sample buffer) it is TIMER1
 * at 1 MHz, from the same crystal as the net core's TIMER0. Phase: the net core sends once, at start,
 * the time to its next latch (op_sched_sync); the first frame clock is placed
 * CONFIG_OP_PACK_FRAME_LEAD_US before a latch. That lead is the frame thread's deadline for read +
 * encode + IPC: under any load that leaves the thread its deadline, no frame is skipped.
 */
#include <errno.h>
#include <string.h>
#include <zephyr/kernel.h>
#include <zephyr/irq.h>
#include <zephyr/sys/byteorder.h>
#include <hal/nrf_timer.h>
#include "op_frame.h"
#include "op_audio.h"
#include "adpcm6.h"

#define HDR 3 /* AIR-3: seq u8, status u16 LE; then one ADPCM-6 frame (codec_state + audio) */
#define MIN_FIRST_US 50 /* first frame clock at least this far after the sync arrives */

BUILD_ASSERT(OP_FRAME_LEN == HDR + ADPCM6_FRAME_BYTES, "AIR-3 v1 payload is one ADPCM-6 frame");
BUILD_ASSERT(ADPCM6_FRAME_SAMPLES == OP_AUDIO_FRAME_SAMPLES && OP_FRAME_US == 1000, "1 ms frames");
BUILD_ASSERT(CONFIG_OP_PACK_FRAME_LEAD_US > 0 && CONFIG_OP_PACK_FRAME_LEAD_US < OP_FRAME_US);

static K_SEM_DEFINE(tick, 0, 2); /* frame clocks not yet processed: a 2-buffer DMA ring */
static K_SEM_DEFINE(synced, 0, 1);
static atomic_t started;
static bool audio_ok;

static void tmr_isr(const void *arg)
{
	nrf_timer_event_clear(NRF_TIMER1, NRF_TIMER_EVENT_COMPARE0);
	nrf_timer_cc_set(NRF_TIMER1, NRF_TIMER_CC_CHANNEL0, OP_FRAME_US); /* after the phased first */
	k_sem_give(&tick);
}

/* Start the frame clock (once): first frame clock after first_us, then every OP_FRAME_US. */
static void clock_start(uint32_t first_us)
{
	if (!atomic_cas(&started, 0, 1)) {
		return;
	}
	nrf_timer_mode_set(NRF_TIMER1, NRF_TIMER_MODE_TIMER);
	nrf_timer_bit_width_set(NRF_TIMER1, NRF_TIMER_BIT_WIDTH_32);
	nrf_timer_prescaler_set(NRF_TIMER1, 4); /* 16 MHz / 2^4 = 1 MHz */
	nrf_timer_cc_set(NRF_TIMER1, NRF_TIMER_CC_CHANNEL0, first_us);
	nrf_timer_shorts_enable(NRF_TIMER1, NRF_TIMER_SHORT_COMPARE0_CLEAR_MASK);
	nrf_timer_int_enable(NRF_TIMER1, NRF_TIMER_INT_COMPARE0_MASK);
	nrf_timer_task_trigger(NRF_TIMER1, NRF_TIMER_TASK_START);
}

/* Net -> app: the latch sync. Runs in the IPC receive context; the phase is set here, on arrival. */
static void on_net(const uint8_t *m, size_t len)
{
	if (len != OP_SYNC_LEN) {
		return;
	}
	int32_t first = (int32_t)sys_get_le16(m) - CONFIG_OP_PACK_FRAME_LEAD_US;

	while (first < MIN_FIRST_US) {
		first += OP_FRAME_US;
	}
	clock_start(first);
	k_sem_give(&synced);
}

static void frame_thread(void *a, void *b, void *c)
{
	uint8_t f[OP_FRAME_LEN] = {0};
	int16_t pcm[OP_AUDIO_FRAME_SAMPLES];
	uint8_t seq = 0;

	for (;;) {
		k_sem_take(&tick, K_FOREVER);
		if (!audio_ok || op_audio_read_frame(pcm) != 0) {
			memset(pcm, 0, sizeof(pcm)); /* no input (DK until Phase 5, end of WAV): silence */
		}
		f[0] = seq++;
		/* f[1..2] status: telemetry (PK-10) lands with the battery/peak sensors */
		adpcm6_encode(pcm, &f[HDR]);
		(void)op_ipc_send(f, sizeof(f)); /* a lost frame shows as a seq skip on air */
	}
}

K_THREAD_DEFINE(op_pack_frame, 1024, frame_thread, NULL, NULL, NULL, CONFIG_OP_PACK_FRAME_PRIO, 0, 0);

int op_pack_start(void)
{
	int err;

	audio_ok = op_audio_start() == 0;
	IRQ_CONNECT(TIMER1_IRQn, 1, tmr_isr, NULL, 0);
	irq_enable(TIMER1_IRQn);
	err = op_ipc_init(on_net);
	if (err != 0) {
		return err;
	}
	err = k_sem_take(&synced, K_MSEC(100));
	if (err != 0) {
		clock_start(OP_FRAME_US); /* no sync: transmit unaligned (the lead is not guaranteed) */
	}
	printk("PACK audio in %s, frame lead %d us%s, prio %d\n",
	       audio_ok ? "on" : "off (no backend or no input WAV): silence", CONFIG_OP_PACK_FRAME_LEAD_US,
	       err ? " NOT ALIGNED (no latch sync)" : "", CONFIG_OP_PACK_FRAME_PRIO);
	return 0;
}
