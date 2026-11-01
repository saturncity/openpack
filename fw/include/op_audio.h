/* OpenPack audio I/O (FW-3). One interface, backend chosen by Kconfig:
 * WAV file (native_sim, nrf5340bsim) or I2S (nrf5340dk, openpack_pack, openpack_rx; silicon bring-up in Phase 5).
 * Audio is 48 kHz mono signed 16-bit.
 */
#ifndef OP_AUDIO_H
#define OP_AUDIO_H

#include <stdint.h>

#define OP_AUDIO_RATE_HZ       48000
#define OP_AUDIO_FRAME_SAMPLES 48 /* 1 ms input frame */
#define OP_AUDIO_BLOCK_SAMPLES CONFIG_OP_DAC_BLOCK_SAMPLES

/* Open the backend. 0 on success, negative errno on failure
 * (-ENOTSUP: no audio on this core). */
int op_audio_start(void);

/* Read one frame of OP_AUDIO_FRAME_SAMPLES samples. 0 on success,
 * -ENODATA at end of input, other negative errno on failure. */
int op_audio_read_frame(int16_t *frame);

/* Write one DAC block of OP_AUDIO_BLOCK_SAMPLES samples. 0 or negative errno. */
int op_audio_write_block(const int16_t *block);

/* I2S backend, pack (#97): start capture; cb runs in the I2S interrupt once per completed frame
 * (RXPTRUPD), the audio frame clock. Steer its rate in whole HFCLKAUDIO steps (3311 ppb each). */
int op_audio_i2s_rx_start(void (*cb)(void));
void op_audio_i2s_aclk_steps(int32_t steps);
/* Pack: stop capture and put the PCM1840 back into shutdown (battery cutoff). */
void op_audio_i2s_stop(void);

/* I2S backend, receiver (#118): samples handed to the PCM5102A so far (zeros included). */
uint32_t op_audio_i2s_tx_out(void);

#endif /* OP_AUDIO_H */
