#include <errno.h>
#include <string.h>
#include <zephyr/kernel.h>
#include <zephyr/kvss/nvs.h>
#include <zephyr/drivers/flash.h>
#include <zephyr/storage/flash_map.h>
#include "op_store.h"

/* The first OP_STORE_SECTORS sectors of storage_partition (nvs needs two: one live, one to garbage-collect into).
 * Not the whole partition: bsim's storage_partition is all 1 MB of the simulated flash.
 */
#define OP_STORE_SECTORS 2
#define OP_STORE_ID      1
#define OP_STORE_VERSION 1

/* On flash: fixed width, little endian by construction (nRF5340 and native_sim x86 are both LE). */
struct rec {
	uint8_t ver;
	uint8_t id;
	uint8_t td;
	int8_t power_dbm;
	uint16_t ch_a, ch_b;
	char region[4];
};

static struct nvs_fs fs;
static bool mounted;

int op_store_init(void)
{
	struct flash_pages_info info;
	const struct flash_area *fa;
	int err;

	err = flash_area_open(PARTITION_ID(storage_partition), &fa);
	if (err) {
		return err;
	}
	fs.flash_device = fa->fa_dev;
	fs.offset = fa->fa_off;
	err = flash_get_page_info_by_offs(fa->fa_dev, fa->fa_off, &info);
	flash_area_close(fa);
	if (err) {
		return err;
	}
	fs.sector_size = info.size;
	fs.sector_count = OP_STORE_SECTORS;
	err = nvs_mount(&fs);
	mounted = err == 0;
	return err;
}

int op_store_save(const struct op_pack_cfg *cfg)
{
	struct rec r = {OP_STORE_VERSION, cfg->id, cfg->td, cfg->power_dbm, cfg->ch_a, cfg->ch_b, ""};
	ssize_t n;

	if (!mounted && op_store_init()) {
		return -EIO;
	}
	memcpy(r.region, cfg->region, sizeof(r.region));
	n = nvs_write(&fs, OP_STORE_ID, &r, sizeof(r)); /* 0 when unchanged, else the length */
	return n < 0 ? (int)n : 0;
}

int op_store_load(struct op_pack_cfg *cfg)
{
	struct rec r;
	struct op_pack_cfg c = {0};
	ssize_t n;

	if (!mounted && op_store_init()) {
		return -EIO;
	}
	n = nvs_read(&fs, OP_STORE_ID, &r, sizeof(r));
	if (n == -ENOENT) {
		return -ENOENT;
	}
	if (n != sizeof(r) || r.ver != OP_STORE_VERSION) {
		return -EINVAL;
	}
	c.id = r.id;
	c.td = r.td;
	c.power_dbm = r.power_dbm;
	c.ch_a = r.ch_a;
	c.ch_b = r.ch_b;
	memcpy(c.region, r.region, sizeof(c.region));
	c.region[sizeof(c.region) - 1] = 0;
	if (!op_pack_cfg_valid(&c)) {
		return -EINVAL;
	}
	*cfg = c;
	return 0;
}
