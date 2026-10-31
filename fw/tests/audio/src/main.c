#include <zephyr/ztest.h>
#include <math.h>

#define PI_ 3.14159265358979323846
#include "op_audio.h"
#include "op_wav_host.h"

#define NFRAMES 10
#define N (NFRAMES * OP_AUDIO_FRAME_SAMPLES)

static int16_t sine[N];

ZTEST(op_audio, test_roundtrip)
{
	int16_t frame[OP_AUDIO_FRAME_SAMPLES];
	short *out;
	unsigned long n;
	int frames = 0;

	for (int i = 0; i < N; i++) {
		sine[i] = (int16_t)lrint(12000.0 * sin(2 * PI_ * 1000.0 * i / OP_AUDIO_RATE_HZ));
	}
	zassert_equal(op_wav_host_save("op_test_in.wav", sine, N), 0);
	zassert_equal(op_audio_start(), 0);

	while (op_audio_read_frame(frame) == 0) {
		zassert_equal(frames < NFRAMES, true);
		for (int off = 0; off < OP_AUDIO_FRAME_SAMPLES; off += OP_AUDIO_BLOCK_SAMPLES) {
			int16_t blk[OP_AUDIO_BLOCK_SAMPLES];
			int len = MIN(OP_AUDIO_BLOCK_SAMPLES, OP_AUDIO_FRAME_SAMPLES - off);

			for (int i = 0; i < OP_AUDIO_BLOCK_SAMPLES; i++) {
				blk[i] = i < len ? frame[off + i] : 0;
			}
			zassert_equal(op_audio_write_block(blk), 0);
		}
		frames++;
	}
	zassert_equal(frames, NFRAMES);
	zassert_equal(op_audio_read_frame(frame), -ENODATA);

	zassert_equal(op_wav_host_load("op_test_out.wav", &out, &n), 0);
	zassert_true(n >= N);
	zassert_mem_equal(out, sine, sizeof(sine));
	op_wav_host_free(out);
}

ZTEST_SUITE(op_audio, NULL, NULL, NULL, NULL, NULL);
