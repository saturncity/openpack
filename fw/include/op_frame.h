/* AIR-3 v1 payload (ADPCM-6, time diversity off): seq u8, status u16 LE, codec_state 3 B, audio 36 B. */
#pragma once
#include <stdint.h>
#include <stddef.h>

#if defined(CONFIG_OP_TEST_FRAME_LEN) && CONFIG_OP_TEST_FRAME_LEN > 0
#define OP_FRAME_LEN CONFIG_OP_TEST_FRAME_LEN /* test only, fw/Kconfig */
#else
#define OP_FRAME_LEN 42
#endif
#define OP_FRAME_US  1000

/* Pack id (AIR-2 address) and carrier pair (AIR-5): Kconfig, or the bsim command line on test builds
 * (CONFIG_OP_TEST_BSIM_ARGS, src/bsim_args.c), so one build serves every pack id in bsim.
 */
#if defined(CONFIG_OP_TEST_BSIM_ARGS)
extern int op_pack_id, op_ch_a_mhz, op_ch_b_mhz;
#define OP_PACK_ID  op_pack_id
#define OP_CH_A_MHZ op_ch_a_mhz
#define OP_CH_B_MHZ op_ch_b_mhz
#else
#define OP_PACK_ID  CONFIG_OP_PACK_ID
#define OP_CH_A_MHZ CONFIG_OP_CH_A_MHZ
#define OP_CH_B_MHZ CONFIG_OP_CH_B_MHZ
#endif

/* FW-2: one frame per IPC message, app core -> net core. Pack only, net -> app, once at start: the
 * latch sync (OP_SYNC_LEN bytes, u16 LE us to the net core's next payload latch, #87).
 */
#define OP_SYNC_LEN 2
int op_ipc_init(void (*rx)(const uint8_t *frame, size_t len));
int op_ipc_send(const uint8_t *frame, size_t len);

/* Net core, pack role: AIR-4 schedule. */
int op_sched_start(void);
int op_sched_sync(void);
void op_sched_put(const uint8_t *frame, size_t len);
uint32_t op_sched_underruns(void);
uint32_t op_sched_overruns(void);

/* App core, pack role: audio -> ADPCM-6 -> IPC, one frame per audio frame (src/app/pack.c). */
int op_pack_start(void);
