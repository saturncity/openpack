/* Pack settings in flash (PK-9 `save`): one NVS record in the storage partition. Zephyr; the pure part is
 * op_pack_cfg_valid() in proto.h. Unit test: fw/tests/store (native_sim flash simulator).
 */
#pragma once
#include "proto.h"

/* Mount (or re-mount) the NVS area. 0 or -errno. */
int op_store_init(void);
/* Write cfg. 0 or -errno. */
int op_store_save(const struct op_pack_cfg *cfg);
/* Read the saved config. 0, -ENOENT (nothing saved) or -EINVAL (record fails op_pack_cfg_valid). */
int op_store_load(struct op_pack_cfg *cfg);
