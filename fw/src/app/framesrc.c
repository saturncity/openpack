/* Placeholder frame source on the app core: one AIR-3 frame per 1 ms with an incrementing seq.
 * Replaced by the audio + codec pipeline (op_audio #20, codec #21); exists so the net-core
 * schedule and the IPC path (FW-2) are exercised end to end in bsim. With the pack's `td` setting on
 * (ADR-0017) each payload also carries frame n-2's td_audio (op_td_tx, AIR-3).
 */
#include <zephyr/kernel.h>
#include "op_frame.h"
#include "op_td.h"

static uint8_t seq;
static struct op_td_tx td;

static void tick(struct k_work *w)
{
	uint8_t f[OP_FRAME_LEN] = {0}, p[OP_FRAME_TD_LEN];

	f[0] = seq++;
	(void)op_ipc_send(p, op_td_tx(&td, f, op_pack_td(), p));
}

static K_WORK_DEFINE(work, tick);

static void expiry(struct k_timer *t)
{
	k_work_submit(&work);
}

static K_TIMER_DEFINE(timer, expiry, NULL);

int op_framesrc_start(void)
{
	op_td_tx_init(&td);
	k_timer_start(&timer, K_USEC(OP_FRAME_US), K_USEC(OP_FRAME_US));
	return 0;
}
