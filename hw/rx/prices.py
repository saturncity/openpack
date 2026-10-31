"""Receiver sub-board unit prices at qty 100 (USD), looked up 2026-10-31. `src` says where each number came from.

"est." = no page read; a class price for a generic part, deliberately on the high side.

The owner is UK-based (coordinator, 2026-10-31): every line names a distributor that sells into the UK
(Farnell UK, RS UK, Mouser UK, DigiKey UK or LCSC) and carries a GBP figure. GBP is the USD figure converted at
GBP_PER_USD, ex VAT. It is NOT a UK quote, and UK stock was not checked line by line (open item 6, ADR-0014).
"""
DK = "Digi-Key qty-100 cut tape, 2026-10-31"
GBP_PER_USD = 0.76   # assumed (1 GBP = 1.32 USD); replace with live UK quotes before ordering (#40)

PRICES = {  # mpn: (usd_each_at_100, source, uk_distributor)
    # UK: priced at DigiKey (ships to the UK), not Fanstel direct ($13.47, which adds import VAT + duty)
    "BT40NE": (16.76, "Digi-Key qty-100 cut tape, part 22107427 (hw/pack/prices.py BT40NE_DIGIKEY_Q100)", "DigiKey UK"),
    "PCM5102APWR": (2.80, "Digi-Key qty-100, via findchips.com snapshot read 2026-10-31 (Mouser q100 $2.78)",
                    "Mouser UK / Farnell UK"),
    "PE4259-63": (0.41, "LCSC C470892 qty-100, via findchips.com/LCSC snapshot read 2026-10-31 (range $0.32-0.49)",
                  "LCSC C470892"),
    "OPA1656IDR": (1.84, DK + " (same as hw/pack/prices.py)", "DigiKey UK / Mouser UK"),
    "TLV75533PDBVR": (0.23, DK + " (same as hw/pack/prices.py)", "Farnell UK / DigiKey UK"),
    "U.FL-R-SMT-1(10)": (0.45, "est. (Hirose U.FL receptacle, q100)", "Farnell UK / RS UK"),
    "BAV99,215": (0.04, "est. (Nexperia BAV99 SOT-23, q100)", "LCSC / Farnell UK"),
    "SMF15A": (0.10, "est. (SMF 200 W TVS SOD-123F, q100)", "LCSC / Farnell UK"),
    "SMF5.0A": (0.10, "est. (SMF 200 W TVS SOD-123F, q100)", "LCSC / Farnell UK"),
    "HDR_2x13_2.54_SMD": (0.40, "est. (2x13 2.54 mm gold pin header, q100)", "LCSC"),
    "ALU_100u_25V": (0.10, "est. (100 uF 25 V SMD aluminium, 6.3 mm)", "LCSC"),
    "ALU_47u_25V": (0.08, "est. (47 uF 25 V SMD aluminium, 5 mm)", "LCSC"),
    "ALU_BP_47u_63V": (0.25, "est. (47 uF 63 V bipolar aluminium, 10 mm, e.g. Nichicon UEP series)", "Farnell UK / RS UK"),
    "C_10u_1206_25V_X7R": (0.12, "est. (10 uF 25 V 1206 X7R)", "LCSC"),
    "C_10u_0603_X5R": (0.06, "est. (10 uF 10 V 0603 X5R)", "LCSC"),
    "C_2u2_0603_X7R": (0.03, "est.", "LCSC"),
    "C_1u_0402": (0.03, "est.", "LCSC"),
    "C_100n_0402": (0.02, "est.", "LCSC"),
    "C_2n2_0402_C0G": (0.02, "est.", "LCSC"),
    "C_100p_0402_C0G": (0.02, "est.", "LCSC"),
    "C_10p_0402_C0G": (0.02, "est.", "LCSC"),
    "R_0402_1%": (0.02, "est.", "LCSC"),
    "R_0603_1%": (0.02, "est.", "LCSC"),
    "TC2030-pads": (0.0, "footprint only", "-"),
}

# Items with no schematic symbol.
EXTRAS = [  # (item, qty, usd_each, source, uk_distributor)
    ("PCB 4-layer ~40x80 mm (50 ohm RF traces)", 1, 1.50, "est. (qty-100 panel share)", "JLCPCB (ships to UK)"),
    ("U.FL-U.FL jumper 50 mm (switch out -> module u.FL)", 1, 1.50, "est.", "LCSC / RS UK"),
]

BT40NE_FANSTEL_Q100 = 13.47  # informational: Fanstel direct (fanstel.com/bt40f-nrf5340, #31 comment)
