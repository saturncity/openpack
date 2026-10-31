#include "adpcm6.h"

#define BITS   6
#define M      (1 << (BITS - 1)) /* sign bit / magnitude levels = 32 */
#define NSTEPS 89

static const int16_t steps[NSTEPS] = {
	7, 8, 9, 10, 11, 12, 13, 14, 16, 17, 19, 21, 23, 25, 28, 31, 34, 37, 41, 45, 50, 55, 60, 66,
	73, 80, 88, 97, 107, 118, 130, 143, 157, 173, 190, 209, 230, 253, 279, 307, 337, 371, 408,
	449, 494, 544, 598, 658, 724, 796, 876, 963, 1060, 1166, 1282, 1411, 1552, 1707, 1878, 2066,
	2272, 2499, 2749, 3024, 3327, 3660, 4026, 4428, 4871, 5358, 5894, 6484, 7132, 7845, 8630,
	9493, 10442, 11487, 12635, 13899, 15289, 16818, 18500, 20350, 22385, 24623, 27086, 29794, 32767};
static const int8_t idx_adj[8] = {-1, -1, -1, -1, 2, 4, 6, 8};

static int32_t clamp(int32_t x, int32_t lo, int32_t hi)
{
	return x < lo ? lo : x > hi ? hi : x;
}

/* Signed reconstructed delta for a code; magnitude (0..31) via *mag. */
static int32_t recon(unsigned code, int32_t step, unsigned *mag)
{
	unsigned m = code & (M - 1);
	int32_t d = step * (int32_t)(2 * m + 1) / M; /* non-negative: same as Python // */

	*mag = m;
	return (code & M) ? -d : d;
}

void adpcm6_encode(const int16_t pcm[ADPCM6_FRAME_SAMPLES], uint8_t out[ADPCM6_FRAME_BYTES])
{
	int32_t sum = 0;

	for (int i = 1; i < ADPCM6_FRAME_SAMPLES; i++) {
		int32_t d = (int32_t)pcm[i] - pcm[i - 1];

		sum += d < 0 ? -d : d;
	}

	int32_t mad = sum / (ADPCM6_FRAME_SAMPLES - 1);
	int idx = NSTEPS - 1;

	for (int i = 0; i < NSTEPS; i++) {
		if (steps[i] >= mad) {
			idx = i;
			break;
		}
	}

	int32_t pred = pcm[0];

	out[0] = (uint8_t)((pcm[0] >> 8) & 255);
	out[1] = (uint8_t)(pcm[0] & 255);
	out[2] = (uint8_t)idx;
	for (int i = 3; i < ADPCM6_FRAME_BYTES; i++) {
		out[i] = 0;
	}

	/* code[0] is padding (0); codes are MSB-first, 6 bits each. */
	for (int i = 1; i < ADPCM6_FRAME_SAMPLES; i++) {
		int32_t step = steps[idx];
		int32_t diff = (int32_t)pcm[i] - pred;
		int32_t ad = diff < 0 ? -diff : diff;
		int32_t mg = ad * M / (2 * step);
		unsigned mag, code;

		if (mg > M - 1) {
			mg = M - 1;
		}
		code = (unsigned)mg | (diff < 0 ? M : 0);
		pred = clamp(pred + recon(code, step, &mag), -32768, 32767);
		idx = clamp(idx + idx_adj[mag * 8 / M], 0, NSTEPS - 1);

		unsigned bit = i * BITS;

		for (int b = 0; b < BITS; b++, bit++) {
			if (code & (1u << (BITS - 1 - b))) {
				out[3 + bit / 8] |= (uint8_t)(0x80 >> (bit % 8));
			}
		}
	}
}

void adpcm6_decode(const uint8_t in[ADPCM6_FRAME_BYTES], int16_t pcm[ADPCM6_FRAME_SAMPLES])
{
	int32_t pred = (int16_t)(((unsigned)in[0] << 8) | in[1]);
	int idx = in[2] > NSTEPS - 1 ? NSTEPS - 1 : in[2];

	pcm[0] = (int16_t)pred;
	for (int i = 1; i < ADPCM6_FRAME_SAMPLES; i++) {
		unsigned code = 0, bit = i * BITS, mag;

		for (int b = 0; b < BITS; b++, bit++) {
			code = (code << 1) | ((in[3 + bit / 8] >> (7 - bit % 8)) & 1);
		}
		pred = clamp(pred + recon(code, steps[idx], &mag), -32768, 32767);
		idx = clamp(idx + idx_adj[mag * 8 / M], 0, NSTEPS - 1);
		pcm[i] = (int16_t)pred;
	}
}
