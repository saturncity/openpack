import csv
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "hw/bom"))


def test_every_pack_mpn_has_uk_row():
    import audit
    audit_refs = {r[0] for r in audit.bom_pack()}
    assert audit_refs
    with open(ROOT / "hw/pack/out/bom.csv") as f:
        mpns = {r["mpn"] for r in csv.DictReader(f) if r["refs"] in audit_refs and r["mpn"] != "-"}
    with open(ROOT / "hw/bom/pack_uk.csv") as f:
        uk = {r["mpn"] for r in csv.DictReader(f)}
    assert not (mpns - uk), f"MPNs missing from hw/bom/pack_uk.csv: {sorted(mpns - uk)}"


def test_uk_total_runs():
    import uk_total
    t4, t100 = uk_total.totals()
    assert 0 < t100 <= t4
