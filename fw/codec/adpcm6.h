/* ADPCM-6 codec (ADR-0005). Pure C, no Zephyr deps. Bit-exact to sim/codec/codec.py. */
#ifndef OPENPACK_ADPCM6_H
#define OPENPACK_ADPCM6_H

#include <stdint.h>

#define ADPCM6_FRAME_SAMPLES 48
#define ADPCM6_FRAME_BYTES   39 /* 3 B header (pred int16 BE, step idx u8) + 36 B of 6-bit codes */

/* Encode 48 samples into 39 bytes. */
void adpcm6_encode(const int16_t pcm[ADPCM6_FRAME_SAMPLES], uint8_t out[ADPCM6_FRAME_BYTES]);

/* Decode 39 bytes into 48 samples. */
void adpcm6_decode(const uint8_t in[ADPCM6_FRAME_BYTES], int16_t pcm[ADPCM6_FRAME_SAMPLES]);

#endif
