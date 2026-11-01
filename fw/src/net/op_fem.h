/* #107 / ADR-0015: nRF21540 FEM power ceiling, checked at build time. Included by every net-core TX path. */
#ifndef OP_FEM_H
#define OP_FEM_H
#include <stdint.h>
#include <zephyr/toolchain.h>
#include <hal/nrf_radio.h>

#ifdef CONFIG_OP_FEM_NRF21540
#define OP_FEM_GAIN CONFIG_OP_FEM_GAIN_DB
#else
#define OP_FEM_GAIN 0
#endif
/* Conducted power at the antenna port, dBm. */
#define OP_TX_CONDUCTED_DBM (CONFIG_OP_TX_SOC_DBM + OP_FEM_GAIN)

BUILD_ASSERT(OP_TX_CONDUCTED_DBM <= CONFIG_OP_TX_MAX_CONDUCTED_DBM,
	     "conducted TX power (OP_TX_SOC_DBM + FEM gain) exceeds OP_TX_MAX_CONDUCTED_DBM (+7 dBm in region UK, ADR-0015)");

/* nRF5340 RADIO.TXPOWER holds the dBm value as a signed byte for -4..+3. */
#define OP_TXPOWER_REG ((nrf_radio_txpower_t)(uint8_t)CONFIG_OP_TX_SOC_DBM)

#ifdef CONFIG_OP_FEM_NRF21540
/* Drive MODE (low gain), ANT_SEL (u.FL) and PDN; returns 0 on success. */
int op_fem_init(void);
#endif
#endif
