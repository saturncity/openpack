/* AIR-3 v1 payload (ADPCM-6, time diversity off): seq u8, status u16 LE, codec_state 3 B, audio 36 B. */
#pragma once
#include <stdint.h>
#include <stddef.h>

#define OP_FRAME_LEN 42
#define OP_FRAME_US  1000

/* FW-2: one frame per IPC message, app core -> net core. */
int op_ipc_init(void (*rx)(const uint8_t *frame, size_t len));
int op_ipc_send(const uint8_t *frame, size_t len);

/* Net core, pack role: AIR-4 schedule. */
int op_sched_start(void);
void op_sched_put(const uint8_t *frame, size_t len);
uint32_t op_sched_underruns(void);
uint32_t op_sched_overruns(void);

/* App core, pack role: placeholder 1 ms frame source until audio + codec land. */
int op_framesrc_start(void);
