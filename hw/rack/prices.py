"""Rack main-board (backplane) unit prices in GBP ex VAT, for ONE rack (the prototype build), looked up 2026-11-01.

The owner is UK-based: every line names a UK distributor (Farnell UK, RS UK, Mouser UK, DigiKey UK or LCSC) and its
GBP price, the quantity break the price is for, and where the number came from:
  "read"  = read on the distributor's UK page on 2026-11-01 (DigiKey UK, www.digikey.co.uk, GBP ex VAT);
  "est."  = not read on a page: a class price for a generic part, deliberately on the high side.
Stock was read where the page showed it; "0 stock" lines are open items in ADR-0018.
"""
DK = "DigiKey UK 2026-11-01, read"

PRICES = {  # mpn: (gbp_each, qty_break, source, uk_distributor)
    # #34 layout picks (coordinator decisions 2026-11-01). USD -> GBP at 0.76.
    "2.54-2*13PFemale": (0.17, 1, "est. (BOOMELE 2x13 2.54 mm female 8.5 mm, LCSC C64320, USD 0.2225, JLC parts record 2026-11-01 (stock unconfirmed)); contact 14 pulled and "
                         "the cavity plugged at assembly: the footprint has no hole at 14 (ADR-0014 key)", "LCSC"),
    "LTST-S270KGKT": (0.03, 1, "est. (Lite-On side-looking green, LCSC C125113, USD 0.042, JLC parts record 2026-11-01 (stock unconfirmed))", "LCSC"),
    "LTST-S270KRKT": (0.03, 1, "est. (Lite-On side-looking red, LCSC C125114, USD 0.032, JLC parts record 2026-11-01 (stock unconfirmed))", "LCSC"),
    "5415025-1": (6.95, 1, "est. (TE right-angle PCB BNC 50 ohm 4 GHz, 1/2-28 bulkhead; buy UK: DigiKey UK / Mouser UK, LCSC C5164649 USD 9.15 for reference; Molex 73138-5033 is the drop-in alternative)", "DigiKey UK / Mouser UK"),
    "QPL9057TR7": (4.60, 1, DK + " (61,763 in stock); 25+ GBP 3.77, 100+ GBP 3.17", "DigiKey UK"),
    "0451004.MRL": (0.90, 1, "est. (Littelfuse Nano2 451 4 A fast 125 V, 2410 case 6.1 x 2.5 mm, LCSC C27515 (LCSC record read 2026-11-01); footprint Fuse_Littelfuse-NANO2-451_453 = the 2410 land)", "LCSC"),
    "R_2512_1R_1W": (0.10, 1, "est. (1 ohm 1 % 2512 1 W thick film)", "LCSC / Farnell UK"),
    "QPQ1907SR": (2.82, 1, DK + " (7,548 in stock; 33-week lead); IL 1.3 typ / 2.2 max dB", "DigiKey UK"),
    "ESD103-B1-02EL": (0.30, 1, "est. (Infineon 15 V 0.09 pF RF ESD, TSLP-2-20; Farnell UK 2725731, LCSC C535146)",
                       "Farnell UK / LCSC"),
    "ESD101-B1-02EL": (0.30, 1, "est. (Infineon 5.5 V 0.1 pF RF ESD, TSLP-2-20; Farnell UK 2480926)", "Farnell UK"),
    "CS0603-39NJ-S": (0.02, 10, "est. (Chilisin 39 nH 5 % 0603, SRF 2.2 GHz, Q 40, 600 mA, DCR 0.25 ohm; LCSC C142171, LCSC record read 2026-11-01)", "LCSC"),
    "SDWL1005C18NGSTF": (0.02, 10, "est. (Sunlord 18 nH 2 % 0402, SRF 4.5 GHz; LCSC C361616, LCSC record read 2026-11-01)", "LCSC"),
    "FB_0603_600R": (0.03, 10, "est. (Murata BLM18KG601SN1D 600 ohm 1.3 A 0603; LCSC C85833)", "LCSC"),
    "TPS259541DSGR": (0.558, 10, DK + " qty-10 break; 20-week lead, stock not shown", "DigiKey UK"),
    "TPS259531DSGR": (0.558, 10, DK + " qty-10 break (4,178 in stock)", "DigiKey UK"),
    "TPS62933DRLR": (1.20, 1, "est. (TI TPS62933 3 A buck, SOT-583)", "DigiKey UK / Farnell UK"),
    "TLV76733DGNR": (0.30, 1, "est. (as hw/rx/prices.py, USD 0.40)", "Farnell UK / DigiKey UK / Mouser UK"),
    "SC16IS752IPW,128": (5.92, 1, DK + " (11,036 in stock); the ,112 tube variant is obsolete", "DigiKey UK"),
    "XC32M4-14.7456-F20NLDTL": (0.06, 1, "LCSC C3034317 read via the JLC parts API: HCI 14.7456 MHz 3225 20 pF, ESR 60 ohm, -40..+85 C, 10 ppm (LCSC C3034317, USD 0.0814, "
                                "JLC parts record read 2026-11-01, 6,684 in stock; #126 review: replaces the 100 ohm AKER C6523919)", "LCSC"),
    "C_33p_0402_C0G": (0.02, 10, "est.", "LCSC"),
    "NC3MAH": (2.08, 1, DK + " (Neutrik NC3MAH; the LCSC buy is C5154126, Extended, price there unconfirmed)", "LCSC / DigiKey UK"),
    "SMAJ58CA": (0.36, 1, DK + " (Littelfuse)", "DigiKey UK"),
    "SMBJ12A": (0.37, 1, DK + " (Littelfuse)", "DigiKey UK"),
    "SMF12A": (0.08, 1, "est. (SMF 200 W TVS SOD-123F)", "LCSC / Farnell UK"),
    "AO4407A": (0.25, 1, "est. (Alpha & Omega -30 V 12 A P-FET SO-8; DMP3013SFV-7 is 0-stock at DigiKey UK)", "LCSC"),
    "BZT52C12": (0.03, 1, "est. (12 V zener SOD-123)", "LCSC"),
    "PJ-063AH": (1.22, 1, DK + " (CUI / Same Sky PJ-063AH 2.1 mm 8 A, 34,138 in stock; not locking): buy UK", "DigiKey UK"),
    "2.54-2*20P": (0.10, 1, "est. (BOOMELE 2x20 2.54 mm IDC header, LCSC C9138, LCSC record read 2026-11-01)", "LCSC"),
    "B2P-VH": (0.15, 1, "est. (JST B2P-VH 2-pin 3.96 mm header, CM4IO 12 V feed; LCSC C160315)", "LCSC"),
    "U.FL-R-SMT-1(10)": (0.34, 10, "est. (Hirose U.FL-R-SMT-1(10), LCSC C88373 (not C88374))", "LCSC"),
    "SRP5030T-6R8M": (0.62, 1, "est. (Bourns SRP5030T-6R8M 6.8 uH, Irms 4.0 A, Isat 4.3 A, DCR 76.2 mohm, Bourns datasheet read 2026-11-01; buy UK, not LCSC: C177249 is only 3.5 A)", "DigiKey UK / Mouser UK / Farnell UK"),
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
    "TP-pad": (0.0, 1, "est. (footprint only: bare test pad)", "-"),
    "PCB_TRACE": (0.0, 1, "copper on the main board (hw/rack/wilkinson.py): no part", "-"),
}

# Items with no schematic symbol: the host computer, cables, panel parts. (item, qty, gbp_each, source, distributor)
# #34 cost-downs (coordinator, 2026-11-01): real quotes for the case, USB lead and RF jumpers; GBP ex VAT (UK VAT 20 %
# on top). Stock marked "unconfirmed" was not re-read at order time.
EXTRAS = [
    ("Raspberry Pi CM4 2 GB RAM / 8 GB eMMC, no wireless (SC0680 = CM4002008)", 1, 79.20,
     "The Pi Hut UK, qty 1, 2026-11-01 (coordinator decision on #95; DigiKey UK SC0680 was 0 stock at GBP 61.64)."
     " SC0681 (16 GB eMMC) same price is the drop-in alternative", "The Pi Hut UK"),
    ("Raspberry Pi CM4 IO Board (SC0326)", 1, 26.15, DK, "DigiKey UK"),
    ("40-way IDC ribbon 152 mm, socket-socket (Assmann H3AAH-4006G): main board J to CM4IO J8", 1, 1.30, DK, "DigiKey UK"),
    ("CM4IO 12 V pigtail: JST VH 2-pin housing to 2.1 mm DC plug, 200 mm", 1, 3.00, "est.", "LCSC / RS UK"),
    ("U.FL-U.FL 1.13 mm jumper 100 mm (Taoglas CAB.6012), main-board port to receiver J3/J4 (#34: ports sit right "
     "behind each receiver, 3.1 dB/m -> 0.3 dB + 2 mated pairs)", 16, 1.02,
     "RS UK 069-0832, read by the coordinator 2026-11-01 (stock unconfirmed); alternative LCSC C7541876 (Kinghelm)",
     "RS UK"),
    ("Neutrik NE8FDP etherCON RJ45 feedthrough (rear panel)", 1, 12.78, DK, "DigiKey UK"),
    ("Cat6 patch 0.3 m, NE8FDP to CM4IO RJ45", 1, 2.00, "est.", "RS UK / Farnell UK"),
    ("Panel-mount USB-C socket to micro-B plug, 30 cm, M3 ears 20 mm apart (Adafruit 4056; CM4IO rpiboot port, RK-1;"
     " no CC resistors: service with a USB-A-to-C lead)", 1, 3.83,
     "The Pi Hut UK SKU 103462, GBP 4.60 inc VAT, read 2026-11-01 (sold out that day; Adafruit direct USD 4.95)",
     "The Pi Hut UK"),
    ("Mean Well GST60A12-P1J 12 V 5 A desktop brick, 2.1 mm plug, C14 inlet", 1, 14.50, DK + " (6,852 in stock)",
     "DigiKey UK"),
    ("UK mains cord BS1363 to C13, 1.83 m (AC-12206-UK)", 1, 8.35, DK + " (7,931 in stock)", "DigiKey UK"),
    ("Main board PCB, full JLCPCB order (#126 review): 5 x 4-layer 412 x 321.5 mm JLC04161H-7628 ENIG bare boards, the "
     "large framed stencil, the extended-part fees of the assembly, DHL for ~2 kg, UK import VAT and handling", 1, 300.00,
     "est. (reviewer's estimate GBP 250-350 for the whole order, mid value; the JLC quote page needs a browser, so quote "
     "before ordering); one board is used, four are spares", "JLCPCB (ships to UK)"),
    ("Hammond RM1U1913SBK 1U 19 in aluminium case, 330 mm deep (mech/rack.py; panels drilled per mech/out)", 1, 140.76,
     "Rapid Online 31-1555, read by the coordinator 2026-11-01, in stock; DigiKey UK HM996-ND GBP 142.98 (90 in stock)",
     "Rapid Online / DigiKey UK"),
    ("M3 x 11 mm F-F hex spacer + 2 x M3 x 6 screws: receiver mounts (2 per slot, mech.json H1/H2)", 16, 0.30,
     "est. (brass hex spacer class price)", "RS UK / Farnell UK"),
    ("M2.5 x 10 mm F-F spacer + screws: CM4IO above the main board", 4, 0.30, "est.", "RS UK / Farnell UK"),
    ("M3 x 5 mm F-F spacer + screws: main board to the case floor (8 holes)", 8, 0.25, "est.", "RS UK / Farnell UK"),
]

# Not on the backplane BOM, priced elsewhere and added by audit.py for the rack total. Antenna kit per rack, ex VAT
# (#34 cost-down, coordinator quotes 2026-11-01; audit.py Audit 5 sizes the coax from the wing geometry). All GBP ex
# VAT; UK VAT 20 % is added at checkout on every line (rack total inc VAT = 1.2 x). The brief asked for one CA3N030
# (30 ft) per wing; Audit 5 shows the far wing needs >= 13.6 m on the smallest venue (6 x 6 m) and 21.5 m on the
# 12 x 12 m one, so the far wing keeps the CA3N075 (+GBP 42.22; a CA3N050 covers stages <= 6 m wide, GBP 61.07).
# The N-socket/BNC-plug adapter replaces the GBP 37.09 LCCA30301-FT1.5 lead: GBP 28.69 less per wing and 0.1 dB
# instead of ~0.2 dB plus a mated pair.
ANTENNA_KIT = [  # (item, qty, gbp_each, source)
    ("L-com HG2409P-NF 8 dBi 2.4 GHz flat patch", 2, 72.12, "ITM Components UK (ADR-0016)"),
    ("L-com CA3N030 CA-400 N-male/N-male 30 ft (9.14 m): rack -> near-wing boom", 1, 45.80,
     "ITM Components UK, ex VAT, read 2026-11-01"),
    ("L-com CA3N075 CA-400 N-male/N-male 75 ft (22.86 m): rack -> far-wing boom (12 m stage)", 1, 88.02,
     "ITM Components UK, ex VAT, read 2026-11-01"),
    ("Amphenol RF NF-BM-NT3G-50 N socket to BNC plug adapter at the rack BNC (replaces the GBP 37.09 LCCA30301-FT1.5)",
     2, 8.40, "RS UK 285-6398, ex VAT, search snippet 2026-11-01"),
    ("Thor LS003 4.0 m winch lighting stand, 35 mm top (antenna boom)", 2, 140.83,
     "Simply Sound and Lighting LS003, GBP 169 inc VAT, in stock, 2026-11-01"),
    ("L-com HGX-PMT07 stationary mast mount kit (U-bolts for 31.7-50.8 mm mast; fits the 35 mm stand top)", 2, 14.45,
     "ITM Components UK, ex VAT, in stock, 2026-11-01"),
]
ANTENNA_KIT_GBP = round(sum(q * g for _, q, g, _ in ANTENNA_KIT), 2)
