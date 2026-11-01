/* RX-5 antenna choice per channel (ADR-0011). One SPDT switch, so the other antenna is only heard
 * when a window is spent on it: every `probe` frames copy A's window, and half a period later copy
 * B's window, listen on the other antenna. Never both copies in one frame, so time/frequency
 * diversity still covers a bad probe. Switch when the other antenna's last-valid RSSI exceeds the
 * current one's by hyst_db (SPEC RX-5). A window that ends without a valid copy on the current
 * antenna ages its stored RSSI by 1 dB, so a dead antenna loses to a live one after hyst_db misses.
 * ADR-0021 adds a miss-triggered switch with a hold (op_ant_set_miss): with wing antennas a hot 3 MHz
 * neighbour blocks the stronger antenna for a few % of windows, too few to age it out.
 * Pure C: no Zephyr dependency (unit tested on native_sim, fw/tests/rx_ant).
 */
#include <string.h>
#include "op_rx.h"

#define RSSI_FLOOR (-127)

void op_ant_init(struct op_ant *s, uint16_t probe_frames, int8_t hyst_db)
{
	memset(s, 0, sizeof(*s));
	s->probe = probe_frames;
	s->hyst_db = hyst_db;
}

uint8_t op_ant_pick(const struct op_ant *s, uint8_t ch, uint32_t frame)
{
	bool probe = s->probe != 0 && frame % s->probe == (ch == 0 ? 0u : s->probe / 2u);

	return probe ? (uint8_t)!s->cur[ch] : s->cur[ch];
}

void op_ant_set_miss(struct op_ant *s, int8_t miss_db, uint16_t hold_frames)
{
	s->miss_db = miss_db;
	s->hold = hold_frames;
}

bool op_ant_report(struct op_ant *s, uint8_t ch, uint8_t ant, bool valid, int8_t rssi_dbm)
{
	uint8_t cur = s->cur[ch];
	uint8_t other = !cur;

	s->ok[ch][ant] = valid;
	if (valid) {
		s->last[ch][ant] = rssi_dbm;
		s->seen[ch][ant] = true;
	} else if (ant == cur && s->seen[ch][cur] && s->last[ch][cur] > RSSI_FLOOR) {
		s->last[ch][cur]--;
	}
	if (ant == cur && s->hold_left[ch] > 0) {
		s->hold_left[ch]--;
	}
	if (!valid && ant == cur && s->miss_db > 0 && s->seen[ch][other] && s->ok[ch][other] &&
	    s->last[ch][other] >= s->last[ch][cur] - s->miss_db) {
		s->cur[ch] = other;
		s->hold_left[ch] = s->hold;
		s->switches++;
		return true;
	}
	if (s->hold_left[ch] > 0) {
		return false;
	}
	if (s->seen[ch][other] &&
	    (!s->seen[ch][cur] || s->last[ch][other] - s->last[ch][cur] >= s->hyst_db)) {
		s->cur[ch] = other;
		s->switches++;
		return true;
	}
	return false;
}
