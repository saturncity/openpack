#include <zephyr/ztest.h>
#include "adpcm6.h"
#include "golden.h"

#define NFRAMES 32 /* silence, full-scale, 30-frame sweep */

BUILD_ASSERT(sizeof(golden_pcm_in) == NFRAMES * ADPCM6_FRAME_SAMPLES * 2);
BUILD_ASSERT(sizeof(golden_enc) == NFRAMES * ADPCM6_FRAME_BYTES);
BUILD_ASSERT(sizeof(golden_dec) == sizeof(golden_pcm_in));

static int16_t le16(const unsigned char *p)
{
	return (int16_t)(p[0] | (p[1] << 8));
}

ZTEST(adpcm6, test_encode_matches_golden)
{
	for (int f = 0; f < NFRAMES; f++) {
		int16_t pcm[ADPCM6_FRAME_SAMPLES];
		uint8_t out[ADPCM6_FRAME_BYTES];

		for (int i = 0; i < ADPCM6_FRAME_SAMPLES; i++) {
			pcm[i] = le16(&golden_pcm_in[(f * ADPCM6_FRAME_SAMPLES + i) * 2]);
		}
		adpcm6_encode(pcm, out);
		zassert_mem_equal(out, &golden_enc[f * ADPCM6_FRAME_BYTES], ADPCM6_FRAME_BYTES,
				  "encoder mismatch in frame %d", f);
	}
}

ZTEST(adpcm6, test_decode_matches_golden)
{
	for (int f = 0; f < NFRAMES; f++) {
		int16_t pcm[ADPCM6_FRAME_SAMPLES];

		adpcm6_decode(&golden_enc[f * ADPCM6_FRAME_BYTES], pcm);
		for (int i = 0; i < ADPCM6_FRAME_SAMPLES; i++) {
			zassert_equal(pcm[i], le16(&golden_dec[(f * ADPCM6_FRAME_SAMPLES + i) * 2]),
				      "decoder mismatch frame %d sample %d", f, i);
		}
	}
}

ZTEST_SUITE(adpcm6, NULL, NULL, NULL, NULL, NULL);
