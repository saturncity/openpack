/* Time diversity (fw/src/td/op_td.c): AIR-3 td_audio pack/unpack, RX-4 recovery from packet n+2. */
#include <string.h>
#include <zephyr/ztest.h>
#include "op_td.h"

#define N 40

/* Frame n: seq n, status 0x1200 + n, codec_state + audio a pattern unique to n. */
static void frame(int n, uint8_t f[OP_FRAME_LEN])
{
	f[0] = (uint8_t)n;
	f[1] = (uint8_t)n;
	f[2] = 0x12;
	for (int i = OP_TD_HDR; i < OP_FRAME_LEN; i++) {
		f[i] = (uint8_t)(n * 31 + i * 7 + 1);
	}
}

ZTEST(td, test_off_is_v1_frame)
{
	struct op_td_tx tx;
	uint8_t f[OP_FRAME_LEN], out[OP_FRAME_TD_LEN];

	op_td_tx_init(&tx);
	for (int n = 0; n < 5; n++) {
		frame(n, f);
		memset(out, 0xee, sizeof(out));
		zassert_equal(op_td_tx(&tx, f, false, out), OP_FRAME_LEN);
		zassert_mem_equal(out, f, OP_FRAME_LEN);
		zassert_equal(out[OP_FRAME_LEN], 0xee, "TD off writes 42 B only");
	}
}

ZTEST(td, test_on_carries_frame_n_minus_2)
{
	struct op_td_tx tx;
	uint8_t f[OP_FRAME_LEN], old[OP_FRAME_LEN], out[OP_FRAME_TD_LEN], zero[OP_TD_LEN] = {0};

	zassert_equal(OP_FRAME_TD_LEN, 81, "AIR-3: 42 + 39");
	op_td_tx_init(&tx);
	for (int n = 0; n < N; n++) {
		frame(n, f);
		zassert_equal(op_td_tx(&tx, f, true, out), OP_FRAME_TD_LEN);
		zassert_mem_equal(out, f, OP_FRAME_LEN);
		if (n < OP_TD_D) {
			zassert_mem_equal(&out[OP_FRAME_LEN], zero, OP_TD_LEN, "no frame n-2 yet");
		} else {
			frame(n - OP_TD_D, old);
			zassert_mem_equal(&out[OP_FRAME_LEN], &old[OP_TD_HDR], OP_TD_LEN, "packet %d", n);
		}
	}
}

ZTEST(td, test_turn_on_has_no_stale_audio)
{
	struct op_td_tx tx;
	uint8_t f[OP_FRAME_LEN], old[OP_FRAME_LEN], out[OP_FRAME_TD_LEN];

	op_td_tx_init(&tx);
	for (int n = 0; n < 7; n++) {
		frame(n, f);
		(void)op_td_tx(&tx, f, false, out);
	}
	frame(7, f);
	(void)op_td_tx(&tx, f, true, out);
	frame(5, old);
	zassert_mem_equal(&out[OP_FRAME_LEN], &old[OP_TD_HDR], OP_TD_LEN);
}

/* Pack -> loss pattern -> receiver: every frame comes out 2 packets late; a frame lost on both copies is
 * recovered from packet n+2 bit-exact (bar the status word, which is packet n+2's); lost if n+2 is lost too.
 */
ZTEST(td, test_recovery)
{
	static const bool lost[N] = {[5] = true, [9] = true, [11] = true, [20] = true, [21] = true,
				     [22] = true, [30] = true, [32] = true, [34] = true};
	struct op_td_tx tx;
	struct op_td_rx rx;
	uint8_t f[OP_FRAME_LEN], want[OP_FRAME_LEN], pkt[OP_FRAME_TD_LEN], out[OP_FRAME_LEN];
	int ok = 0, rec = 0, gone = 0;

	op_td_tx_init(&tx);
	op_td_rx_init(&rx);
	for (int k = 0; k < N; k++) {
		uint16_t tag = 0xffff;
		enum op_td_res r;

		frame(k, f);
		(void)op_td_tx(&tx, f, true, pkt);
		r = op_td_rx(&rx, lost[k] ? NULL : pkt, 100 + k, out, &tag);
		if (k < OP_TD_D) {
			zassert_equal(r, OP_TD_NONE, "packet %d: nothing to play yet", k);
			continue;
		}
		int n = k - OP_TD_D;

		zassert_equal(tag, 100 + n, "tag of packet %d comes back with frame %d", n, n);
		frame(n, want);
		if (!lost[n]) {
			zassert_equal(r, OP_TD_OK, "frame %d", n);
			zassert_mem_equal(out, want, OP_FRAME_LEN);
			ok++;
		} else if (!lost[k]) {
			zassert_equal(r, OP_TD_REC, "frame %d from packet %d", n, k);
			zassert_equal(out[0], (uint8_t)n, "seq");
			zassert_mem_equal(&out[OP_TD_HDR], &want[OP_TD_HDR], OP_TD_LEN, "audio of frame %d", n);
			rec++;
		} else {
			zassert_equal(r, OP_TD_LOST, "frame %d: packets %d and %d lost", n, n, k);
			gone++;
		}
	}
	/* recovered: 5, 11, 21, 22, 34 (packet n+2 arrived); lost: 9, 20, 30, 32 (n+2 lost as well) */
	zassert_equal(rec, 5);
	zassert_equal(gone, 4);
	zassert_equal(ok, N - OP_TD_D - 9);
}

ZTEST(td, test_lost_when_n_plus_2_lost)
{
	struct op_td_tx tx;
	struct op_td_rx rx;
	uint8_t f[OP_FRAME_LEN], pkt[OP_FRAME_TD_LEN], out[OP_FRAME_LEN];
	uint16_t tag;
	enum op_td_res r[12];

	op_td_tx_init(&tx);
	op_td_rx_init(&rx);
	for (int k = 0; k < 12; k++) {
		frame(k, f);
		(void)op_td_tx(&tx, f, true, pkt);
		r[k] = op_td_rx(&rx, (k == 4 || k == 6) ? NULL : pkt, 0, out, &tag);
	}
	zassert_equal(r[6], OP_TD_LOST, "frame 4: packets 4 and 6 lost");
	zassert_equal(r[8], OP_TD_REC, "frame 6 from packet 8");
	zassert_equal(r[7], OP_TD_OK);
}

ZTEST(td, test_reset_restarts_delay)
{
	struct op_td_rx rx;
	uint8_t pkt[OP_FRAME_TD_LEN] = {0}, out[OP_FRAME_LEN];
	uint16_t tag;

	op_td_rx_init(&rx);
	for (int k = 0; k < 5; k++) {
		(void)op_td_rx(&rx, pkt, 0, out, &tag);
	}
	op_td_rx_init(&rx); /* re-lock */
	zassert_equal(op_td_rx(&rx, pkt, 0, out, &tag), OP_TD_NONE);
	zassert_equal(op_td_rx(&rx, pkt, 0, out, &tag), OP_TD_NONE);
	zassert_equal(op_td_rx(&rx, pkt, 0, out, &tag), OP_TD_OK);
}

ZTEST_SUITE(td, NULL, NULL, NULL, NULL, NULL);
