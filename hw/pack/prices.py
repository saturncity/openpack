"""Unit prices at qty 100 (USD), looked up 2026-10-31. `src` says where each number came from.

"DK" = Digi-Key cut tape, qty-100 break, read from the product page that day. "est." = no page
read; a class price for a generic passive, deliberately on the high side.
"""
DK = "Digi-Key qty-100 cut tape, 2026-10-31"

PRICES = {  # mpn: (usd_each_at_100, source)
    "BT40NE": (13.47, "Fanstel direct, qty-100 break on fanstel.com/bt40f-nrf5340 (read 2026-10-31, #31 comment)"),
    "PCM1840IRTWR": (3.37, DK),
    "OPA1656IDR": (1.84, DK),
    "TPS61023DRLR": (0.80, DK),
    "TLV75533PDBVR": (0.23, DK),
    "USBLC6-2SC6": (0.21, DK),
    "SJ1-3543": (1.61, DK + " (Same Sky, M6 threaded bushing + nut); fallback Switchcraft 35RAPC3BH3 $3.29"),
    "USB4105-GF-A": (0.57, DK),
    "BH-18650-B1BA002": (1.36, "LCSC C2988620 q1 (via Flux part page); retention from battery door"),
    "JS102011SAQN": (0.64, DK),
    "DMG2305UX-7": (0.10, "est."),
    "TPD1E10B06DPYR": (0.41, "Digi-Key listing price (tier not shown; q1 assumed)"),
    "BAV199,215": (0.21, "Digi-Key listing price (tier not shown; q1 assumed)"),
    "SF-1206F300-2": (0.52, DK + " (Bourns 3 A 1206 fast, 23 mOhm cold)"),
    "DFE252012F-1R0M=P2": (0.17, DK),
    "GRM31CR60J107ME39L": (0.35, "est. (100 uF 6.3 V 1206)"),
    "GRM31CR61A476ME15L": (0.25, "est. (47 uF 10 V 1206)"),
    "GRM21BR61A226ME51L": (0.12, "est. (22 uF 10 V 0805)"),
    "C_10u_1206_X7R": (0.12, "est. (10 uF 16 V 1206 X7R)"),
    "C_10u_0603_X5R": (0.06, "est. (10 uF 10 V 0603 X5R)"),
    "C_1u_0402": (0.03, "est."),
    "C_100n_0402": (0.02, "est."),
    "C_22p_0402_C0G": (0.02, "est."),
    "R_0402_1%": (0.02, "est."),
    "LTST-C191KGKT": (0.15, "Digi-Key listing price (q1 assumed); AlInGaP green, Vf ~2.0 V"),
    "LTST-C191KRKT": (0.15, "est. = KGKT price (same Lite-On series)"),
    "LTST-C191KSKT": (0.15, "est. = KGKT price (same Lite-On series)"),
    "TC2030-pads": (0.0, "footprint only"),
    "TP-pad": (0.0, "footprint only"),
}

# Items with no schematic symbol. The 18650 cell is excluded from PK-12 by definition.
EXTRAS = [  # (item, qty, usd_each, source)
    ("PCB 4-layer ~60x90 mm", 1, 2.50, "est. (audit.py v1 figure)"),
    ("3D-printed PETG enclosure + clip (mech/)", 1, 2.50, "est. (audit.py v1 figure)"),
    ("u.FL to wire pigtail + 31 mm whip (PK-5)", 1, 1.00, "est."),
]

# Informational: the same module bought from Digi-Key (qty-100 cut tape, 2026-10-31, part 22107427).
BT40NE_DIGIKEY_Q100 = 16.76
