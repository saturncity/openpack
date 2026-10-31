/* Test only (CONFIG_OP_TEST_BSIM_ARGS, bsim net core): pack id and carrier pair from the command line,
 * so tests/bsim/scenarios (#27) runs 8 packs and 8 receivers from one pack and one receiver build.
 * Defaults are the Kconfig values; op_frame.h maps OP_PACK_ID / OP_CH_A_MHZ / OP_CH_B_MHZ here.
 */
#include "bs_cmd_line.h"
#include "bs_dynargs.h"
#include "posix_native_task.h"
#include "op_frame.h"

int op_pack_id = CONFIG_OP_PACK_ID;
int op_ch_a_mhz = CONFIG_OP_CH_A_MHZ;
int op_ch_b_mhz = CONFIG_OP_CH_B_MHZ;

static void op_bsim_register_args(void)
{
	static bs_args_struct_t args[] = {
		{.option = "op_pack_id", .name = "id", .type = 'i', .dest = &op_pack_id,
		 .descript = "OpenPack pack id 0-7 (AIR-2 access address), default CONFIG_OP_PACK_ID"},
		{.option = "op_ch_a", .name = "MHz", .type = 'i', .dest = &op_ch_a_mhz,
		 .descript = "OpenPack copy A carrier (AIR-5), default CONFIG_OP_CH_A_MHZ"},
		{.option = "op_ch_b", .name = "MHz", .type = 'i', .dest = &op_ch_b_mhz,
		 .descript = "OpenPack copy B carrier (AIR-5), default CONFIG_OP_CH_B_MHZ"},
		ARG_TABLE_ENDMARKER,
	};

	bs_add_extra_dynargs(args);
}

NATIVE_TASK(op_bsim_register_args, PRE_BOOT_1, 10);
