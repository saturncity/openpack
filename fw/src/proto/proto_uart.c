/* Console glue: read lines from the console UART, run the role's command table, write the reply.
 * With a chosen openpack,proto (the USB CDC ACM instance, fw/boards/op_usb_cdc.dtsi: DK, pack board) the protocol is on
 * USB and uart0 keeps the log; else the console UART (bsim pty, receiver board). See fw/PROTOCOL.md.
 */
#include <zephyr/kernel.h>
#include <zephyr/init.h>
#include <zephyr/drivers/uart.h>
#include <zephyr/sys/ring_buffer.h>
#include "proto.h"
#include "op_frame.h"
#include "op_rx.h"
#ifdef CONFIG_OP_PERSIST
#include "op_store.h"
#endif

#if defined(CONFIG_OP_CONSOLE_USB_CDC)
#define PROTO_DEV DEVICE_DT_GET(DT_CHOSEN(openpack_proto))
#else
#define PROTO_DEV DEVICE_DT_GET(DT_CHOSEN(zephyr_console))
#endif

#ifdef CONFIG_OP_ROLE_RX
/* Telemetry from the app core's counters (#24: merge, PLC, jitter slot, clock recovery). */
static void sample(struct op_rx_state *s)
{
	struct op_rx_snap n;

	op_rx_app_snapshot(&n);
	op_rx_state_from_snap(s, &n);
}

static struct op_rx_state st = {.sample = sample};
#define TBL  op_rx_cmds
#define NTBL op_rx_ncmds
#else
static struct op_pack_state st;
#define TBL  op_pack_cmds
#define NTBL op_pack_ncmds

static int pack_init(void)
{
	op_pack_state_init(&st, CONFIG_OP_PACK_ID, CONFIG_OP_CH_A_MHZ, CONFIG_OP_CH_B_MHZ);
	st.cur.td = IS_ENABLED(CONFIG_OP_TIME_DIVERSITY); /* boot value of `td` (ADR-0017) */
#ifdef CONFIG_OP_PERSIST
	/* Saved settings win over the Kconfig defaults; none, or a record that fails validation, keeps the defaults. */
	st.persist = op_store_save;
	if (op_store_load(&st.cur) == 0) {
		printk("OpenPack config: loaded from flash\n");
	}
#endif
	st.saved = st.cur;
	return 0;
}
SYS_INIT(pack_init, APPLICATION, 0);

bool op_pack_td(void)
{
	return st.cur.td;
}
#endif

static void put(const struct device *d, const char *s, size_t n)
{
	for (size_t i = 0; i < n; i++) {
		uart_poll_out(d, s[i]);
	}
}

/* RX is interrupt driven into a ring buffer: at 115200 baud a byte arrives every 87 us, polling every 1 ms drops bytes. */
RING_BUF_DECLARE(rxrb, 256);
static K_SEM_DEFINE(rxsem, 0, 1);

static void rx_isr(const struct device *d, void *u)
{
	uint8_t buf[16];

	uart_irq_update(d);
	while (uart_irq_rx_ready(d)) {
		int n = uart_fifo_read(d, buf, sizeof(buf));

		if (n <= 0) {
			break;
		}
		ring_buf_put(&rxrb, buf, n);
	}
	k_sem_give(&rxsem);
}

static void proto_thread(void *a, void *b, void *c)
{
	const struct device *d = PROTO_DEV;
	char line[OP_PROTO_LINE_MAX], reply[OP_PROTO_REPLY_MAX];
	size_t n = 0;
	unsigned char ch;

	while (!device_is_ready(d)) {
		k_msleep(10);
	}
	uart_irq_callback_user_data_set(d, rx_isr, NULL);
	uart_irq_rx_enable(d);
	for (;;) {
		if (ring_buf_get(&rxrb, &ch, 1) == 0) {
			/* #87 stress only: OP_TEST_PROTO_POLL_MS > 0 brings back the 50 ms poll. */
			k_sem_take(&rxsem, CONFIG_OP_TEST_PROTO_POLL_MS > 0
						   ? K_MSEC(CONFIG_OP_TEST_PROTO_POLL_MS)
						   : K_FOREVER);
			continue;
		}
		if (ch == '\r') {
			continue;
		}
		if (ch != '\n') {
			if (n < sizeof(line) - 1) {
				line[n++] = ch;
			} else {
				n = sizeof(line); /* overflow: drop the line */
			}
			continue;
		}
		if (n >= sizeof(line)) {
			put(d, "err line too long\n", 18);
		} else {
			line[n] = 0;
			size_t r = op_proto_exec(TBL, NTBL, &st, line, reply, sizeof(reply));

			put(d, reply, r);
		}
		n = 0;
	}
}

K_THREAD_DEFINE(op_proto, 2048, proto_thread, NULL, NULL, NULL, 7, 0, 0);
