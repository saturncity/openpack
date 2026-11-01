"""Receiver sub-board unit prices at qty 100 (USD), looked up 2026-10-31. `src` says where each number came from.

"est." = no page read; a class price for a generic part, deliberately on the high side.

The owner is UK-based (coordinator, 2026-10-31): every line names a distributor that sells into the UK
(Farnell UK, RS UK, Mouser UK, DigiKey UK or LCSC) and carries a GBP figure. GBP is the USD figure converted at
GBP_PER_USD, ex VAT. It is NOT a UK quote, and UK stock was not checked line by line (open item 6, ADR-0014).
"""
DK = "Digi-Key qty-100 cut tape, 2026-10-31"
GBP_PER_USD = 0.76   # assumed (1 GBP = 1.32 USD); replace with live UK quotes before ordering (#40)

PRICES = {  # mpn: (usd_each_at_100, source, uk_distributor)
    # ADR-0021: BT40E (no FEM). UK: priced at Digi-Key UK in GBP (GBP 9.7765 qty-100 cut tape, 803 in stock, 10 wk
    # standard lead, read 2026-11-01); the USD figure is that GBP / GBP_PER_USD so the BOM's GBP column is the quote.
    # Fanstel direct is $9.55 (BT40E_FANSTEL_Q100) but adds import VAT + duty.
    "BT40E": (round(9.7765 / GBP_PER_USD, 2), "Digi-Key UK qty-100 cut tape GBP 9.7765, part 13174285, 803 in stock, "
              "10 wk lead (read 2026-11-01)", "DigiKey UK"),
    "PCM5102APWR": (2.80, "Digi-Key qty-100, via findchips.com snapshot read 2026-10-31 (Mouser q100 $2.78)",
                    "Mouser UK / Farnell UK"),
    "PE4259-63": (0.41, "LCSC C470892 qty-100, via findchips.com/LCSC snapshot read 2026-10-31 (range $0.32-0.49)",
                  "LCSC C470892"),
    "OPA1656IDR": (1.84, DK + " (same as hw/pack/prices.py)", "DigiKey UK / Mouser UK"),
    "TLV76733DGNR": (0.40, "est. (TI TLV767 1 A 16 V LDO, HVSSOP-8, q100)", "Farnell UK / DigiKey UK / Mouser UK"),
    "TPS3808G01DBVR": (0.80, "est. (TI TPS3808 adjustable supervisor, SOT-23-6, q100)", "Farnell UK / Mouser UK"),
    "TQ2SA-12V": (3.20, "est. (Panasonic TQ2 DPDT 12 V signal relay, q100; Farnell UK 1124056)", "Farnell UK / RS UK"),
    "BSS138": (0.05, "est. (onsemi BSS138 SOT-23, q100)", "LCSC / Farnell UK"),
    "BAT54,215": (0.03, "est. (Nexperia BAT54 SOT-23, q100)", "LCSC / Farnell UK"),
    "S1J": (0.04, "est. (S1J 1 A 600 V SMA, IFSM 30 A, q100)", "LCSC / Farnell UK"),
    "U.FL-R-SMT-1(10)": (0.45, "est. (Hirose U.FL receptacle, q100)", "Farnell UK / RS UK"),
    "SMF15A": (0.10, "est. (SMF 200 W TVS SOD-123F, q100)", "LCSC / Farnell UK"),
    "SMF5.0A": (0.10, "est. (SMF 200 W TVS SOD-123F, q100)", "LCSC / Farnell UK"),
    "HDR_2x13_2.54_KEY14": (0.40, "est. (2x13 2.54 mm gold THT pin header, pin 14 pulled as the key, q100)", "LCSC"),
    "TP-pad": (0.0, "footprint only", "-"),
    "ALU_100u_25V": (0.10, "est. (100 uF 25 V SMD aluminium, 6.3 mm)", "LCSC"),
    "ALU_22u_25V": (0.07, "est. (22 uF 25 V SMD aluminium, 5 mm)", "LCSC"),
    "ALU_47u_25V": (0.08, "est. (47 uF 25 V SMD aluminium, 5 mm)", "LCSC"),
    "ALU_BP_47u_63V": (0.25, "est. (47 uF 63 V bipolar aluminium, 10 mm, e.g. Nichicon UEP series)", "Farnell UK / RS UK"),
    "C_10u_1206_25V_X7R": (0.12, "est. (10 uF 25 V 1206 X7R)", "LCSC"),
    "C_10u_0603_X5R": (0.06, "est. (10 uF 10 V 0603 X5R)", "LCSC"),
    "C_2u2_0603_X7R": (0.03, "est.", "LCSC"),
    "C_1u_0402": (0.03, "est.", "LCSC"),
    "C_100n_0402": (0.02, "est.", "LCSC"),
    "C_2n2_0402_C0G": (0.02, "est.", "LCSC"),
    "C_1n_0402": (0.02, "est.", "LCSC"),
    "C_100p_0402_C0G": (0.02, "est.", "LCSC"),
    "C_10p_0402_C0G": (0.02, "est.", "LCSC"),
    "R_0402_1%": (0.02, "est.", "LCSC"),
    "R_0603_1%": (0.02, "est.", "LCSC"),
    "TC2030-pads": (0.0, "footprint only", "-"),
    "DNP": (0.0, "not fitted (#81 review S4): pads only; fit 100 R 0402 for a digital add-on", "-"),
}

# Items with no schematic symbol.
EXTRAS = [  # (item, qty, usd_each, source, uk_distributor)
    ("PCB 4-layer ~40x80 mm (50 ohm RF traces)", 1, 1.50, "est. (qty-100 panel share)", "JLCPCB (ships to UK)"),
    ("U.FL-U.FL jumper 50 mm (switch out -> module u.FL)", 1, 1.50, "est.", "LCSC / RS UK"),
]

BT40E_FANSTEL_Q100 = 9.55    # informational: Fanstel direct (docs/analysis/module-antenna.md, ADR-0021)
BT40NE_DIGIKEY_Q100 = 16.76  # informational: the module this board used before ADR-0021 (Digi-Key qty-100)
