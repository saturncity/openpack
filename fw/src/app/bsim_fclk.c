/* Test only (bsim pack app core, #97): the frame clock rate offset and an open lead loop from the
 * command line, so one build runs every tests/bsim/sched/lead.sh case. bsim's -xo_drift moves the
 * whole device (TIMER0 and TIMER1 share one crystal), so the HFCLKAUDIO offset is modelled here:
 *   -op_fclk_ppb=<ppb>  frame clock rate offset (default CONFIG_OP_TEST_FCLK_PPB; +371 = FREQ 39846)
 *   -op_lead_open       leave the lead loop open (negative control)
 */
#include <stdbool.h>
#include "bs_cmd_line.h"
#include "bs_dynargs.h"
#include "posix_native_task.h"

int op_fclk_ppb = CONFIG_OP_TEST_FCLK_PPB;
bool op_lead_open;

static int arg_ppb; /* the bsim parser writes a default into every dest: copy when found */

static void found_ppb(char *argv, int offset)
{
	op_fclk_ppb = arg_ppb;
}

static void op_bsim_fclk_args(void)
{
	static bs_args_struct_t args[] = {
		{.option = "op_fclk_ppb", .name = "ppb", .type = 'i', .dest = &arg_ppb,
		 .call_when_found = found_ppb,
		 .descript = "OpenPack test: pack frame clock rate offset, ppb (default CONFIG_OP_TEST_FCLK_PPB)"},
		{.is_switch = true, .option = "op_lead_open", .type = 'b', .dest = &op_lead_open,
		 .descript = "OpenPack test: pack lead loop open (no rate correction)"},
		ARG_TABLE_ENDMARKER,
	};

	bs_add_extra_dynargs(args);
}

NATIVE_TASK(op_bsim_fclk_args, PRE_BOOT_1, 11);
