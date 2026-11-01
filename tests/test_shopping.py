import csv
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "hw/bom"))
import shopping  # noqa: E402

VAT = 0.20


def rows():
    with open(ROOT / "hw/bom/shopping.csv") as f:
        return list(csv.DictReader(f))


def test_line_totals_and_vat():
    for r in rows():
        assert abs(int(r["qty"]) * float(r["unit_gbp_ex"]) - float(r["line_gbp_ex"])) <= 0.005, r["mpn"]
        assert abs(float(r["line_gbp_ex"]) * VAT - float(r["line_vat"])) <= 0.005, r["mpn"]


def test_basket_and_grand_totals_add_up():
    req = [r for r in rows() if r["required"] == "yes"]
    base = {}
    for r in req:
        base[r["basket"]] = base.get(r["basket"], 0) + float(r["line_gbp_ex"])
    grand = sum(float(r["line_gbp_ex"]) for r in req)
    assert abs(sum(base.values()) - grand) < 0.005
    md = (ROOT / "docs/shopping-list.md").read_text()
    for b, v in base.items():
        assert f"| {b} | {v:,.2f} |" in md, b
    assert f"**{grand:,.2f}**" in md and f"**{grand * (1 + VAT):,.2f}**" in md
    cats = {}
    for r in req:
        cats[r["category"]] = cats.get(r["category"], 0) + float(r["line_gbp_ex"])
    assert abs(sum(cats.values()) - grand) < 0.005
    assert "Rapid Online" in base and "RACK" not in base


def test_every_line_priced_and_sourced():
    for r in rows():
        assert r["price_status"] in ("quoted", "estimated", "placeholder"), r["mpn"]
        if r["price_status"] == "quoted":
            assert r["source_url"].startswith("http") and r["date_read"], r["mpn"]
        assert r["basket"] in shopping.BASKETS


def test_pack_and_rx_quantities_cover_four_boards():
    byk = {}
    for r in rows():
        byk[(r["basket"], r["mpn"])] = int(r["qty"])
    with open(ROOT / "hw/bom/pack_uk.csv") as f:
        for r in csv.DictReader(f):
            q = int(r["qty_per_pack"])
            if q and r["mpn"] in ("BT40NE", "SF-1206F300-2", "BWIPX1-SMA-1.13L150"):
                assert any(k[1] == r["mpn"] and v >= 4 * q for k, v in byk.items()), r["mpn"]
    assert any(k[1] == "BT40E" and v == 4 for k, v in byk.items())


def test_generated_files_current():
    assert subprocess.run([sys.executable, str(ROOT / "hw/bom/shopping.py"), "--check"]).returncode == 0


def test_no_mpn_appears_twice():
    seen = {}
    for r in rows():
        m = r["mpn"]
        if m in ("-", "TBD"):
            continue
        assert m not in seen, f"{m} is in both {seen[m]} and {r['basket']}"
        seen[m] = r["basket"]


def test_optional_cuts_stay_in_total_and_are_listed():
    cut = [r for r in rows() if r["required"] == "yes" and int(r["cut_qty"])]
    assert {r["mpn"] for r in cut} == {"nRF5340-DK", "nRF-PPK2", "LS003", "-"}
    md = (ROOT / "docs/shopping-list.md").read_text()
    assert "## Optional cuts the owner may choose" in md
    for r in cut:
        assert int(r["cut_qty"]) <= int(r["qty"])
    total = sum(int(r["cut_qty"]) * float(r["unit_gbp_ex"]) for r in cut)
    assert f"**{total:,.2f}**" in md


def test_rack_antenna_choices():
    by = {r["mpn"]: r for r in rows()}
    assert by["CA3N030"]["qty"] == "1" and by["CA3N075"]["qty"] == "1"
    assert "LCCA30301-FT1.5" not in by and by["NF-BM-NT3G-50"]["qty"] == "2"
