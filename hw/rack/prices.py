"""Rack main-board (backplane) unit prices in GBP ex VAT, for ONE rack (the prototype build), looked up 2026-11-01.

The owner is UK-based: every line names a UK distributor (Farnell UK, RS UK, Mouser UK, DigiKey UK or LCSC) and its
GBP price, the quantity break the price is for, and where the number came from:
  "read"  = read on the distributor's UK page on 2026-11-01 (DigiKey UK, www.digikey.co.uk, GBP ex VAT);
  "est."  = not read on a page: a class price for a generic part, deliberately on the high side.
Stock was read where the page showed it; "0 stock" lines are open items in ADR-0018.
"""
DK = "DigiKey UK 2026-11-01, read"

PRICES = {  # mpn: (gbp_each, qty_break, source, uk_distributor)
    "QPL9057TR7": (4.60, 1, DK + " (61,763 in stock); 25+ GBP 3.77, 100+ GBP 3.17", "DigiKey UK"),
    "0451004.MRL": (0.90, 1, "est. (Littelfuse Nano2 451 4 A fast, 125 V)", "DigiKey UK / Farnell UK"),
    "R_2512_1R_1W": (0.10, 1, "est. (1 ohm 1 % 2512 1 W thick film)", "LCSC / Farnell UK"),
    "M20-7831346": (2.19, 1, DK + " (Harwin 2x13 2.54 mm socket, 4,728 in stock)", "DigiKey UK"),
    "LTST-C191KGKT": (0.11, 1, "DigiKey UK, read for hw/bom/pack_uk.csv (Lite-On 0603 green)", "DigiKey UK"),
    "LTST-C191KRKT": (0.11, 1, "DigiKey UK, read for hw/bom/pack_uk.csv (Lite-On 0603 red)", "DigiKey UK"),
    "QPQ1907SR": (2.82, 1, DK + " (7,548 in stock; 33-week lead); IL 1.3 typ / 2.2 max dB", "DigiKey UK"),
    "ESD103-B1-02EL": (0.30, 1, "est. (Infineon 15 V 0.09 pF RF ESD, TSLP-2-20; Farnell UK 2725731, LCSC C535146)",
                       "Farnell UK / LCSC"),
    "ESD101-B1-02EL": (0.30, 1, "est. (Infineon 5.5 V 0.1 pF RF ESD, TSLP-2-20; Farnell UK 2480926)", "Farnell UK"),
    "LQW18AN39NG80D": (0.11, 1, DK + " (10,561 in stock): 39 nH, SRF 3.28 GHz, Idc 1 A, DCR 0.16 ohm", "DigiKey UK"),
    "0402CS-18NXG": (0.15, 1, "est. (Coilcraft 0402CS 18 nH, the QPL9057 EVB L1)", "DigiKey UK / Mouser UK"),
    "FB_0603_600R": (0.03, 10, "est. (600 ohm at 100 MHz 0603 ferrite bead, 1 A)", "LCSC"),
    "TPS259541DSGR": (0.558, 10, DK + " qty-10 break; 20-week lead, stock not shown", "DigiKey UK"),
    "TPS259531DSGR": (0.558, 10, DK + " qty-10 break (4,178 in stock)", "DigiKey UK"),
    "TPS62933DRLR": (1.20, 1, "est. (TI TPS62933 3 A buck, SOT-583)", "DigiKey UK / Farnell UK"),
    "TLV76733DGNR": (0.30, 1, "est. (as hw/rx/prices.py, USD 0.40)", "Farnell UK / DigiKey UK / Mouser UK"),
    "SC16IS752IPW,128": (5.92, 1, DK + " (11,036 in stock); the ,112 tube variant is obsolete", "DigiKey UK"),
    "CX3225GB14745P0HPQCC": (0.58, 1, DK + " (3,000 in stock): 14.7456 MHz 3225 18 pF", "DigiKey UK"),
    "NC3MAH": (2.08, 1, DK + " (Neutrik NC3MAH; qty-10 break not shown)", "DigiKey UK"),
    "112487": (7.18, 1, DK + " (Amphenol RF 112487 R/A bulkhead BNC, 4 GHz; 12-week lead)", "DigiKey UK"),
    "SMAJ58CA": (0.36, 1, DK + " (Littelfuse)", "DigiKey UK"),
    "SMBJ12A": (0.37, 1, DK + " (Littelfuse)", "DigiKey UK"),
    "SMF12A": (0.08, 1, "est. (SMF 200 W TVS SOD-123F)", "LCSC / Farnell UK"),
    "AO4407A": (0.25, 1, "est. (Alpha & Omega -30 V 12 A P-FET SO-8; DMP3013SFV-7 is 0-stock at DigiKey UK)", "LCSC"),
    "BZT52C12": (0.03, 1, "est. (12 V zener SOD-123)", "LCSC"),
    "PJ-063AH": (1.22, 1, DK + " (Same Sky PJ-063AH 2.1 mm 8 A, 34,138 in stock; not locking)", "DigiKey UK"),
    "SBH11-PBPC-D20-ST-BK": (0.49, 1, DK + " (Sullins 2x20 box header, 69,820 in stock)", "DigiKey UK"),
    "B2P-VH": (0.15, 1, "est. (JST VH 2-pin 3.96 mm header, CM4IO 12 V feed)", "LCSC / Farnell UK"),
    "U.FL-R-SMT-1(10)": (0.34, 10, "est. (as hw/rx/prices.py, USD 0.45)", "Farnell UK / RS UK"),
    "IND_6u8_4A": (0.60, 1, "est. (6.8 uH 4 A shielded power inductor, 5x5 mm; TPS62933 reference design value)",
                   "LCSC / DigiKey UK"),
    "ALU_100u_25V": (0.08, 1, "est. (as hw/rx/prices.py)", "LCSC"),
    "C_22u_1206_25V_X5R": (0.10, 1, "est.", "LCSC"),
    "C_10u_1206_25V_X7R": (0.09, 1, "est. (as hw/rx/prices.py, USD 0.12)", "LCSC"),
    "C_10u_0603_X5R": (0.05, 10, "est.", "LCSC"),
    "C_1u_0402": (0.02, 10, "est.", "LCSC"),
    "C_100n_0402": (0.02, 10, "est.", "LCSC"),
    "C_22n_0402": (0.02, 10, "est.", "LCSC"),
    "C_33n_0402": (0.02, 10, "est.", "LCSC"),
    "C_10n_0402": (0.02, 10, "est.", "LCSC"),
    "C_100p_0402_C0G": (0.02, 10, "est.", "LCSC"),
    "C_22p_0402_C0G": (0.02, 10, "est.", "LCSC"),
    "R_0402_1%": (0.01, 10, "est.", "LCSC"),
    "R_0402_100R_TF": (0.08, 10, "est. (100 ohm 0402 thin film, Wilkinson isolation)", "LCSC / Farnell UK"),
    "R_0402_0R": (0.01, 1, "est.", "LCSC"),
    "PCB_TRACE": (0.0, 1, "copper on the main board (hw/rack/wilkinson.py): no part", "-"),
}

# Items with no schematic symbol: the host computer, cables, panel parts. (item, qty, gbp_each, source, distributor)
EXTRAS = [
    ("Raspberry Pi CM4 2 GB RAM / 8 GB eMMC, no wireless (SC0680 = CM4002008)", 1, 79.20,
     "The Pi Hut UK, qty 1, 2026-11-01 (coordinator decision on #95; DigiKey UK SC0680 was 0 stock at GBP 61.64)."
     " SC0681 (16 GB eMMC) same price is the drop-in alternative", "The Pi Hut UK"),
    ("Harwin M20-003 polarising key, fitted in socket position 14 (ADR-0014 key)", 8, 0.22, DK + " (Harwin M20-003)",
     "DigiKey UK / Farnell UK 512023"),
    ("Raspberry Pi CM4 IO Board (SC0326)", 1, 26.15, DK, "DigiKey UK"),
    ("40-way IDC ribbon 152 mm, socket-socket (Assmann H3AAH-4006G): main board J to CM4IO J8", 1, 1.30, DK, "DigiKey UK"),
    ("CM4IO 12 V pigtail: JST VH 2-pin housing to 2.1 mm DC plug, 200 mm", 1, 3.00, "est.", "LCSC / RS UK"),
    ("U.FL-U.FL 1.13 mm cable 200 mm (Sevskiy CA-MHF1-MC1.13-200-MHF1), splitter port to sub-board J3/J4", 16, 4.48,
     DK + " (109,584 in stock)", "DigiKey UK"),
    ("Neutrik NE8FDP etherCON RJ45 feedthrough (rear panel)", 1, 12.78, DK, "DigiKey UK"),
    ("Cat6 patch 0.3 m, NE8FDP to CM4IO RJ45", 1, 2.00, "est.", "RS UK / Farnell UK"),
    ("Panel-mount USB-C socket to micro-USB plug, 0.3 m (CM4IO rpiboot service port, RK-1)", 1, 8.00,
     "est. (not found on DigiKey UK: open item)", "RS UK / Farnell UK"),
    ("Mean Well GST60A12-P1J 12 V 5 A desktop brick, 2.1 mm plug, C14 inlet", 1, 14.50, DK + " (6,852 in stock)",
     "DigiKey UK"),
    ("UK mains cord BS1363 to C13, 1.83 m (AC-12206-UK)", 1, 8.35, DK + " (7,931 in stock)", "DigiKey UK"),
    ("Main board PCB 4-layer ~400 x 150 mm, JLC04161H-7628, ENIG", 1, 25.00, "est. (JLCPCB qty-5 price share)",
     "JLCPCB (ships to UK)"),
    ("1U 19 in steel case, ~250 mm deep, with blank rear panel to punch", 1, 60.00, "est.", "RS UK / Farnell UK"),
]

# Not on the backplane BOM, priced elsewhere and added by audit.py for the rack total:
ANTENNA_KIT_GBP = 340.56   # ADR-0016 (PR #93): 2 x (HG2409P-NF + CA3N050 + BNC jumper), ex VAT, ITM Components UK
