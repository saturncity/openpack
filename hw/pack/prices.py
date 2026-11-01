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
    # printed cradle in mech/pack.py + two stamped contacts (the MYOUNG BH-18650-B1BA002 holder is SMT: dropped, #34)
    "MY-18650-04-J/05-J": (0.2265, "LCSC C19184125 MY-18650-04-J (+ plate) $0.1181 @50-149 + C19184124 MY-18650-05-J "
                                    "(- spring) $0.1084 (only ladder shown, @5); read 2026-11-01"),
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
    "C_100n_0402": (0.0013, "LCSC C1525 (Samsung CL05B104KO5NNNC, 100 nF 16 V X7R 0402), qty 100, 2026-10-31"),
    "C_22p_0402_C0G": (0.02, "est."),
    # UniOhm 0402WGF series 1 %: qty-100 prices seen on LCSC pages: 1k C11702 $0.0013, 100R C25076 $0.0013,
    # 100k C25741 $0.0013, 1M C26083 $0.0015, 5.1k C25905 $0.0023, 330R C407692 $0.0064. 2.2k, 180k, 732k not
    # looked up; every 0402 resistor is priced at the highest seen (330R).
    "R_0402_1%": (0.0064, "LCSC C407692 (and C11702, C25076, C25741, C26083, C25905), qty 100, 2026-10-31; highest of the six used for all"),
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
    # PK-5 whip feed: IPEX/MHF1 1.13 mm cable, SMA end cut off, ~100 mm kept; 31 mm 0.9 mm tinned wire soldered on
    ("IPEX 1.13 pigtail BWIPX1-SMA-1.13L150 (BAT Wireless, SMA cut off)", 1, 0.6015, "LCSC C784404 $0.6015 @100, 1908 in stock, read 2026-11-01"),
    ("whip: 31 mm 0.9 mm tinned Cu wire + 20 mm heat-shrink", 1, 0.03, "est."),
    ("cell leads: 2 x 60 mm 24 AWG silicone wire", 1, 0.02, "est."),
    ("M2 x 6 thread-forming pan screw (PT type, zinc)", 2, 0.112, "Fastener Superstore 585907 M2-0.89x6 PT pan Phillips zinc, "
     "$559 per 5000 carton = $0.112 (read 2026-11-01; LCSC/Accu listing not found)"),
]

# Informational: the same module bought from Digi-Key (qty-100 cut tape, 2026-10-31, part 22107427).
BT40NE_DIGIKEY_Q100 = 16.76
