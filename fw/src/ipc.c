/* FW-2: app <-> net core link over ipc_service (icmsg on ipc0), one AIR-3 frame per message. */
#include <errno.h>
#include <zephyr/kernel.h>
#include <zephyr/ipc/ipc_service.h>
#include "op_frame.h"

static K_SEM_DEFINE(bound, 0, 1);
static void (*rx_cb)(const uint8_t *frame, size_t len);
static struct ipc_ept ept;

static void on_bound(void *priv)
{
	k_sem_give(&bound);
}

static void on_recv(const void *data, size_t len, void *priv)
{
	if (rx_cb != NULL) {
		rx_cb(data, len);
	}
}

static struct ipc_ept_cfg cfg = {
	.name = "op_frame",
	.cb = {.bound = on_bound, .received = on_recv},
};

int op_ipc_init(void (*rx)(const uint8_t *frame, size_t len))
{
	const struct device *dev = DEVICE_DT_GET(DT_NODELABEL(ipc0));
	int err;

	rx_cb = rx;
	err = ipc_service_open_instance(dev);
	if (err != 0 && err != -EALREADY) {
		return err;
	}
	err = ipc_service_register_endpoint(dev, &ept, &cfg);
	if (err != 0) {
		return err;
	}
	return k_sem_take(&bound, K_SECONDS(1));
}

int op_ipc_send(const uint8_t *frame, size_t len)
{
	int n = ipc_service_send(&ept, frame, len);

	return n < 0 ? n : 0;
}
