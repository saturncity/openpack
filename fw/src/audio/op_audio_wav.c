/* WAV file backend (native_sim, nrf5340bsim). Host file I/O is in op_wav_host_bottom.c.
 * Paths: env OP_AUDIO_IN / OP_AUDIO_OUT, else Kconfig defaults. */
#include <errno.h>
#include <stddef.h>
#include "op_audio.h"
#include "op_wav_host.h"

static short *in_buf;
static unsigned long in_n, in_pos;

int op_audio_start(void)
{
	const char *in = op_wav_host_getenv("OP_AUDIO_IN");
	const char *out = op_wav_host_getenv("OP_AUDIO_OUT");

	if (in_buf) {
		op_wav_host_free(in_buf);
		in_buf = NULL;
	}
	in_pos = 0;
	if (op_wav_host_load(in ? in : CONFIG_OP_AUDIO_WAV_IN, &in_buf, &in_n)) {
		return -EIO;
	}
	return op_wav_host_out_open(out ? out : CONFIG_OP_AUDIO_WAV_OUT) ? -EIO : 0;
}

int op_audio_read_frame(int16_t *frame)
{
	if (!in_buf) {
		return -ENODEV;
	}
	if (in_pos + OP_AUDIO_FRAME_SAMPLES > in_n) {
		return -ENODATA;
	}
	for (int i = 0; i < OP_AUDIO_FRAME_SAMPLES; i++) {
		frame[i] = in_buf[in_pos + i];
	}
	in_pos += OP_AUDIO_FRAME_SAMPLES;
	return 0;
}

int op_audio_write_block(const int16_t *block)
{
	return op_wav_host_out_append(block, OP_AUDIO_BLOCK_SAMPLES) ? -EIO : 0;
}
