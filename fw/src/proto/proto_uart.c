/* Console glue: read lines from the console UART, run the role's command table, write the reply.
 * bsim: uart0 is the pty. DK: uart0 is the VCOM; the pack's USB CDC ACM is a follow-up (see fw/PROTOCOL.md).
 */
#include <zephyr/kernel.h>
#include <zephyr/init.h>
#include <zephyr/drivers/uart.h>
#include <zephyr/sys/ring_buffer.h>
#include "proto.h"

#define PROTO_DEV DEVICE_DT_GET(DT_CHOSEN(zephyr_console))

#ifdef CONFIG_OP_ROLE_RX
static struct op_rx_state st = {.sample = op_rx_stub_sample};
#define TBL  op_rx_cmds
#define NTBL op_rx_ncmds
#else
static struct op_pack_state st;
#define TBL  op_pack_cmds
#define NTBL op_pack_ncmds

static int pack_init(void)
{
	op_pack_state_init(&st, CONFIG_OP_PACK_ID, CONFIG_OP_CH_A_MHZ, CONFIG_OP_CH_B_MHZ);
	return 0;
}
SYS_INIT(pack_init, APPLICATION, 0);
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
			k_sem_take(&rxsem, K_FOREVER);
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
