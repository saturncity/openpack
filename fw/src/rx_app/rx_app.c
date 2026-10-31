/* Receiver app core: consumes one merged frame per 1 ms from the net core (FW-2, op_frame endpoint).
 * Until the jitter buffer, PLC and DAC land (RX-6, RX-7, #24+), it only counts: frames, valid,
 * lost (no valid copy), per-copy successes, and seq skips (two consecutive valid frames whose seq
 * advances by more than 1 = a frame the pack sent that never came out of the merge). The pack
 * repeats a seq when its source underruns, so a repeat is not a skip. Prints one RXAPP line per
 * second of the counts in that second (tests/bsim/rx/check.py parses them).
 */
#include <zephyr/kernel.h>
#include "op_rx.h"

struct stats {
	uint32_t frames, valid, lost, a_ok, b_ok, skips;
	int32_t rssi_sum;
};

static struct stats st;
static uint8_t last_seq, last_epoch;
static bool last_valid;

static void on_frame(const uint8_t *data, size_t len)
{
	const struct op_rx_msg *m = (const struct op_rx_msg *)data;

	if (len != sizeof(*m)) {
		return;
	}
	unsigned int key = irq_lock();

	st.frames++;
	if (m->epoch != last_epoch) {
		last_epoch = m->epoch;
		last_valid = false;
	}
	if (m->flags & OP_RX_VALID) {
		st.valid++;
		st.a_ok += !!(m->flags & OP_RX_A_OK);
		st.b_ok += !!(m->flags & OP_RX_B_OK);
		st.rssi_sum += m->rssi;
		st.skips += last_valid && (uint8_t)(m->frame[0] - last_seq) > 1;
		last_seq = m->frame[0];
		last_valid = true;
	} else {
		st.lost++;
		last_valid = false;
	}
	irq_unlock(key);
}

static void report(struct k_work *w)
{
	unsigned int key = irq_lock();
	struct stats s = st;
	uint8_t ep = last_epoch;

	st = (struct stats){0};
	irq_unlock(key);
	printk("RXAPP t_ms=%u epoch=%u frames=%u valid=%u lost=%u a_ok=%u b_ok=%u skips=%u rssi=%d\n",
	       (uint32_t)k_uptime_get(), ep, s.frames, s.valid, s.lost, s.a_ok, s.b_ok, s.skips,
	       s.valid ? s.rssi_sum / (int32_t)s.valid : 0);
}

static K_WORK_DEFINE(report_work, report);

static void expiry(struct k_timer *t)
{
	k_work_submit(&report_work);
}

static K_TIMER_DEFINE(report_timer, expiry, NULL);

int op_rx_app_start(void)
{
	int err = op_ipc_init(on_frame);

	if (err == 0) {
		k_timer_start(&report_timer, K_SECONDS(1), K_SECONDS(1));
	}
	return err;
}
