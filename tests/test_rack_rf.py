"""RK-2 (#33, ADR-0018): the 1:8 Wilkinson model (hw/rack/wilkinson.py) and the rack RF cascade (audit.py Audit 6).
numpy only; the scikit-rf cross-check runs where scikit-rf is installed (`pip install scikit-rf`, proposed for CI)."""
import importlib.util, math, pathlib
import numpy as np
import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


wk = _load("hw_rack_wilkinson_t", ROOT / "hw/rack/wilkinson.py")
audit = _load("audit_t", ROOT / "audit.py")
IDEAL = {**wk.STACKUP, "tand": 0.0, "sigma": 1e12, "rough_m": 0.0}


def test_microstrip_widths():
    w50, w70 = wk.width_for(50), wk.width_for(70.71)
    assert 0.34e-3 < w50 < 0.42e-3 and 0.17e-3 < w70 < 0.23e-3   # JLC 7628 0.21 mm class values
    assert w70 > 0.1e-3, "70.7 ohm arm stays above JLCPCB's 0.1 mm (4 mil) minimum track"
    assert 15e-3 < wk.quarter_wave_m(w70) < 19e-3


def test_ideal_tree_is_an_ideal_split():
    s = wk.sparams([wk.F0_HZ], s=IDEAL, l_iso=0.0)[0]
    il = -20 * np.log10(np.abs(s[1:, 0]))
    assert np.allclose(il, 10 * math.log10(8), atol=0.05)
    assert -20 * math.log10(abs(s[0, 0])) > 30
    iso = -20 * np.log10(np.abs(s[1:, 1:][~np.eye(8, dtype=bool)]))
    assert iso.min() > 30
    assert np.allclose(s, s.T, atol=1e-9), "reciprocal"


def test_band_performance_and_stackup_tolerance():
    r = wk.summary(11)
    assert r["il_db"] <= 11.0 and r["excess_db"] <= 2.0       # modelled 10.6 dB; audit adds 0.5 dB for layout
    assert r["iso_db"] >= 20 and r["rl_in_db"] >= 15 and r["rl_out_db"] >= 15
    assert r["imbalance_db"] <= 0.2
    for er in (4.2, 4.6):                                     # FR-4 er spread: the cut lengths still work
        t = wk.summary(5, s={**wk.STACKUP, "er": er},)
        assert t["iso_db"] >= 20 and t["rl_in_db"] >= 15 and t["il_db"] <= 11.2, er


def test_matches_scikit_rf():
    rf = pytest.importorskip("skrf")
    from skrf.circuit import Circuit
    from skrf.media import MLine
    s = wk.STACKUP
    f = rf.Frequency(2400, 2483.5, 5, "MHz")
    w50, w70 = wk.width_for(50), wk.width_for(70.71)
    ml = lambda w: MLine(frequency=f, w=w, h=s["h_m"], t=s["t_m"], ep_r=s["er"], tand=s["tand"],
                         rho=1 / s["sigma"], rough=s["rough_m"], z0_port=50)
    m50, m70 = ml(w50), ml(w70)
    lq = wk.quarter_wave_m(w70)
    feeds = (wk.FEED_IN_M, wk.FEED_12_M, wk.FEED_23_M, wk.FEED_OUT_M)
    cnx, n = [], [0]

    def name():
        n[0] += 1
        return f"n{n[0]}"

    port_in = Circuit.Port(f, "in", z0=50)
    feed = m50.line(feeds[0], "m", name=name())
    cnx.append([(port_in, 0), (feed, 0)])
    heads = [(feed, 1)]
    for st in range(3):
        nxt = []
        for h in heads:
            a, b = m70.line(lq, "m", name=name()), m70.line(lq, "m", name=name())
            cnx.append([h, (a, 0), (b, 0)])
            r = m50.resistor(wk.R_ISO, name=name()) ** m50.inductor(wk.L_ISO, name=name())
            r.name = name()
            for arm, rp in ((a, 0), (b, 1)):
                o = m50.line(feeds[1 + st], "m", name=name())
                cnx.append([(arm, 1), (r, rp), (o, 0)])
                nxt.append((o, 1))
        heads = nxt
    for i, h in enumerate(heads):
        cnx.append([h, (Circuit.Port(f, f"o{i}", z0=50), 0)])
    S = Circuit(cnx).network.s
    mine = wk.sparams(f.f)
    il_skrf, il_mine = -20 * np.log10(np.abs(S[:, 1:, 0])), -20 * np.log10(np.abs(mine[:, 1:, 0]))
    # same Z0 to ~2 %; this model's conductor loss is the higher (conservative) one
    assert np.all(il_mine >= il_skrf - 0.05) and np.all(il_mine - il_skrf <= 0.6)
    assert -20 * np.log10(np.abs(S[:, 0, 0])).min() >= 15
    assert -20 * np.log10(np.abs(S[:, 1, 2])).min() >= 20


def test_lna_meets_rk2():
    lna = audit.lna_at()
    assert lna["nf_max"] <= 2.0                                   # RK-2 / issue #33: NF <= 2 dB (worst case 0.9)
    assert lna["ip1db_min"] >= -10 and lna["iip3_min"] >= 0       # RK-2 input P1dB / IIP3 (worst case)
    assert 21 <= lna["gain"] <= 23


def test_cascade_keeps_the_r1_margin():
    wil = audit.wilkinson_db()
    nf_on = audit.cascade_nf_db(audit.rack_chain(audit.COAX_BUDGET_DB, True, True, wil))
    nf_byp = audit.cascade_nf_db(audit.rack_chain(audit.COAX_BUDGET_DB, False, True, wil))
    assert nf_on <= audit.AUDIT4_SYS_NF_DB < nf_byp               # module LNA on is required at the 6 dB budget
    assert audit.cascade_nf_db(audit.rack_chain(audit.COAX_ADR16_DB, False, True, wil)) <= audit.AUDIT4_SYS_NF_DB
    assert audit.r1_noise_cost_db(nf_on)[0] <= 0.5
