/* Receiver app core: one merged frame per 1 ms from the net core (FW-2, op_frame endpoint) ->
 * ADPCM-6 decode, or PLC for a frame with no valid copy (RX-6) -> jitter slot -> DAC, with the
 * DAC clock steered by the PI loop on the slot fill (RX-7, ADR-0013).
 *
 * Per frame, first thing: read the DAC position (op_aclk_played_q16), so the fill the loop sees
 * is the slot fill at frame arrival. A new lock epoch re-primes the slot and clears the PLC
 * history; the PI integrator (the crystal offset) is kept across re-locks.
 *
 * Counts, as in #23: frames, valid, lost, per-copy successes, seq skips (two consecutive valid
 * frames whose seq advances by more than 1; a repeated seq is the pack's own underrun, not a skip).
 * Plus RX-6/RX-7: plc (concealed frames), fill at arrival (mean/min/max, milli-samples), applied
 * clock correction (ppb), slips (slot underruns/overruns, cumulative), DAC samples played.
 * One RXAPP line per second of the counts in that second (tests/bsim/rx/check*.py parse them).
 */
#include <zephyr/kernel.h>
#include "op_rx.h"
#include "op_audio.h"
#include "adpcm6.h"
#include "op_clk.h"
#include "op_jslot.h"
#include "op_plc.h"

#define HDR    3 /* AIR-3: seq u8, status u16; then codec_state + audio = one ADPCM-6 frame */
#define TARGET CONFIG_OP_RX_SLOT_TARGET_SAMPLES

BUILD_ASSERT(OP_FRAME_LEN - HDR == ADPCM6_FRAME_BYTES, "AIR-3 v1 payload is one ADPCM-6 frame");
BUILD_ASSERT(ADPCM6_FRAME_SAMPLES == OP_JSLOT_FRAME && OP_PLC_N == OP_JSLOT_FRAME, "1 ms frames");

struct stats {
	uint32_t frames, valid, lost, a_ok, b_ok, skips, plc;
	int32_t rssi_sum;
	int64_t fill_sum; /* Q16 */
	int64_t ppb_sum;
	int32_t fill_min, fill_max;
};

static struct stats st;
static uint8_t last_seq, last_epoch;
static bool last_valid;
static struct op_jslot slot;
static struct op_plc plc;
static struct op_clk pi;
static int32_t ppb;
static bool audio_ok;
static uint64_t dac_samples;

static void stats_clear(struct stats *s)
{
	*s = (struct stats){.fill_min = INT32_MAX, .fill_max = INT32_MIN};
}

static void dac_out(const int16_t *blk, uint16_t n, void *ctx)
{
	ARG_UNUSED(ctx);
	dac_samples += n;
	if (audio_ok) {
		(void)op_audio_write_block(blk);
	}
}

static void on_frame(const uint8_t *data, size_t len)
{
	const struct op_rx_msg *m = (const struct op_rx_msg *)data;
	uint64_t played = op_aclk_played_q16();
	int16_t pcm[ADPCM6_FRAME_SAMPLES], out[ADPCM6_FRAME_SAMPLES];
	bool valid;
	int32_t err;

	if (len != sizeof(*m)) {
		return;
	}
	valid = m->flags & OP_RX_VALID;
	if (m->epoch != last_epoch) {
		op_jslot_unprime(&slot);
		op_plc_init(&plc);
	}
	err = op_jslot_arrive(&slot, played, NULL);
	ppb = op_aclk_set_ppb(op_clk_update(&pi, err));
	if (valid) {
		adpcm6_decode(&m->frame[HDR], pcm);
	}
	op_plc_frame(&plc, valid ? pcm : NULL, out);
	op_jslot_write(&slot, out);
	(void)op_jslot_drain(&slot, played, OP_AUDIO_BLOCK_SAMPLES, dac_out, NULL);

	unsigned int key = irq_lock();
	int32_t fill = err + (TARGET << 16);

	st.frames++;
	st.fill_sum += fill;
	st.ppb_sum += ppb;
	st.fill_min = MIN(st.fill_min, fill);
	st.fill_max = MAX(st.fill_max, fill);
	if (m->epoch != last_epoch) {
		last_epoch = m->epoch;
		last_valid = false;
	}
	if (valid) {
		st.valid++;
		st.a_ok += !!(m->flags & OP_RX_A_OK);
		st.b_ok += !!(m->flags & OP_RX_B_OK);
		st.rssi_sum += m->rssi;
		st.skips += last_valid && (uint8_t)(m->frame[0] - last_seq) > 1;
		last_seq = m->frame[0];
		last_valid = true;
	} else {
		st.lost++;
		st.plc++;
		last_valid = false;
	}
	irq_unlock(key);
}

static int32_t milli(int64_t q16)
{
	return (int32_t)(q16 * 1000 / 65536);
}

static void report(struct k_work *w)
{
	unsigned int key = irq_lock();
	struct stats s = st;
	uint8_t ep = last_epoch;
	uint32_t under = slot.under, over = slot.over;
	uint64_t dac = dac_samples;
	int32_t corr = ppb;

	stats_clear(&st);
	irq_unlock(key);
	printk("RXAPP t_ms=%u epoch=%u frames=%u valid=%u lost=%u a_ok=%u b_ok=%u skips=%u rssi=%d "
	       "plc=%u fill_mean_ms=%d fill_min_ms=%d fill_max_ms=%d ppb=%d ppb_mean=%d "
	       "under=%u over=%u dac=%llu\n",
	       (uint32_t)k_uptime_get(), ep, s.frames, s.valid, s.lost, s.a_ok, s.b_ok, s.skips,
	       s.valid ? s.rssi_sum / (int32_t)s.valid : 0, s.plc,
	       s.frames ? milli(s.fill_sum / s.frames) : 0, s.frames ? milli(s.fill_min) : 0,
	       s.frames ? milli(s.fill_max) : 0, corr,
	       s.frames ? (int32_t)(s.ppb_sum / s.frames) : 0, under, over, dac);
}

static K_WORK_DEFINE(report_work, report);

static void expiry(struct k_timer *t)
{
	k_work_submit(&report_work);
}

static K_TIMER_DEFINE(report_timer, expiry, NULL);

int op_rx_app_start(void)
{
	int err;

	stats_clear(&st);
	op_jslot_init(&slot, TARGET, TARGET + 2 * OP_JSLOT_FRAME);
	op_plc_init(&plc);
	op_clk_init(&pi, CONFIG_OP_RX_CLK_KP_PPB, CONFIG_OP_RX_CLK_KI_PPB, CONFIG_OP_RX_CLK_LIM_PPB);
	audio_ok = op_audio_start() == 0;
	printk("RXAPP_CFG audio out %s, slot target %d samples, kp %d ki %d ppb\n",
	       audio_ok ? "on" : "off (no backend or no input WAV)", TARGET,
	       CONFIG_OP_RX_CLK_KP_PPB, CONFIG_OP_RX_CLK_KI_PPB);
	err = op_aclk_start();
	if (err == 0) {
		err = op_ipc_init(on_frame);
	}
	if (err == 0) {
		k_timer_start(&report_timer, K_SECONDS(1), K_SECONDS(1));
	}
	return err;
}
