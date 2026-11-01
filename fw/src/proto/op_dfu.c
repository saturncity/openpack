/* `dfu` (#25): enter MCUboot serial recovery. Set the retained boot mode, then reset 200 ms later so the `ok` reply is
 * on the wire first. MCUboot (fw/sysbuild/mcuboot.conf, BOOT_SERIAL_BOOT_MODE) sees the mode, stays in the bootloader
 * and speaks mcumgr SMP on its serial port, and leaves again after BOOT_SERIAL_INACTIVITY_TIMEOUT without a command.
 */
#include <zephyr/kernel.h>
#include <zephyr/init.h>
#include <zephyr/retention/bootmode.h>
#include <zephyr/sys/reboot.h>
#include "proto.h"

static void reset_now(struct k_work *w)
{
	sys_reboot(SYS_REBOOT_COLD);
}

static K_WORK_DELAYABLE_DEFINE(reset_work, reset_now);

static int enter_recovery(void)
{
	int err = bootmode_set(BOOT_MODE_TYPE_BOOTLOADER);

	if (err) {
		return err;
	}
	k_work_schedule(&reset_work, K_MSEC(200));
	return 0;
}

static int dfu_init(void)
{
	op_dfu_hook = enter_recovery;
	return 0;
}
SYS_INIT(dfu_init, APPLICATION, 1);
