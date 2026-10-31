# Pack parts, UK shopping list for 4 packs

**DRAFT. NOT TO BE BOUGHT YET.** Prices were read 2026-10-31 from distributor pages or search snippets and are not a quote. The schematic may still change (the radio FEM line may be dropped). Source of truth: `hw/bom/pack_uk.csv`; totals from `python3 hw/bom/uk_total.py`.

## Rules that apply

- UK VAT is 20%. Digi-Key UK shows ex-VAT and inc-VAT unit prices side by side (for example BT40NE GBP 16.34 ex, 19.61 inc).
- LCSC and other overseas orders under GBP 135: VAT is collected at checkout, with no separate import-duty bill (post-Brexit rules). Above GBP 135 expect duty or VAT handling at the carrier.
- Delivery thresholds. RS UK: free over GBP 50 ex VAT (basket page, 2026). Farnell UK: older sources say GBP 20 ex VAT; unverified. Digi-Key UK and Mouser UK thresholds were not confirmed, so check at checkout. Digi-Reel packaging adds a GBP 4.50 fee, so choose Cut Tape.
- Digi-Key delivers UK orders duty-paid by courier. Pick UPS (DDP) over FedEx or DHL (VAT due on delivery).

## Baskets (qty for 4 packs, unit prices at that quantity, ex VAT)

| Basket | Lines | Ex VAT | Inc VAT | Delivery |
|---|---|---|---|---|
| 1. Digi-Key UK | every IC, connector, LED, switch, fuse, inductor, module (BT40NE) and capacitor in the CSV | about GBP 126.56 | about GBP 151.87 | probably free at this size; confirm |
| 2. Mouser UK | DMG2305UX-7 (x4, plus spares, since Digi-Key has 0 stock) | about GBP 0.44 for 4 | about GBP 0.53 | unknown; buy about 20 as spares so the delivery fee is worth paying, or use RS UK stock 827-0452 |
| 3. LCSC | BH-18650-B1BA002 x4 (about GBP 4.16); optionally PCBs from the same family of fabs | about GBP 4.16 | about GBP 4.99 (VAT at checkout) | LCSC shipping to the UK not confirmed (page unreadable) |
| Other (estimates) | PCB, enclosure, pigtail and whip | about GBP 18.80 | about GBP 22.56 | n/a |

Total for 4 packs: about GBP 150 ex VAT, about GBP 180 inc VAT, before delivery (Digi-Key lines are real; the "other" row and generic passives are estimates).

## Parts that need a decision before ordering

- **GRM31CR60J107ME39L (100 uF 1206)**: discontinued at Digi-Key UK. Proposed swap, Samsung CL31A107MQHNNNE at GBP 0.50. Check DC-bias derating. Schematic unchanged.
- **DMG2305UX-7**: 0 stock at Digi-Key UK; in stock at Mouser UK and RS UK (snippet data, not verified on the page).
- **BH-18650-B1BA002**: found only at LCSC. UK alternative, Keystone 1042 (SMD 18650 holder), has a different footprint, so a layout change would be needed.
- **BT40NE**: Digi-Key UK has 624 in stock with a 10-week lead time. For qty 4 take it from there; Fanstel direct is the alternative.
- **Generic passives**: not price-checked; estimates only. Order specific Samsung or Yageo parts when the BOM is frozen.
