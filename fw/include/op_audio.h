/* OpenPack audio I/O (FW-3). One interface, backend chosen by Kconfig:
 * WAV file (native_sim, nrf5340bsim) or I2S (nrf5340dk, stubbed until Phase 5).
 * Audio is 48 kHz mono signed 16-bit.
 */
#ifndef OP_AUDIO_H
#define OP_AUDIO_H

#include <stdint.h>

#define OP_AUDIO_RATE_HZ       48000
#define OP_AUDIO_FRAME_SAMPLES 48 /* 1 ms input frame */
#define OP_AUDIO_BLOCK_SAMPLES CONFIG_OP_DAC_BLOCK_SAMPLES

/* Open the backend. 0 on success, negative errno on failure
 * (-ENOTSUP: I2S backend not implemented yet). */
int op_audio_start(void);

/* Read one frame of OP_AUDIO_FRAME_SAMPLES samples. 0 on success,
 * -ENODATA at end of input, other negative errno on failure. */
int op_audio_read_frame(int16_t *frame);

/* Write one DAC block of OP_AUDIO_BLOCK_SAMPLES samples. 0 or negative errno. */
int op_audio_write_block(const int16_t *block);

#endif /* OP_AUDIO_H */
