/* I2S backend: stub until Phase 5 (hardware bring-up). */
#include <errno.h>
#include "op_audio.h"

int op_audio_start(void) { return -ENOTSUP; }
int op_audio_read_frame(int16_t *frame) { (void)frame; return -ENOTSUP; }
int op_audio_write_block(const int16_t *block) { (void)block; return -ENOTSUP; }
