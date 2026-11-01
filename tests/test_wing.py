"""Wing-antenna model and the RX-5 replay used by run.py --geometry (#101, ADR-0021)."""
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "sim/loss"))
import wing_geometry as wg  # noqa: E402


def _run_py():
    spec = importlib.util.spec_from_file_location("g2run", ROOT / "tests/bsim/scenarios/run.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.RX5.update(probe=1000, hyst=6)
    return mod


def test_threshold_matches_audit4():
    assert -13 <= wg.ci_threshold_db(2423) <= -11.5
    assert wg.neighbour_tolerance_db(3) < 10 < wg.neighbour_tolerance_db(5)


def test_rule_holds_every_venue():
    for v in wg.VENUES:
        assert wg.summary(wg.evaluate(v, wg.RULE))["worst_best"] > -wg.MARGIN_DB
        assert wg.near_far(v, wg.RULE)["worst"] > -wg.MARGIN_DB


def test_rx5_leaves_a_blocked_antenna_and_stays():
    run = _run_py()
    n = 3000
    ok_l = [i < 500 for i in range(n)]      # antenna L (stronger RSSI) blocked from frame 500
    ok_r = [True] * n
    got, used, sw = run.rx5_replay([ok_l, ok_r], [-40, -50], 0)
    lost = [not g for g in got]
    assert sum(lost[500:600]) == 6 + 10     # ages 1 dB per miss until R leads by hyst (6 dB) + dRSSI (10 dB)
    assert [i for i in range(600, n) if lost[i]] == [1000, 2000]   # then only the probes of dead L
    assert all(u == 1 for i, u in enumerate(used[600:], 600) if i % 1000) and sw == 1


def test_rx5_probe_cost_scales_with_interval():
    run = _run_py()
    n = 10000
    ok = [[True] * n, [False] * n]          # the other antenna never hears this copy
    got100, *_ = run.rx5_replay(ok, [-40, -60], 1, probe=100)
    got1000, *_ = run.rx5_replay(ok, [-40, -60], 1, probe=1000)
    assert n - sum(got100) == 100 and n - sum(got1000) == 10
