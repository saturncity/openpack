/* Pack app core pipeline (FW-2..FW-4): per audio frame (48 samples = 1 ms) op_audio_read_frame ->
 * ADPCM-6 -> AIR-3 payload -> op_ipc_send. The net core puts the newest frame on air (net/sched.c).
 *
 * Pacing is the audio frame clock, an interrupt, never a kernel timeout (#87). A k_timer runs on the
 * 32768 Hz RTC: 1 ms = 33 ticks = 1007 us, so the frame phase sweeps past the net core's latch every
 * 142 frames, and any other thread's timeout due within 3 ticks of a frame (nrf_rtc_timer
 * MIN_CYCLES_FROM_NOW) pushed that frame 61 us late; near the latch the late frame missed its slot
 * and was overwritten by the next one: a repeat, then a seq skip.
 *
 * Frame clock (#97): on silicon the I2S RXPTRUPD event, one per 48-sample buffer (op_audio_i2s.c),
 * clocked by HFCLKAUDIO. Without I2S (bsim, WAV backend) TIMER1 at 16 MHz stands in, from the same
 * crystal as the net core's TIMER0, plus a test-only rate offset (OP_TEST_FCLK_PPB, bsim
 * -op_fclk_ppb). Phase: the net core sends once, at start, the time to its next latch
 * (op_sched_sync); the first frame clock is placed CONFIG_OP_PACK_FRAME_LEAD_US before a latch (I2S:
 * a TIMER1 one-shot starts I2S there; its first frame completes 1 ms later, at the same phase).
 * That lead is the frame thread's deadline for read + encode + IPC: under any load that leaves the
 * thread its deadline, no frame is skipped.
 *
 * Holding the lead (#97, ADR-0022): HFCLKAUDIO cannot hit 12.288 MHz (FREQ 39846 = +0.371 ppm), so the
 * frame clock drifts 1.34 ms/h against TIMER0. Every OP_PACK_LEAD_REPORT_FRAMES frames the net core
 * reports the earliest frame's latch margin; op_lead (PI, op_clk.c) turns the drift from the first
 * report into a rate correction, dithered per frame between whole HFCLKAUDIO steps. The TIMER1
 * stand-in applies the same steps to its period.
 *
 * Time diversity (ADR-0017): with the pack's `td` setting on, op_td_tx appends frame n-2's td_audio
 * (codec_state + audio, 39 B) to frame n, an 81 B payload (AIR-3); the net core times it per length.
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
#include "op_td.h"
#include "op_lead.h"
#if defined(CONFIG_OP_TEST_SCHED_REPORT)
#include "nsi_hw_scheduler.h" /* bsim: device time, for run.py (a) frame clock -> TXEN */
#endif

#define HDR 3 /* AIR-3: seq u8, status u16 LE; then one ADPCM-6 frame (codec_state + audio) */
#define MIN_FIRST_US 50 /* first frame clock at least this far after the sync arrives */
#define TICKS_US     16 /* TIMER1 at 16 MHz */
#define FRAME_Q32    ((int64_t)OP_FRAME_US * TICKS_US << 32)
#define Q32_PPB_E3   68719477LL /* one frame (16000 ticks) * 1 ppb in Q32 ticks, x1000 */

/* Test only (bsim, src/app/bsim_fclk.c): frame clock rate offset and open loop from the command line */
#if defined(CONFIG_ARCH_POSIX)
extern int op_fclk_ppb;
extern bool op_lead_open;
#define FCLK_PPB  op_fclk_ppb
#define LEAD_OPEN op_lead_open
#else
#define FCLK_PPB  CONFIG_OP_TEST_FCLK_PPB
#define LEAD_OPEN false
#endif

BUILD_ASSERT(OP_FRAME_LEN == HDR + ADPCM6_FRAME_BYTES, "AIR-3 v1 payload is one ADPCM-6 frame");
BUILD_ASSERT(ADPCM6_FRAME_SAMPLES == OP_AUDIO_FRAME_SAMPLES && OP_FRAME_US == 1000, "1 ms frames");
BUILD_ASSERT(CONFIG_OP_PACK_FRAME_LEAD_US > 0 && CONFIG_OP_PACK_FRAME_LEAD_US < OP_FRAME_US);

static K_SEM_DEFINE(tick, 0, 2); /* frame clocks not yet processed: a 2-buffer DMA ring */
static K_SEM_DEFINE(synced, 0, 1);
static atomic_t started;
static bool audio_ok, i2s_clock;
#define I2S_CLOCK (IS_ENABLED(CONFIG_OP_AUDIO_I2S) && i2s_clock) /* compiled out without I2S */
static uint32_t fclk_hw_mod; /* test only: device time of the last frame clock, mod OP_FRAME_US */
static struct op_lead lead;
static int32_t steps; /* HFCLKAUDIO steps this frame */
static uint64_t next_q32; /* TIMER1 stand-in: next frame clock, ticks since start, Q32 */
static uint32_t reports;

/* Once per frame, in the frame clock's interrupt: this frame's rate steps, then wake the thread. */
static void frame_clock(void)
{
	steps = op_lead_frame(&lead);
	if (I2S_CLOCK) {
		op_audio_i2s_aclk_steps(steps);
	}
	k_sem_give(&tick);
}

static void tmr_isr(const void *arg)
{
	nrf_timer_event_clear(NRF_TIMER1, NRF_TIMER_EVENT_COMPARE0);
	if (I2S_CLOCK) { /* one-shot at the phased instant: I2S takes over the frame clock */
		nrf_timer_int_disable(NRF_TIMER1, NRF_TIMER_INT_COMPARE0_MASK);
		nrf_timer_task_trigger(NRF_TIMER1, NRF_TIMER_TASK_STOP);
		(void)op_audio_i2s_rx_start(frame_clock);
		return;
	}
#if defined(CONFIG_OP_TEST_SCHED_REPORT)
	/* now - (count - the compare that fired) = the frame clock instant */
	nrf_timer_task_trigger(NRF_TIMER1, nrf_timer_capture_task_get(NRF_TIMER_CC_CHANNEL1));
	fclk_hw_mod = (uint32_t)((nsi_hws_get_time() -
				  (nrf_timer_cc_get(NRF_TIMER1, NRF_TIMER_CC_CHANNEL1) -
				   nrf_timer_cc_get(NRF_TIMER1, NRF_TIMER_CC_CHANNEL0)) / TICKS_US) %
				 OP_FRAME_US);
#endif
	frame_clock();
	/* Next frame clock: 1 ms * (1 - offset - steps) on. The counter free-runs (no CLEAR short) and
	 * the compare is absolute, so the sub-tick fraction is never lost (bsim's TIMER rounds every
	 * CLEAR-relative period up to a whole us); the 32-bit counter wraps with CC.
	 */
	next_q32 += FRAME_Q32 - (int64_t)(FCLK_PPB + steps * OP_ACLK_STEP_PPB) * Q32_PPB_E3 / 1000;
	nrf_timer_cc_set(NRF_TIMER1, NRF_TIMER_CC_CHANNEL0, (uint32_t)(next_q32 >> 32));
}

/* Start the frame clock (once): first frame clock after first_us, then every OP_FRAME_US. */
static void clock_start(uint32_t first_us)
{
	if (!atomic_cas(&started, 0, 1)) {
		return;
	}
	nrf_timer_mode_set(NRF_TIMER1, NRF_TIMER_MODE_TIMER);
	nrf_timer_bit_width_set(NRF_TIMER1, NRF_TIMER_BIT_WIDTH_32);
	nrf_timer_prescaler_set(NRF_TIMER1, 0); /* 16 MHz */
	nrf_timer_task_trigger(NRF_TIMER1, NRF_TIMER_TASK_CLEAR);
	next_q32 = (uint64_t)first_us * TICKS_US << 32;
	nrf_timer_cc_set(NRF_TIMER1, NRF_TIMER_CC_CHANNEL0, first_us * TICKS_US);
	nrf_timer_int_enable(NRF_TIMER1, NRF_TIMER_INT_COMPARE0_MASK);
	nrf_timer_task_trigger(NRF_TIMER1, NRF_TIMER_TASK_START);
}

/* Net -> app, in the IPC receive context: the lead report (#97), or the latch sync (the phase is set
 * here, on arrival).
 */
static void on_net(const uint8_t *m, size_t len)
{
	if (len == OP_LEAD_LEN) {
		int32_t early = (int16_t)sys_get_le16(m), late = (int16_t)sys_get_le16(&m[2]);
		int32_t ppb = op_lead_report(&lead, early);

		if (IS_ENABLED(CONFIG_OP_TEST_SCHED_REPORT) && ++reports % 10 == 0) { /* 1/s, bsim only */
			printk("PACK_LEAD reports=%u ref_us=%d margin_us=%d late_us=%d ppb=%d steps=%d "
			       "fclk_ppb=%d open=%d\n",
			       reports, lead.ref, early, late, ppb, steps, FCLK_PPB, LEAD_OPEN);
		}
		return;
	}
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
	uint8_t f[OP_FRAME_LEN] = {0}, p[OP_FRAME_TD_LEN];
	int16_t pcm[OP_AUDIO_FRAME_SAMPLES];
	uint8_t seq = 0;
	static struct op_td_tx td; /* zeroed: no frame n-2 yet */

	for (;;) {
		k_sem_take(&tick, K_FOREVER);
		if (!audio_ok || op_audio_read_frame(pcm) != 0) {
			memset(pcm, 0, sizeof(pcm)); /* no input (DK until Phase 5, end of WAV): silence */
		}
		f[0] = seq++;
		/* f[1..2] status: telemetry (PK-10) lands with the battery/peak sensors */
		adpcm6_encode(pcm, &f[HDR]);
		/* a lost frame shows as a seq skip on air */
		(void)op_ipc_send(p, op_td_tx(&td, f, op_pack_td(), p));
		if (IS_ENABLED(CONFIG_OP_TEST_SCHED_REPORT) && seq == 0) { /* every 256 frames */
			printk("PACK_FCLK fclk_hw_mod_us=%u\n", fclk_hw_mod);
		}
	}
}

K_THREAD_DEFINE(op_pack_frame, 1024, frame_thread, NULL, NULL, NULL, CONFIG_OP_PACK_FRAME_PRIO, 0, 0);

int op_pack_start(void)
{
	int err;

	audio_ok = op_audio_start() == 0;
	i2s_clock = IS_ENABLED(CONFIG_OP_AUDIO_I2S) && audio_ok;
	op_lead_init(&lead, CONFIG_OP_PACK_LEAD_KP_PPB, CONFIG_OP_PACK_LEAD_KI_PPB,
		     CONFIG_OP_PACK_LEAD_LIM_PPB, LEAD_OPEN);
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
	printk("PACK audio in %s, frame clock %s, frame lead %d us%s, prio %d, lead loop %s "
	       "(fclk offset %d ppb)\n",
	       audio_ok ? "on" : "off (no backend or no input WAV): silence",
	       i2s_clock ? "I2S RXPTRUPD" : "TIMER1", CONFIG_OP_PACK_FRAME_LEAD_US,
	       err ? " NOT ALIGNED (no latch sync)" : "", CONFIG_OP_PACK_FRAME_PRIO,
	       LEAD_OPEN ? "OPEN (test)" : "on", FCLK_PPB);
	return 0;
}
