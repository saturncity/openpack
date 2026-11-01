"""BabbleSim BLE_simple modem interference model in Python, for quick sweeps (#89, docs/analysis/r1-uk-isolation.md).

Tables come from BabbleSim ext_2G4_modem_BLE_simple/src/modem_BLE_simple.c (Apache-2.0, Oticon/Nordic): the Rx
filter power gains (channel_filter_Prop2 for BLE 2M, channel_filter_BLE for 1M) and TxSpectrum_WLAN, all on a
200 kHz grid and symmetric, so only half of each table is stored. The computation is modem_analog_rx() (overlap of
the interferer spectrum with the Rx filter) and modem_digital_perf_ber() (BER = Q(sqrt(SNR - NFExtra)) with the
-35 dB digital floor). Defaults: NFAna 4 dB, NFExtra 2 dB. This is the twin's physics, not the silicon's.
"""
import math

RES_MHZ = 0.2
_P2 = [1.0000e-06, 1.5849e-06, 2.5119e-06, 3.9811e-06, 6.3096e-06, 7.9433e-06, 1.0000e-05, 1.2589e-05, 1.5849e-05,
       1.9953e-05, 2.5119e-05, 3.1623e-05, 3.9811e-05, 5.0119e-05, 6.3096e-05, 7.9433e-05, 1.0000e-04, 1.2589e-04,
       1.5849e-04, 1.9953e-04, 2.5119e-04, 3.1623e-04, 3.9811e-04, 5.0119e-04, 6.3096e-04, 1.0000e-03, 1.5849e-03,
       3.1623e-03, 6.3096e-03, 3.1565e-02, 5.2087e-02, 6.4973e-02, 1.3748e-01, 2.0369e-01, 4.3440e-01, 8.5992e-01,
       1.0097, 1.0097, 1.0097, 1.0097, 1.0097]           # channel_filter_Prop2[0..40], centre last
_B1 = [1.0000e-06, 1.2589e-06, 1.5849e-06, 1.9953e-06, 2.5119e-06, 3.1623e-06, 5.0119e-06, 1.0000e-05, 3.1623e-05,
       1.0000e-04, 3.1623e-04, 1.0000e-03, 3.1623e-03, 1.0000e-02, 3.9811e-02, 1.1398e-01, 2.6304e-01, 6.7212e-01,
       7.9446e-01, 9.8531e-01, 1.1791]                   # channel_filter_BLE[0..20]
_WS = [1.511874e-06, 3.797656e-06, 9.539280e-06, 1.511874e-05, 2.396159e-05, 3.797656e-05, 6.753293e-05,
       9.539280e-05, 1.347459e-04, 1.903337e-04, 2.688534e-04, 3.797656e-04, 4.565786e-04, 3.016585e-04,
       3.585218e-04, 5.617144e-04, 7.071566e-04, 8.501892e-04, 7.577319e-04, 1.200924e-03]  # TxSpectrum_WLAN[0..19]
_WMAIN, _WDC = 1.200924e-02, 2.396159e-03               # [20..101] flat, [61] = DC notch
_T2 = [1.4055e-05, 5.6012e-05, 1.5134e-04, 2.1890e-04, 1.2972e-04, 3.2762e-04, 3.3251e-03, 1.4459e-02, 4.1335e-02,
       8.0105e-02, 1.1656e-01, 1.5506e-01, 1.7652e-01]  # TxSpectrum_Prop2[0..12] (BLE 2M), centre last


def _full(half):
    return half + half[-2::-1]


RX_FILTER = {"2M": _full(_P2), "1M": _full(_B1)}
TX2M = _full(_T2)
WLAN = _WS + [_WMAIN] * 41 + [_WDC] + [_WMAIN] * 41 + _WS[::-1]
assert len(RX_FILTER["2M"]) == 81 and len(RX_FILTER["1M"]) == 41 and len(WLAN) == 123
assert abs(sum(WLAN) - 1) < 1e-5


def through_filter_db(off_mhz, phy="2M", spec=None):
    """Share of one interferer's power (dB) that lands in the receiver's channel filter, offset off_mhz.
    spec: interferer spectrum on the 200 kHz grid (default Wi-Fi, TX2M for a neighbouring pack)."""
    spec = WLAN if spec is None else spec
    filt, d = RX_FILTER[phy], round(abs(off_mhz) / RES_MHZ)
    hr, hi = len(filt) // 2, len(spec) // 2
    s = sum(a * spec[k - hr + d + hi] for k, a in enumerate(filt) if 0 <= k - hr + d + hi < len(spec))
    return 10 * math.log10(s) if s > 0 else -300.0


def wifi_through_filter_db(off_mhz, phy="2M"):
    return through_filter_db(off_mhz, phy)


def per(sinr_db, bits, nf_extra=2.0, floor_db=-35.0):
    """Packet error vs SINR at the modem input, BLE_simple BER model, all bits independent."""
    nu = 10 ** (-(sinr_db - nf_extra) / 10) + 10 ** (floor_db / 10)
    ber = 0.5 * math.erfc(math.sqrt(1 / nu) / math.sqrt(2))
    return 1 - (1 - ber) ** bits


def sinr_db(f_mhz, wifi_mhz, wanted_dbm, wifi_dbm, phy="2M", nf_db=4.0):
    """SINR of a carrier at f_mhz while Wi-Fi channels wifi_mhz all transmit at wifi_dbm (at the antenna port)."""
    bw = {"2M": 2.5e6, "1M": 1.1e6}[phy]
    n = 10 ** ((-174 + 10 * math.log10(bw) + nf_db) / 10)
    i = sum(10 ** ((wifi_dbm + wifi_through_filter_db(f_mhz - w, phy)) / 10) for w in wifi_mhz)
    return wanted_dbm - 10 * math.log10(n + i)


def copy_loss(f_mhz, wifi_mhz, wanted_dbm, wifi_dbm, busy, bits, phy="2M"):
    """Expected copy loss: each Wi-Fi channel is on air a fraction busy of the time (independent channels);
    the copy fails with the PER of the SINR against the channels on air (worst single channel counted)."""
    ok = 1.0
    for w in wifi_mhz:
        ok *= 1 - busy * per(sinr_db(f_mhz, [w], wanted_dbm, wifi_dbm, phy), bits)
    return 1 - ok


def isolation_needed_db(f_mhz, wifi_mhz, wanted_dbm, wifi_dbm, bits, per_max=1e-3, phy="2M"):
    """Extra wanted-to-Wi-Fi isolation (dB) until the copy's PER with Wi-Fi on air is <= per_max."""
    for x in range(0, 400):
        if per(sinr_db(f_mhz, wifi_mhz, wanted_dbm + x / 10, wifi_dbm, phy), bits) <= per_max:
            return x / 10
    return 40.0
