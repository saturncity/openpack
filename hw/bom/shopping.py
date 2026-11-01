"""Build hw/bom/shopping.csv and docs/shopping-list.md (issue #36, ADR-0019).

    python3 hw/bom/shopping.py          # rewrite both files
    python3 hw/bom/shopping.py --check  # exit 1 if either is stale

Pack and receiver lines are derived from hw/bom/pack_uk.csv and hw/rx/out/bom.csv so quantities follow the boards.
Hand-entered lines (bench, antennas, fab, mechanical) are in MANUAL below. The rack is a placeholder (#34).
All GBP, ex VAT; VAT 20 % on everything (LCSC / JLCPCB: collected at checkout, no duty under GBP 135 per order).
"""
import csv
import math
import pathlib
import sys
from collections import OrderedDict

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent.parent
VAT = 0.20
N_PACKS = 4
N_RX = 4          # one receiver sub-board per pack (ADR-0018 slot per carrier); the rack has 8 slots, 4 are used
RX_Q4_UPLIFT = 1.30  # hw/rx prices are qty-100; pack_uk.csv shows qty-4 is ~1.3x qty-100 for active parts
D_REPO = "2026-10-31"
D_NOW = "2026-11-01"

BASKETS = [  # order = basket order in the list
    "Digi-Key UK", "Mouser UK", "Farnell UK", "RS UK", "LCSC", "JLCPCB",
    "ITM Components", "Simply Sound & Lighting", "The Pi Hut", "Thomann", "tinySA reseller (UK)",
]
SEARCH = {
    "Digi-Key UK": "https://www.digikey.co.uk/en/products/result?keywords=",
    "Mouser UK": "https://www.mouser.co.uk/c/?q=",
    "Farnell UK": "https://uk.farnell.com/w/search?st=",
    "RS UK": "https://uk.rs-online.com/web/c/?searchTerm=",
    "LCSC": "https://www.lcsc.com/search?q=",
}
FIELDS = ["basket", "category", "item", "mpn", "qty", "unit_gbp_ex", "line_gbp_ex", "line_vat", "price_status",
          "source_url", "date_read", "required", "reason", "notes"]

CAT_BENCH, CAT_PACK, CAT_RX, CAT_ANT, CAT_FAB, CAT_MECH, CAT_SHIP, CAT_RACK = (
    "Bench kit", "Packs x4", "Receivers x4", "Antennas, coax, stands", "PCB fabrication", "Mechanical and cells",
    "Shipping", "RACK (pending #34)")


def line(basket, cat, item, mpn, qty, unit, status, url, date, reason, notes="", required=True):
    return dict(basket=basket, category=cat, item=item, mpn=mpn, qty=qty, unit_gbp_ex=unit, price_status=status,
                source_url=url, date_read=date, required="yes" if required else "optional", reason=reason, notes=notes)


# ---------------------------------------------------------------- hand-entered lines
Q, E = "quoted", "estimated"
MANUAL = [
    # Bench kit
    line("Digi-Key UK", CAT_BENCH, "nRF5340-DK", "nRF5340-DK", 2, 40.00, E, SEARCH["Digi-Key UK"] + "nRF5340-DK", "",
         "Phase 5 DK bring-up (#38): ADC/DAC delay, T_GAP, lock, end-to-end latency. Second DK is the peer.",
         "Estimate from memory of ~GBP 40-48 ex VAT; page not readable 2026-11-01 (fetch timed out). Also stocked by Mouser UK and Farnell UK."),
    line("Digi-Key UK", CAT_BENCH, "Nordic Power Profiler Kit II", "nRF-PPK2", 1, 75.00, E, SEARCH["Digi-Key UK"] + "nRF-PPK2", "",
         "#38 FEM and pack current; sources/measures 0.8-5 V for the battery-life check.",
         "Estimate; page not readable 2026-11-01. Also Mouser UK / Farnell UK."),
    line("Digi-Key UK", CAT_BENCH, "TI PCM1840 evaluation module", "PCM1840EVM", 1, 55.00, E, SEARCH["Digi-Key UK"] + "PCM1840EVM", "",
         "#38 ADC delay and noise measured before the pack is populated (ADR-0019 mitigation).",
         "Estimate; TI also sells direct but ships from US. If DK UK has no stock use Mouser UK 595-PCM1840EVM."),
    line("Digi-Key UK", CAT_BENCH, "Tag-Connect TC2030-IDC-NL cable (2x5 1.27 mm to TC2030 no-legs)", "TC2030-IDC-NL", 1, 32.00, E,
         SEARCH["Digi-Key UK"] + "TC2030-IDC-NL", "",
         "Programs and debugs the pack and receiver boards (both carry TC2030 pads only, no header). Not in either BOM, so a missing item.",
         "Estimate; plugs into the DK's debug-out header. Alternative: TC2030-CTX-NL (no ribbon)."),
    line("The Pi Hut", CAT_BENCH, "PCM5102A I2S DAC breakout board", "PCM5102A module", 1, 9.00, E, "https://thepihut.com", "",
         "#38 I2S backend and the DAC output chain on the bench; FLT/XSMT strap tests (ADR-0017).",
         "Estimate; stock not verified (Pi Hut search fetch 2026-11-01 returned nothing useful). Any PCM5102A (not PCM5100) breakout works; fall back to a HiFiBerry DAC Zero (same chip)."),
    line("The Pi Hut", CAT_BENCH, "8-channel 24 MHz USB logic analyser (Cypress FX2 clone, sigrok fx2lafw)", "FX2-LA-8CH", 1, 9.50, E,
         "https://thepihut.com", "",
         "#38 end-to-end latency via GPIO toggles; I2S and frame-clock phasing (ADR-0020/0022). Cheapest adequate: 24 MHz sampling is 40 ns against ms-scale latency.",
         "Estimate; Pi Hut search fetch 2026-11-01 found no analyser. Same part is sold by Rapid Electronics and Pimoroni; the choice is a commodity clone."),
    line("The Pi Hut", CAT_BENCH, "Micro-USB cable 1 m (DK, PPK2, programming)", "USB-A to micro-B 1 m", 3, 2.50, E, "https://thepihut.com", "",
         "Powers/connects 2 DKs and the PPK2.", "Estimate."),
    line("The Pi Hut", CAT_BENCH, "Dupont jumper wires F-F 20 cm (40-pack)", "Dupont F-F 40", 2, 2.50, E, "https://thepihut.com", "",
         "Logic analyser probes to DK pins and board test pads (TP1-TP13 on the receiver).", "Estimate."),
    line("Thomann", CAT_BENCH, "Lavalier microphone, 3.5 mm TRS, omni electret", "Samson LM5 (or equivalent)", 1, 15.00, E,
         "https://www.thomann.de/gb/samson_lm5.htm", "",
         "Real source for the preamp/ADC chain on the bench (noise, THD, start-up) and R5 listening checks.",
         "Estimate; Thomann UK site ships to the UK (GBP prices inc VAT at checkout). Final show mic is the owner's choice and out of scope."),
    line("Thomann", CAT_BENCH, "Cable 3.5 mm TRS to 3.5 mm TRS 1.5 m", "TRS-TRS 1.5 m", 1, 3.50, E, "https://www.thomann.de/gb/", "",
         "DAC output to the PC sound card / headphone amp during #38.", "Estimate."),
    line("Farnell UK", CAT_BENCH, "SMA attenuator 20 dB 2 W DC-6 GHz", "SMA-ATT-20DB", 1, 12.00, E, SEARCH["Farnell UK"] + "SMA+attenuator+20dB", "",
         "Protects the tinySA input (max +6 dBm) while measuring conducted TX power at the pack u.FL (limit +7 dBm, ADR-0016/design-log).",
         "Estimate; class part, choose any 50 ohm 2 W SMA 20 dB with DC-6 GHz rating."),
    line("Farnell UK", CAT_BENCH, "SMA attenuator 10 dB 2 W DC-6 GHz", "SMA-ATT-10DB", 1, 10.00, E, SEARCH["Farnell UK"] + "SMA+attenuator+10dB", "",
         "Stacks to 30 dB for the nRF21540 +20 dBm case if the FEM is fitted.", "Estimate."),
    line("Farnell UK", CAT_BENCH, "u.FL to SMA female pigtail 150 mm", "U.FL-SMA-F-150", 2, 4.00, E, SEARCH["Farnell UK"] + "u.FL+SMA+pigtail", "",
         "Connects the pack/receiver u.FL (and the DK RF connector) to the SMA attenuator and analyser.", "Estimate."),
    line("Farnell UK", CAT_BENCH, "SMA male-male adapter", "SMA-MM", 2, 3.00, E, SEARCH["Farnell UK"] + "SMA+male+male+adapter", "",
         "Joins attenuators to the tinySA.", "Estimate."),
    line("tinySA reseller (UK)", CAT_BENCH, "tinySA Ultra spectrum analyser 100 kHz-5.3 GHz", "tinySA Ultra", 1, 118.00, E, "https://tinysa.org/wiki/pmwiki.php?n=Main.Buy", "",
         "#92 / design-log AN-risk 2: conducted TX power and the 99 % OBW and 2483.5-2487.6 MHz emissions on a pack at 2482 MHz (limit 2.51 MHz OBW). Cheapest adequate; indicative, not a lab EN 300 328 report.",
         "Estimate (~GBP 140 inc VAT). NO UK stockist confirmed: tinysa.org lists resellers, Amazon UK is the usual route. If it cannot be bought in the UK, use a Siglent SSA1015X-class unit from RS UK instead (about GBP 700 ex VAT)."),
    line("tinySA reseller (UK)", CAT_BENCH, "NanoVNA-H4 vector network analyser", "NanoVNA-H4", 1, 75.00, E, "https://nanovna.com", "",
         "Optional: RF-11 (QPQ1907 loss at band edges), antenna/coax S11, receiver RF chain S2P checks.",
         "Optional. Estimate. UK stockist not confirmed.", False),
    line("RS UK", CAT_BENCH, "Rigol DS1054Z 50 MHz 4-channel oscilloscope", "DS1054Z", 1, 310.00, E, SEARCH["RS UK"] + "DS1054Z", "",
         "Optional: preamp step into 10 nF, start-up transient, boost ripple, P48/hot-plug transients. The PPK2 and logic analyser do not see analogue waveforms.",
         "Optional. Estimate; skip if the owner already has a scope.", False),

    # Antennas, coax, stands (decided)
    line("ITM Components", CAT_ANT, "L-com HyperLink 2.4 GHz 8 dBi flat patch, N-female", "HG2409P-NF", 2, 72.12, Q,
         "https://www.itm.com", D_NOW,
         "One per wing (ADR-0021); R1 antenna.", "Price from ADR-0016 (ITM Components UK). Assumed ex VAT (ITM lists ex VAT by default); ADR does not state the basis."),
    line("ITM Components", CAT_ANT, "L-com CA3N030 400-series coax N-male/N-male 9.14 m (30 ft)", "CA3N030", 2, 45.80, Q,
         "https://www.itm.com", D_NOW,
         "Antenna to rack feed, owner decision. Near-wing length per design-log.",
         "Owner-given ITM price GBP 45.80 ex VAT. OPEN: the design-log rack placeholder says the far wing may need CA3N075 (22.86 m, near the 6 dB RK-2 budget); the rack agent decides. Not priced, not included."),
    line("ITM Components", CAT_ANT, "L-com LCCA30301-FT1.5 BNC-male to N-female jumper 45 cm", "LCCA30301-FT1.5", 2, 37.09, Q,
         "https://www.itm.com", D_NOW,
         "Joins each coax to the RK-1 BNC on the rack (ADR-0016, 4.2 dB of the 6 dB RK-2 budget).",
         "Price from ADR-0016 (supplier not stated there; assumed ITM as the L-com stockist). Listed here with the antennas because it is antenna feed, not backplane."),
    line("ITM Components", CAT_ANT, "L-com HGX-PMT07 pole mount bracket for HG2409P", "HGX-PMT07", 2, 14.45, Q,
         "https://www.itm.com", D_NOW, "Holds each panel on the stand pole at 4 m, tilted 10 deg down (ADR-0021).", "Owner-given ITM price ex VAT."),
    line("Simply Sound & Lighting", CAT_ANT, "Thor winch-up lighting stand", "LS003", 2, 140.83, Q,
         "https://www.simplysoundandlighting.co.uk", D_NOW,
         "4 m mounting height in each wing where the venue has no boom (ADR-0021; install doc step 3).",
         "Owner-given ~GBP 140.83 ex VAT each. Large item: delivery is a separate line (estimated)."),

    # Mechanical and cells
    line("RS UK", CAT_MECH, "Protected 18650 Li-ion cell, button top, ~3000 mAh", "18650 protected", N_PACKS + 2, 7.00, E,
         SEARCH["RS UK"] + "protected+18650", "",
         "PK-6: one removable protected 18650 per pack, no on-board charging. 4 + 2 spares for bench and failure.",
         "Estimate. Must be PROTECTED (the pack has no cell protection) and button-top to suit the printed cradle contacts. Li-ion cells are restricted for post; if RS UK will not ship, buy from Farnell UK."),
    line("RS UK", CAT_MECH, "External 18650 charger, 2-bay, with display", "18650 charger 2-bay", 1, 18.00, E, SEARCH["RS UK"] + "18650+charger", "",
         "The pack has no charging circuit (PK-6), so cells charge externally.", "Estimate."),
    line("RS UK", CAT_MECH, "PETG filament 1.75 mm, 1 kg spool (enclosures + belt clips)", "PETG 1 kg", 1, 18.00, E, SEARCH["RS UK"] + "PETG+1.75mm", "",
         "ADR-0008: printed PETG body, clip and cradle on the Bambu A1 mini (assumed owned, not listed). About 30 g per pack; 1 kg covers reprints.",
         "Estimate. Any PETG that prints on textured PEI; Bambu A1 mini is not on the list because nothing in the repo says the owner lacks it."),
    line("RS UK", CAT_MECH, "M2 x 6 pan-head thread-forming screws, pack of 100", "M2x6 PT pan", 1, 6.00, E, SEARCH["RS UK"] + "M2x6+thread+forming", "",
         "2 per pack board retention into printed bosses (ADR-0008, pack_uk.csv).", "Estimate; replaces the US Fastener Superstore source in pack_uk.csv."),
    line("RS UK", CAT_MECH, "M2 brass heat-set inserts, pack of 50", "M2 heat-set insert", 1, 7.00, E, SEARCH["RS UK"] + "M2+heat+set+insert", "",
         "Clip screws into 7 mm bosses (ADR-0008), two per pack plus spares.", "Estimate."),
    line("RS UK", CAT_MECH, "Silicone hookup wire 24 AWG, 5 m red/black", "24AWG silicone", 1, 5.00, E, SEARCH["RS UK"] + "24AWG+silicone+wire", "",
         "Cell leads (2 x 60 mm per pack) and the 31 mm whip wire.", "Estimate."),
    line("Farnell UK", CAT_MECH, "Lead-free low-temperature solder paste, 10 g syringe", "Chip Quik SMDLTLFP10T5", 2, 14.00, E,
         SEARCH["Farnell UK"] + "SMDLTLFP10T5", "",
         "Bare PCBs plus stencil, assembly waits for bench results (ADR-0019); hot-plate reflow. 8 boards of about 70-95 parts each.",
         "Estimate. Reflow hot plate/oven is not listed: nothing in the repo says whether the owner has one. If not, add a hot plate (about GBP 40) before assembly."),

    # PCB fabrication (JLCPCB)
    line("JLCPCB", CAT_FAB, "Pack PCB, 4-layer, 73.5 x 35.1 mm, 1.6 mm, ENIG, 10 pcs", "pack.kicad_pcb", 1, 28.00, E,
         "https://cart.jlcpcb.com/quote", "",
         "4 packs plus 6 spares so a re-spin or a bad solder job costs boards, not a new order (ADR-0019). Size/layers from hw/pack/out/fab/pack-job.gbrjob.",
         "Estimate: JLCPCB 4-layer, 10 pcs, small area, plus ENIG surcharge. Gerbers: hw/pack/out/fab/gerber."),
    line("JLCPCB", CAT_FAB, "Pack stencil, top side only, frameless", "pack stencil", 1, 8.00, E, "https://cart.jlcpcb.com/quote", "",
         "All 70 pack parts are on Top (cpl_jlc.csv), one stencil.", "Estimate."),
    line("JLCPCB", CAT_FAB, "Receiver sub-board PCB, 4-layer, 48.1 x 90.1 mm, 1.6 mm, ENIG, 10 pcs", "rx.kicad_pcb", 1, 36.00, E,
         "https://cart.jlcpcb.com/quote", "",
         "4 receivers plus 6 spares (50 ohm RF traces, 4-layer). Size/layers from hw/rx/out/fab/rx-job.gbrjob.",
         "Estimate; 5 pcs would do for 4 boards but 10 costs little more. Gerbers: hw/rx/out/fab/gerber."),
    line("JLCPCB", CAT_FAB, "Receiver stencil, top side only, frameless", "rx stencil", 1, 8.00, E, "https://cart.jlcpcb.com/quote", "",
         "All 95 receiver parts are on Top, one stencil.", "Estimate."),

    # Shipping
    line("Digi-Key UK", CAT_SHIP, "Delivery (UPS, duty-paid)", "-", 1, 0.00, E, "https://www.digikey.co.uk", "",
         "Free above the Digi-Key UK threshold (about GBP 33, unconfirmed); basket is far above it.", "Estimate."),
    line("Mouser UK", CAT_SHIP, "Delivery", "-", 1, 6.00, E, "https://www.mouser.co.uk", "",
         "Small basket; Mouser UK free-shipping threshold not confirmed.", "Estimate."),
    line("Farnell UK", CAT_SHIP, "Delivery", "-", 1, 4.00, E, "https://uk.farnell.com", "",
         "Under the free-delivery threshold (older sources say GBP 20 ex VAT, unconfirmed).", "Estimate."),
    line("RS UK", CAT_SHIP, "Delivery", "-", 1, 0.00, E, "https://uk.rs-online.com", "",
         "Free over GBP 50 ex VAT (pack-parts-uk-draft.md); basket is above it.", "Estimate."),
    line("LCSC", CAT_SHIP, "Shipping to the UK (courier) + import VAT at checkout", "-", 1, 12.00, E, "https://www.lcsc.com", "",
         "LCSC to UK is a worldwide courier. Order is under GBP 135, so VAT (20 %) is collected at checkout and there is no duty.",
         "Estimate; UK shipping option not confirmed (LCSC page unreadable per pack-parts-uk-draft.md)."),
    line("JLCPCB", CAT_SHIP, "Shipping to the UK (DHL) + import VAT at checkout", "-", 1, 16.00, E, "https://cart.jlcpcb.com/quote", "",
         "JLCPCB collects UK VAT (20 %) at checkout; no duty under GBP 135.", "Estimate."),
    line("ITM Components", CAT_SHIP, "Delivery (antennas and coax)", "-", 1, 10.00, E, "https://www.itm.com", "",
         "Coax drums are heavy.", "Estimate."),
    line("Simply Sound & Lighting", CAT_SHIP, "Delivery (2 stands)", "-", 1, 30.00, E, "https://www.simplysoundandlighting.co.uk", "",
         "Stands are about 10 kg each.", "Estimate."),
    line("The Pi Hut", CAT_SHIP, "Delivery", "-", 1, 3.50, E, "https://thepihut.com", "", "Standard.", "Estimate."),
    line("Thomann", CAT_SHIP, "Delivery to the UK", "-", 1, 8.00, E, "https://www.thomann.de/gb/", "",
         "Thomann ships from Germany; UK prices include VAT at checkout.", "Estimate."),
    line("tinySA reseller (UK)", CAT_SHIP, "Delivery", "-", 1, 4.00, E, "https://tinysa.org", "", "Estimate.", "Estimate."),

    # Rack placeholders (qty 0, excluded)
    line("RACK", CAT_RACK, "Backplane PCB(s) + stencil (hw/rack)", "TBD", 0, 0, "placeholder", "", "",
         "Rack main board: Wilkinson 1:8 per antenna, fused slots, CM4 carrier (ADR-0018). Numbers come from #34.", "Fill after the rack layout PR merges.", False),
    line("RACK", CAT_RACK, "Backplane parts (slot sockets, LNA, BAW filters, splitters, connectors)", "TBD", 0, 0, "placeholder", "", "",
         "From hw/rack BOM.", "Fill after the rack layout PR merges.", False),
    line("RACK", CAT_RACK, "1U chassis, CM4 + IO board, power supply, XLR/BNC panel parts", "TBD", 0, 0, "placeholder", "", "",
         "Rack enclosure and host (ADR-0018).", "Fill after the rack layout PR merges.", False),
]


# ---------------------------------------------------------------- derived pack / receiver lines
def is_passive(mpn):
    return mpn.startswith(("C_", "R_", "ALU_", "GRM")) or mpn.startswith("GRM")


def spares(unit, passive, order):
    if passive:
        return max(10, math.ceil(0.25 * order))
    return 1 if unit < 1.0 else 0


def basket_for_rx(dist):
    d = dist.lower()
    if d.startswith("lcsc"):
        return "LCSC"
    if "farnell" in d and "digikey" not in d and "mouser" not in d:
        return "Farnell UK"
    if "mouser" in d and "digikey" not in d and "digi-key" not in d and "farnell" not in d:
        return "Mouser UK"
    return "Digi-Key UK"


def derive():
    demand = OrderedDict()  # (basket, mpn) -> dict

    def add(key, qty, who, unit4, unit100, status, url, date, note, item):
        d = demand.setdefault(key, dict(qty=0, who=[], unit4=unit4, unit100=unit100, status=status, url=url,
                                        date=date, note=note, item=item))
        d["qty"] += qty
        d["who"].append(who)
        if who.startswith("pack"):  # pack_uk.csv price is the better-sourced one; prefer it
            d.update(unit4=unit4, unit100=unit100, status=status, url=url, date=date, note=note)

    with open(HERE / "pack_uk.csv") as f:
        for r in csv.DictReader(f):
            q = int(r["qty_per_pack"])
            dist, mpn = r["distributor"], r["mpn"]
            if q == 0 or dist in ("-", "") or dist.startswith("self") or mpn.startswith(("PCB-", "M2x6", "CELL-")):
                continue
            basket = {"Digi-Key UK": "Digi-Key UK", "Mouser UK": "Mouser UK", "LCSC": "LCSC"}[dist]
            blob = (r["notes"] + r["stock"]).upper()
            est = "ESTIMATE" in blob or "UNVERIFIED" in blob or "NOT CHECKED" in blob
            date = D_NOW if "2026-11-01" in blob else D_REPO
            url = r["url"]
            if url.rstrip("/").endswith((".co.uk", ".com")) or not url:
                url = SEARCH[basket] + mpn
            add((basket, mpn), q * N_PACKS, f"pack x{q}", float(r["gbp_qty4"]), float(r["gbp_qty100"]),
                E if est else Q, url, "" if est else date, r["notes"], r["ref"])

    with open(ROOT / "hw/rx/out/bom.csv") as f:
        for r in csv.DictReader(f):
            mpn, q = r["mpn"], int(r["qty"])
            if r["uk_distributor"] == "-" and not r["value"].startswith("U.FL-U.FL"):
                continue
            if r["value"].startswith("PCB"):
                continue
            if r["value"].startswith("U.FL-U.FL"):
                mpn, basket = "U.FL-U.FL-50MM", "LCSC"
            else:
                basket = basket_for_rx(r["uk_distributor"])
            unit = float(r["unit_gbp"])
            active = not is_passive(mpn) and unit >= 0.2
            src = r["source"]
            est = src.startswith("est") or "est." in src.lower()[:5] or active
            unit_adj = round(unit * RX_Q4_UPLIFT, 2) if active else unit
            quoted_exact = mpn == "BT40E"
            if quoted_exact:
                unit_adj, est = unit, False  # DK UK GBP 9.7765 quoted, used as is
            url = SEARCH[basket] + mpn
            note = (f"rx price from hw/rx/out/bom.csv ({src})" +
                    (f"; x{RX_Q4_UPLIFT} on the qty-100 figure for a 4-board order" if active and not quoted_exact else ""))
            add((basket, mpn), q * N_RX, f"rx x{q}", unit_adj, unit_adj, E if est else Q, url,
                "" if est else D_NOW, note, r["refs"])

    # extras from pack_uk.csv that need their own treatment
    out = []
    for (basket, mpn), d in demand.items():
        passive = is_passive(mpn)
        unit_ref = d["unit4"]
        sp = spares(unit_ref, passive, d["qty"])
        order = d["qty"] + sp
        unit = d["unit100"] if order >= 100 else d["unit4"]
        cat = CAT_PACK if all(w.startswith("pack") for w in d["who"]) else (
            CAT_RX if all(w.startswith("rx") for w in d["who"]) else "Packs x4 + Receivers x4")
        status = d["status"]
        if mpn == "BT40NE":  # BT40NE is the consigned module the brief names; keep price quoted
            pass
        reason = (f"Needed {d['qty']} ({'; '.join(d['who'])}; refs {d['item'][:40]}), +{sp} spare"
                  if sp else f"Needed {d['qty']} ({'; '.join(d['who'])})")
        out.append(line(basket, cat, d["item"][:60] if False else mpn, mpn, order, round(unit, 4), status,
                        d["url"], d["date"], reason, d["note"][:240]))
    return out


def all_lines():
    lines = derive() + MANUAL
    # tidy: item column readable
    for l in lines:
        l["qty"] = int(l["qty"])
        l["unit_gbp_ex"] = round(float(l["unit_gbp_ex"]), 4)
        l["line_gbp_ex"] = round(l["qty"] * l["unit_gbp_ex"], 2)
        l["line_vat"] = round(l["line_gbp_ex"] * VAT, 2)
    order = {b: i for i, b in enumerate(BASKETS + ["RACK"])}
    lines.sort(key=lambda l: (order[l["basket"]], l["category"] == CAT_SHIP, l["category"], l["mpn"]))
    return lines


def write_csv(lines, path):
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        for l in lines:
            w.writerow({k: l[k] for k in FIELDS})


def money(x):
    return f"{x:,.2f}"


def summarize(lines):
    base = OrderedDict()
    cat = OrderedDict()
    opt = 0.0
    for l in lines:
        if l["required"] != "yes":
            opt += l["line_gbp_ex"]
            continue
        base[l["basket"]] = base.get(l["basket"], 0) + l["line_gbp_ex"]
        cat[l["category"]] = cat.get(l["category"], 0) + l["line_gbp_ex"]
    return base, cat, opt


def render(lines):
    base, cat, opt = summarize(lines)
    tot = sum(base.values())
    est_lines = [l for l in lines if l["price_status"] == E and l["required"] == "yes" and l["category"] != CAT_SHIP]
    est_total = sum(l["line_gbp_ex"] for l in est_lines)
    q_total = sum(l["line_gbp_ex"] for l in lines if l["price_status"] == Q and l["required"] == "yes")
    o = []
    o.append("# OpenPack shopping list (issue #36, ADR-0019)\n")
    o.append("One purchase, bought once, after all design is done (ADR-0019). **Everything except the rack backplane**: "
             "the RACK section is a placeholder until the rack layout (#34) merges. Generated from `hw/bom/shopping.csv` "
             "by `python3 hw/bom/shopping.py`; do not edit this file by hand. A test (`tests/test_shopping.py`) checks that the totals add up.\n")
    o.append("## Totals\n")
    o.append("| Basket | Ex VAT (GBP) | VAT 20 % | Inc VAT |\n|---|---:|---:|---:|")
    for b, v in base.items():
        o.append(f"| {b} | {money(v)} | {money(v*VAT)} | {money(v*(1+VAT))} |")
    o.append(f"| **Grand total (required, no rack)** | **{money(tot)}** | **{money(tot*VAT)}** | **{money(tot*(1+VAT))}** |")
    o.append(f"| Optional items (not in total) | {money(opt)} | {money(opt*VAT)} | {money(opt*(1+VAT))} |")
    o.append(f"| RACK (pending #34) | TBD | TBD | TBD |\n")
    o.append(f"Of the required total, GBP {money(q_total)} ex VAT is **quoted** and the rest, GBP {money(tot-q_total)}, is **estimated** "
             f"(including shipping). Estimated prices are marked `estimated` in every table; none can be called a quote.\n")
    o.append("## How prices were read\n")
    o.append("- All prices GBP **ex VAT**; VAT 20 % shown separately and added in the inc-VAT column. Digi-Key UK, Mouser UK, Farnell UK, RS UK show ex- and inc-VAT side by side; ITM Components and the owner-given Simply Sound prices are ex VAT.\n"
             "- **quoted** = a price read from a source page, with its URL and read date. For pack lines these are the readings in `hw/bom/pack_uk.csv` (2026-10-31 for Digi-Key UK, 2026-11-01 for LCSC) and `hw/rx/out/bom.csv`; for the antennas, coax, mounts and stands they are the figures given by the owner or ADR-0016 on 2026-11-01. Prices are at the quantity of 4 packs (or the 100-tier when the order quantity reaches 100), not re-read today.\n"
             "- **estimated** = no page read (or the repo marks it ESTIMATE). On 2026-11-01 the web fetches of Farnell, Mouser and The Pi Hut timed out or returned nothing, so every bench kit price, all fab, mechanical and shipping lines are estimates. Re-check each basket before paying.\n"
             "- **LCSC and JLCPCB** orders to the UK: 20 % import VAT is collected at checkout, no duty under GBP 135 per consignment, courier shipping is a separate line. Split orders so each stays under GBP 135 ex VAT (the PCB order and parts order already do).\n"
             "- Quantities: pack lines are 4 packs; receiver lines are **4 receivers** (one per pack; the rack has 8 slots, 4 stay empty). Spares: passives max(10, 25 %), ICs under GBP 1 get 1 spare, dearer parts none. Lines used by both pack and receiver are merged into one line.\n"
             "- Parts the repo consigns elsewhere: BT40NE (pack) at Digi-Key UK GBP 16.34 at qty 4, BT40E (receiver) at Digi-Key UK GBP 9.78 (10 week lead on both; order first). F1 fuse SF-1206F300-2 at Digi-Key UK. No FEM is bought (U8 is not fitted).\n")
    o.append("## Gaps and decisions\n")
    o.append("- **Not UK-sourceable / unconfirmed:** the tinySA Ultra (no UK stockist confirmed; Amazon UK is the usual route), the NanoVNA (optional). Everything else is on a UK distributor's list but unverified in stock.\n"
             "- **Missing from the BOMs, added here:** Tag-Connect TC2030-IDC-NL (programming), protected 18650 cells, an external 18650 charger, solder paste, the u.FL pigtails and attenuators for conducted-power measurement.\n"
             "- **Open:** CA3N030 (9.14 m) is ordered for both wings by the owner; the design-log rack placeholder suggests the far wing may need CA3N075 (22.86 m). If so, swap one line when #34 lands. A reflow hot plate/oven and a multimeter are assumed owned.\n"
             "- **Not listed (assumed owned):** Bambu A1 mini (ADR-0008 says the owner has it), PC, soldering iron.\n")
    cur = None
    for b in BASKETS + ["RACK"]:
        bl = [l for l in lines if l["basket"] == b]
        if not bl:
            continue
        if b == "RACK":
            o.append("## RACK (pending #34): placeholder\n")
            o.append("Do not buy these yet. Pull in the numbers from the rack layout PR (#34) when it merges, then regenerate. Antennas, coax and stands are NOT here; they are in the ITM and Simply Sound baskets.\n")
        else:
            bt = base.get(b, 0)
            o.append(f"## Basket: {b}\n")
            o.append(f"**Basket total: GBP {money(bt)} ex VAT, VAT {money(bt*VAT)}, GBP {money(bt*(1+VAT))} inc VAT.**\n")
        o.append("| Item | Part number | Qty | Unit (GBP ex VAT) | Line total | Price | Link | Reason / what it unblocks |\n|---|---|---:|---:|---:|---|---|---|")
        for l in bl:
            tag = l["price_status"] + (f" {l['date_read']}" if l["date_read"] and l["price_status"] == Q else "")
            if l["required"] != "yes" and b != "RACK":
                tag += ", OPTIONAL"
            link = f"[link]({l['source_url']})" if l["source_url"] else "-"
            item = l["item"] if l["category"] in (CAT_BENCH, CAT_ANT, CAT_FAB, CAT_MECH, CAT_SHIP, CAT_RACK) else f"{l['category']} part"
            reason = l["reason"] + ((" " + l["notes"]) if l["notes"] else "")
            reason = reason.replace("|", "/")
            o.append(f"| {item} | {l['mpn']} | {l['qty']} | {l['unit_gbp_ex']:.4f} | {money(l['line_gbp_ex'])} | {tag} | {link} | {reason} |")
        o.append("")
    o.append("## Summary by category\n")
    o.append("| Category | Ex VAT | VAT 20 % | Inc VAT |\n|---|---:|---:|---:|")
    for c, v in cat.items():
        o.append(f"| {c} | {money(v)} | {money(v*VAT)} | {money(v*(1+VAT))} |")
    o.append(f"| **Total** | **{money(tot)}** | **{money(tot*VAT)}** | **{money(tot*(1+VAT))}** |\n")
    o.append("Shipping is its own category. Optional items are excluded. The RACK section is excluded (placeholder).\n")
    return "\n".join(o)


def main():
    lines = all_lines()
    csv_path, md_path = HERE / "shopping.csv", ROOT / "docs/shopping-list.md"
    if "--check" in sys.argv:
        import io
        buf = io.StringIO()
        w = csv.DictWriter(buf, fieldnames=FIELDS, lineterminator="\r\n")
        w.writeheader()
        for l in lines:
            w.writerow({k: l[k] for k in FIELDS})
        ok = csv_path.read_bytes().decode() == buf.getvalue() and md_path.read_text() == render(lines)
        sys.exit(0 if ok else 1)
    write_csv(lines, csv_path)
    md_path.write_text(render(lines))
    base, cat, opt = summarize(lines)
    for b, v in base.items():
        print(f"{b:28s} {v:9.2f}")
    t = sum(base.values())
    print(f"TOTAL ex {t:.2f}  VAT {t*VAT:.2f}  inc {t*(1+VAT):.2f}; optional {opt:.2f}")


if __name__ == "__main__":
    main()
