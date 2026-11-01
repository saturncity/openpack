/* Pack cell monitor (PK-8, ADR-0012, #118). Pure C: no Zephyr dependency (unit tested on native_sim, fw/tests/batt).
 *
 * The cell is read through the board's VBAT_SENSE divider (R12/R13, tapped at the cell) while the radio transmits,
 * i.e. under load. LOW (red LED) below low_mv, back to OK at low_mv + hyst_mv. CUTOFF below cut_mv (3.3 V, ADR-0012:
 * IOVDD 3.0 V + LDO + path + ADC error = 3.201 V, rounded up) for cut_n samples in a row; it latches.
 */
#ifndef OP_BATT_H
#define OP_BATT_H

#include <stdint.h>

enum op_batt_state { OP_BATT_OK, OP_BATT_LOW, OP_BATT_CUTOFF };

struct op_batt {
	int32_t low_mv, cut_mv, hyst_mv;
	uint8_t cut_n, below;
	enum op_batt_state st;
	int32_t last_mv;
};

/* Cell voltage from the ADC pin voltage and the divider (full = top + bottom, out = bottom), rounded. */
int32_t op_batt_cell_mv(int32_t pin_mv, uint32_t full_ohms, uint32_t out_ohms);
void op_batt_init(struct op_batt *b, int32_t low_mv, int32_t cut_mv, int32_t hyst_mv, uint8_t cut_n);
enum op_batt_state op_batt_update(struct op_batt *b, int32_t cell_mv);

/* Zephyr side (fw/src/app/batt.c): sample every CONFIG_OP_BATT_PERIOD_MS, drive the battery LEDs, power off. */
int op_batt_start(void);

#endif /* OP_BATT_H */
