"""Per-pack UK BOM totals in GBP from pack_uk.csv, vs PK-12 (BOM <= $35 ex cell, qty 100).
Exchange rate is an ASSUMPTION (not fetched live); update if needed."""
import csv
import pathlib

VAT = 0.20
USD_PER_GBP = 1.31
RATE_DATE = "2026-10-31 (assumed, not live)"
PK12_USD = 35.0
HERE = pathlib.Path(__file__).resolve().parent


def totals(path=HERE / "pack_uk.csv"):
    t4 = t100 = 0.0
    with open(path) as f:
        for r in csv.DictReader(f):
            q = int(r["qty_per_pack"])
            t4 += q * float(r["gbp_qty4"])
            t100 += q * float(r["gbp_qty100"])
    return t4, t100


if __name__ == "__main__":
    t4, t100 = totals()
    print("Per pack (GBP)      ex VAT   inc VAT (20%)")
    print(f"  qty 4 packs      {t4:7.2f}   {t4*(1+VAT):7.2f}")
    print(f"  qty 100 packs    {t100:7.2f}   {t100*(1+VAT):7.2f}")
    usd = t100 * USD_PER_GBP
    print(f"qty100 ex VAT = ${usd:.2f} at {USD_PER_GBP} USD/GBP ({RATE_DATE}); PK-12 limit ${PK12_USD:.0f} -> {'OK' if usd <= PK12_USD else 'OVER'}")
