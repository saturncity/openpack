"""Step 1 audit: airtime, latency, battery, thermal. Run: python3 audit.py"""

PHY_BPS = 2e6        # nRF5340 proprietary/BLE 2M PHY (its max)
PKT_OVH_B = 11       # preamble 2 + address 4 + header 2 + CRC 3
RAMP_US = 40         # nRF5340 fast ramp-up
GUARD_US = 30        # sync jitter guard, ponytail: guess, measure on hardware


def slot_us(payload_b):
    return (payload_b + PKT_OVH_B) * 8 / PHY_BPS * 1e6 + RAMP_US + GUARD_US


def payload_b(kbps, frame_ms):
    return round(kbps * frame_ms / 8)


def airtime(name, kbps, frame_ms, packs_per_channel, copies):
    used = slot_us(payload_b(kbps, frame_ms)) * packs_per_channel * copies
    budget = frame_ms * 1000
    ok = used <= budget * 0.9  # leave 10% for beacon/sync
    print(f"{name:<44} {used:7.0f}/{budget:5.0f} us  {used / budget:5.0%}  {'OK' if ok else 'FAIL'}")
    return ok


def latency_ms(frame_ms, codec_delay_ms, air_ms):
    adc, dac = 0.35, 0.40  # ~17/fs and ~19/fs filter group delay at 48 kHz
    merge = 0.2            # wait for 2nd diversity copy
    return adc + frame_ms + codec_delay_ms + air_ms + merge + dac


if __name__ == "__main__":
    print("== TDMA airtime (single 2.4 GHz channel, 2 Mbps) ==")
    a = airtime("A plan: LC3plus 160k, 8 packs, 1 ms", 160, 1.0, 8, 1)
    b = airtime("A' plan: LC3plus 160k, 8 packs, 2.5 ms frame", 160, 2.5, 8, 1)
    c = airtime("B PCM 24/48 (1152k), 1 pack/ch, 1 copy", 1152, 1.0, 1, 1)
    d = airtime("B' PCM 24/48, 1 pack/ch, 2 copies", 1152, 1.0, 1, 2)
    e = airtime("C ADPCM 6-bit (288k), 1 pack/ch, 2 copies", 288, 1.0, 1, 2)
    f = airtime("C' ADPCM 6-bit, 2 packs/ch, 2 copies", 288, 1.0, 2, 2)
    assert not a and not b, "plan's TDMA should not fit"
    assert c and not d and e

    print("\n== End-to-end latency ==")
    lc3 = latency_ms(2.5, 2.5, 0.3)  # LC3plus 2.5 ms frame: ~2.5 ms extra look-ahead/overlap (verify vs spec)
    adp = latency_ms(1.0, 0.0, 0.25)
    print(f"LC3plus 2.5 ms frames  ~{lc3:.1f} ms  (target 1.9-3.0)")
    print(f"ADPCM 1 ms frames      ~{adp:.1f} ms")
    assert lc3 > 3.0 and adp <= 3.0

    print("\n== Residual loss after diversity merge (independent losses) ==")
    for p1, p2, note in [(0.40, 0.10, "plan: 2.4 + 5 GHz"), (0.40, 0.40, "two 2.4 GHz channels, worst case"),
                         (0.10, 0.10, "two 2.4 GHz channels, picked clear")]:
        print(f"{note:<36} {p1:.0%} x {p2:.0%} = {p1 * p2:.1%}")

    print("\n== Battery (18650 3500 mAh, 3.6 V nominal, 90% converter) ==")
    wh = 3.5 * 3.6 * 0.9
    loads = {"nRF5340 + FEM, 40% TX duty": 0.12, "OPA1612 x2 ch @5V": 0.04,
             "PCM1840": 0.03, "LDO/bias/LEDs": 0.05}
    p_nrf = sum(loads.values())
    p_esp = p_nrf + 0.35  # ESP32-C5 5 GHz Wi-Fi TX, ~1 ms frames => near-continuous
    for name, p in [("nRF-only pack", p_nrf), ("+ ESP32-C5 5 GHz", p_esp), ("plan's 0.55 W", 0.55)]:
        print(f"{name:<20} {p:.2f} W -> {wh / p:5.1f} h")
    assert wh / 0.55 >= 16

    print("\n== Thermal (sealed ABS box 100x65x25 mm, h~10 W/m2K) ==")
    area = 2 * (0.100 * 0.065 + 0.100 * 0.025 + 0.065 * 0.025)
    for p in (p_nrf, 0.55, p_esp):
        print(f"{p:.2f} W -> dT {p / (10 * area):4.1f} K free air, ~{3 * p / (10 * area):4.1f} K in a costume pouch")


# ---- Audit 2 additions (Fable, 2026-10-31). Run: python3 audit.py ----
import random


def gap_carriers(wifi_width_mhz, carrier_mhz=2.0):
    """How many carriers fit between Wi-Fi 1/6/11 (centres 2412/2437/2462) in 2400-2483.5."""
    busy = [(c - wifi_width_mhz / 2, c + wifi_width_mhz / 2) for c in (2412, 2437, 2462)]
    edges = [2400.0] + [e for b in busy for e in b] + [2483.5]
    gaps = [(edges[i], edges[i + 1]) for i in range(0, len(edges), 2)]
    return sum(int((hi - lo) // carrier_mhz) for lo, hi in gaps), gaps


def airtime2(bits_per_sample, phy_bps, copies=2, hdr_b=6, frame_ms=1.0):
    """Airtime fraction of a 1 ms frame: audio payload + hdr (seq/status/codec state) + PHY overhead."""
    pay = round(48 * frame_ms * bits_per_sample / 8) + hdr_b
    us = ((pay + PKT_OVH_B) * 8 / phy_bps * 1e6 + RAMP_US + GUARD_US) * copies
    return us / (frame_ms * 1000)


def burst_loss(busy=0.40, mean_burst_frames=2.0, p_bad=0.9, p_good=0.001, frames=60000, seed=1):
    """Gilbert-Elliott per channel, independent across the two channels. Returns (residual, max_run, runs>1)."""
    rng = random.Random(seed)
    g2b = (1 / mean_burst_frames) * busy / (1 - busy)   # keeps time-in-bad = busy
    b2g = 1 / mean_burst_frames
    state = [False, False]
    lost = run = maxrun = long_runs = 0
    for _ in range(frames):
        both = True
        for i in range(2):
            state[i] = (rng.random() >= b2g) if state[i] else (rng.random() < g2b)
            both &= rng.random() < (p_bad if state[i] else p_good)
        if both:
            lost += 1; run += 1; maxrun = max(maxrun, run)
        else:
            long_runs += run > 1; run = 0
    return lost / frames, maxrun, long_runs


def bom_pack():
    """PK-12: pack BOM at qty 100 from hw/pack/out/bom.csv, written by hw/pack/pack.py from the SKiDL
    netlist + hw/pack/prices.py (every price carries its source). Excludes the 18650 cell (~$5)."""
    import csv, pathlib
    with open(pathlib.Path(__file__).resolve().parent / "hw/pack/out/bom.csv") as f:
        return [(r["refs"], r["value"], int(r["qty"]), float(r["ext_usd"])) for r in csv.DictReader(f)]


BOM_PACK_MAX_USD = 35.0  # SPEC PK-12 / REQUIREMENTS R12

if __name__ == "__main__":
    print("\n== Audit 2: channel plan ==")
    for w in (20, 22):
        n, gaps = gap_carriers(w)
        print(f"Wi-Fi width {w} MHz: {n:2d} x 2 MHz carriers fit in gaps {[(round(a), round(b)) for a, b in gaps]}  (need 16 for 8 packs x 2 copies)")
    assert gap_carriers(20)[0] < 16, "if this passes, the 'all in the gaps' claim is fine"

    print("\n== Audit 2: codec x PHY airtime (2 copies, 1 pack/channel pair, 1 ms frame) ==")
    print(f"{'codec':<34}{'2 Mbps (nRF5340)':>18}{'4 Mbps (nRF54L15)':>20}")
    for name, bps in [("ADPCM 6-bit", 6), ("ADPCM 8-bit", 8), ("block-float 8+3/16 (~8.2 b)", 8.1875),
                      ("block-float 10+3/16", 10.1875), ("PCM 12-bit", 12), ("PCM 16-bit", 16), ("PCM 24-bit", 24)]:
        a2, a4 = airtime2(bps, 2e6), airtime2(bps, 4e6)
        print(f"{name:<34}{a2:>13.0%} {'OK ' if a2 <= 0.9 else 'FAIL'}{a4:>15.0%} {'OK ' if a4 <= 0.9 else 'FAIL'}")

    print("\n== Audit 2: bursty loss (Gilbert-Elliott, 60 s, PLC hides single-frame drops) ==")
    for busy, mb, note in [(0.10, 2, "clear channels"), (0.40, 2, "worst case, short bursts"),
                           (0.40, 4, "worst case, 4 ms A-MPDU bursts")]:
        r, mx, lr = burst_loss(busy, mb)
        print(f"{note:<32} busy {busy:.0%}  residual {r:5.2%}  max run {mx:2d} frames  audible events/min {lr / 1:4.0f}")

    print("\n== Audit 2: pack BOM (ex. 18650 cell ~$5) ==")
    bom = bom_pack()
    tot = sum(r[3] for r in bom)
    for refs, val, qty, ext in bom:
        print(f"  {val[:30]:<30} x{qty:<3} {refs[:22]:<22} ${ext:5.2f}")
    print(f"  {'TOTAL (hw/pack/out/bom.csv)':<58} ${tot:5.2f}   PK-12 limit ${BOM_PACK_MAX_USD:.0f}")
    assert tot <= BOM_PACK_MAX_USD, f"PK-12 fails: pack BOM ${tot:.2f} > ${BOM_PACK_MAX_USD:.0f}"
    bt40 = next(r for r in bom if r[1] == "BT40NE")[3]
    dk = tot - bt40 + 16.76  # BT40NE at Digi-Key qty-100 cut tape (hw/pack/prices.py BT40NE_DIGIKEY_Q100)
    print(f"  BT40NE priced at ${bt40:.2f}: Fanstel direct, qty-100 break (fanstel.com/bt40f-nrf5340, 2026-10-31)")
    print(f"  margin to PK-12 ${BOM_PACK_MAX_USD - tot:.2f}; R12 target ~$30 -> {tot - 30:+.2f}")
    print(f"  info: with BT40NE from Digi-Key ($16.76 @100) the BOM is ${dk:.2f}"
          f" ({'over' if dk > BOM_PACK_MAX_USD else 'within'} PK-12). Excludes PCB assembly and conformal coating.")

    print("\n== Pack cell cutoff (ADR-0012): firmware shuts down below this cell voltage, under load ==")
    # +3V3 (TLV75533P from the cell) feeds the module and PCM1840 IOVDD, whose minimum is 3.0 V (SBAS989 6.3).
    i_3v3 = 0.140            # A: nRF21540 at +19 dBm (~115 mA) + nRF5340 + PCM1840 IOVDD, peak during TX
    r_ldo = 0.238 / 0.5      # ohm: TLV755P 3.3 V dropout max 238 mV at 500 mA, 125 C (in dropout: an Rdson)
    i_5v_in = 0.032 * 5.0 / (3.2 * 0.85)   # A from the cell into the boost: ~32 mA at 5 V (PCM1840 AVDD, OPA1656, bias)
    r_path = 0.023 + 0.10 + 0.03 + 0.05    # ohm: SF-1206F300 fuse, DMG2305UX Rds(on) at -2.5 V, JS102011SAQN contact, holder/traces
    r_top, r_bot, v_cell_max = 1e6, 1e6, 4.2   # hw/pack/pack.py R12 (BAT+ to VBAT_SENSE), R13 (to GND)
    ratio = r_bot / (r_top + r_bot)
    assert ratio * v_cell_max <= 3.3, "divider must keep P0.04/AIN0 within the 3.3 V rail (nRF5340 PS, SAADC: AIN0-AIN7 cannot exceed VDD)"
    # SAADC: 0.6 V internal ref, gain 1/4 -> 2.4 V full scale; 3.2 V cell reads 1.6 V, 4.2 V reads 2.1 V (both in range)
    assert ratio * 3.2 < 0.6 / 0.25 and ratio * v_cell_max < 0.6 / 0.25
    v_err = 0.08             # V: 1 % divider + nRF5340 SAADC gain error at 3.2 V
    cutoff = 3.0 + i_3v3 * r_ldo + (i_3v3 + i_5v_in) * r_path + v_err
    CELL_CUTOFF_V = round(cutoff + 0.049, 1)   # rounded up to 0.1 V
    print(f"  IOVDD min 3.00 + LDO {i_3v3 * r_ldo * 1e3:.0f} mV + path {(i_3v3 + i_5v_in) * r_path * 1e3:.0f} mV"
          f" + ADC error {v_err * 1e3:.0f} mV = {cutoff:.2f} V -> cutoff {CELL_CUTOFF_V:.1f} V (red LED below 3.4 V, PK-8)")
    assert CELL_CUTOFF_V < 3.4, "cutoff must sit below the red battery LED threshold"
    # Stopping at 3.2 V under load leaves ~10 % of a protected cell unused; runtime at 0.55 W with 90 % of 3.5 Ah:
    print(f"  runtime with 90 % of the cell usable: {0.9 * wh / 0.55:.1f} h (PK-7 >= 16 h)")
    assert 0.9 * wh / 0.55 >= 16


# ---- Audit 3: region (UK vs US), 2026-10-31, issue #80, ADR-0015. Run: python3 audit.py ----
# Sources (clause numbers quoted in ADR-0015):
#   ETSI EN 300 328 V2.2.2 (2019-07), UK designated standard under the Radio Equipment Regulations 2017:
#     4.3.2.2 EIRP <= 20 dBm; 4.3.2.3 PSD <= 10 dBm/MHz EIRP; 4.3.2.4 (non-adaptive, >= 10 dBm) Tx-sequence <= 10 ms,
#     Tx-gap >= that sequence and >= 3.5 ms; 4.3.2.5 MU = Pout/100 mW x DC <= 10 %; 4.3.2.4/5/6 do not apply below
#     10 dBm EIRP; 4.3.2.6.2/.3 DAA/LBT, threshold TL = -70 dBm/MHz + 10 log10(100 mW / Pout).
#   Ofcom IR 2030 v1.17 (Oct 2026): IR2030/7/1 WBDTS 2400-2483.5 MHz 100 mW EIRP and 10 mW/MHz (non-FHSS);
#     IR2030/1/22 non-specific SRD 10 mW EIRP; IR2030/26/5 wireless audio 10 mW EIRP (EN 300 422).
#   FCC 47 CFR 15.247(b)(3),(b)(4): 1 W conducted, 6 dBi before back-off.
import math
import pathlib

SENS_2M_DBM = -93.0      # nRF5340 PS v1.x: BLE 2M -95 dBm for <= 37 B; our 53-92 B packets: 2 dB back-off (est.)
WHIP_DBI = 2.0           # ADR-0007: ~2 dBi whip, the declared antenna gain for EIRP
NRF5340_MAX_DBM = 3.0    # nRF5340 PS: max TX output power, no FEM
CI_REQ_DB = 10.0         # BLE 2M co-channel C/I needed (sim/loss/RESULTS.md s3)
UK_WIFI_13 = 2472        # UK Wi-Fi channel 13 centre (IEEE 802.11 2.4 GHz channels 1-13 allowed under IR2030/7/1)

REGIONS = {  # max pack EIRP the design may declare, the Wi-Fi channels a venue may run, and the rule that sets it
    "US": {"eirp_dbm": 20.0, "wifi": (2412, 2437, 2462),
           "rule": "FCC 15.247(b)(3): 30 dBm conducted; BT40NE 19.1 dBm + 2 dBi whip = 21.1; twin uses 20"},
    "UK": {"eirp_dbm": 9.0, "wifi": (2412, 2437, 2462),   # + Wi-Fi 13 where a venue uses it (wifi13=True below)
           "rule": "EN 300 328 4.3.2.4/.5/.6 exempt below 10 dBm EIRP; declared 9 dBm (1 dB production/test margin)"},
}


def pkt_air_us(time_div, phy_bps=PHY_BPS):
    """AIR-3 packet on air (no ramp): 42 B payload without time diversity, 81 B with, + 11 B overhead."""
    pay = 1 + 2 + 3 + 36 + (39 if time_div else 0)
    return (pay + PKT_OVH_B) * 8 / phy_bps * 1e6


def duty_cycle(time_div):
    """EN 300 328 4.3.2.4.2: total transmitter-on time / observation period. Two copies per 1 ms frame, per pack."""
    return 2 * pkt_air_us(time_div) / 1000


def medium_utilisation(eirp_dbm, dc):
    """EN 300 328 4.3.2.5.2: MU = (Pout / 100 mW) x DC."""
    return 10 ** (eirp_dbm / 10) / 100 * dc


def max_tx_gap_us(time_div, t_gap=100):
    """Longest silence in one 1 ms frame: frame - TX ramp - 2 copies - retune gap (the RX slot is silent)."""
    return 1000 - RAMP_US - 2 * pkt_air_us(time_div) - t_gap


def gfsk_spectrum(rs=2e6, h=0.5, bt=0.5, osr=32, nsym=100_000, seed=1):
    """BLE 2M GFSK (h 0.5, BT 0.5) complex-baseband PSD, normalised to sum 1. Returns (freq Hz, p)."""
    import numpy as np
    rng = np.random.default_rng(seed)
    fs, t = rs * osr, np.arange(-2 * osr, 2 * osr + 1) / osr
    g = np.exp(-t ** 2 / (2 * (math.sqrt(math.log(2)) / (2 * math.pi * bt)) ** 2))
    f = np.convolve(np.repeat(rng.choice([-1.0, 1.0], nsym), osr), g / g.sum(), "same") * h * rs / 2
    x = np.exp(2j * np.pi * np.cumsum(f) / fs)
    n = 8192
    p = (np.abs(np.fft.fft(x[: len(x) // n * n].reshape(-1, n) * np.hanning(n), axis=1)) ** 2).mean(0)
    p = np.fft.fftshift(p)
    return np.fft.fftshift(np.fft.fftfreq(n, 1 / fs)), p / p.sum()


def psd_stats():
    """(worst 1 MHz share of the power, 99 % occupied bandwidth in MHz): EN 300 328 5.4.3 step 5-7 / 4.3.2.7."""
    import numpy as np
    fr, p = gfsk_spectrum()
    w = int(round(1e6 / (fr[1] - fr[0])))
    cs = np.cumsum(p)
    obw = fr[np.searchsorted(cs, 0.995)] - fr[np.searchsorted(cs, 0.005)]
    return float(np.convolve(p, np.ones(w), "valid").max()), obw / 1e6


def wifi_mask_dbr(off_mhz):
    """802.11 OFDM 20 MHz transmit mask (0 dBr to 9 MHz, -20 @ 11, -28 @ 20, -40 @ 30), linear in dB between."""
    pts = [(0, 0), (9, 0), (11, -20), (20, -28), (30, -40)]
    o = abs(off_mhz)
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        if o <= x1:
            return y0 + (y1 - y0) * (o - x0) / (x1 - x0)
    return -40.0


def carrier_ci_db(f_mhz, region, wifi_dbm=20.0, d_pack=10.0, d_wifi=2.0, pack_eirp=None, wifi13=False):
    """C/I at the receiver for one carrier vs the worst Wi-Fi channel of the region (sim/loss/RESULTS.md s3, ADR-0003
    geometry: free space, same rx antenna, no fading, no body loss). A 2 MHz slice of 20 MHz Wi-Fi is -10 dB."""
    p = REGIONS[region]["eirp_dbm"] if pack_eirp is None else pack_eirp
    c = p - 20 * math.log10(d_pack)
    chans = REGIONS[region]["wifi"] + ((UK_WIFI_13,) if wifi13 else ())
    i = max(wifi_dbm - 20 * math.log10(d_wifi) - 10 + wifi_mask_dbr(f_mhz - w) for w in chans)
    return c - i


def link_range_m(eirp_dbm, n, sys_nf_db, body_db=10.0, g_rx=6.0, fade_db=10.0, snr_db=10.0):
    """Max pack-receiver distance keeping fade_db of margin; path loss 40.2 + 10 n log10(d) dB at 2.44 GHz.
    Sensitivity = kTB(2 MHz) + system NF + SNR (10 dB reproduces the -93 dBm nRF5340 figure with NF ~7)."""
    sens = -174 + 10 * math.log10(2e6) + sys_nf_db + snr_db
    return 10 ** ((eirp_dbm - body_db + g_rx - sens - fade_db - 40.2) / (10 * n))


def cascade_nf_db(stages):
    """Friis: stages = [(gain_db, nf_db), ...] from the antenna connector inwards."""
    f, g = 0.0, 1.0
    for i, (gdb, nfdb) in enumerate(stages):
        f = 10 ** (nfdb / 10) if i == 0 else f + (10 ** (nfdb / 10) - 1) / g
        g *= 10 ** (gdb / 10)
    return 10 * math.log10(f)


def _traces():
    import importlib.util
    spec = importlib.util.spec_from_file_location("traces", pathlib.Path(__file__).resolve().parent / "sim/loss/traces.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


if __name__ == "__main__":
    print("\n== Audit 3: region rules (EN 300 328 V2.2.2 + IR 2030 vs FCC 15.247), ADR-0015 ==")
    for td in (False, True):
        dc = duty_cycle(td)
        p10 = 10 * math.log10(0.10 / dc * 100)
        print(f"  TD {'on ' if td else 'off'}: {pkt_air_us(td):.0f} us/copy, DC {dc:.1%}/pack; MU at 20 dBm"
              f" {medium_utilisation(20, dc):.1%} (limit 10 %, 4.3.2.5.3); MU 10 % at {p10:.1f} dBm;"
              f" longest Tx-gap {max_tx_gap_us(td):.0f} us vs >= 3500 us (4.3.2.4.3)")
    assert abs(pkt_air_us(False) - 212) < 1 and abs(duty_cycle(False) - 0.424) < 0.001
    for td in (False, True):  # narrower PHY option (#76): 1 Mbit halves the bandwidth, doubles the air time
        fr1 = RAMP_US + 2 * pkt_air_us(td, 1e6) + 100
        print(f"  1 Mbit PHY, TD {'on ' if td else 'off'}: ramp + 2 copies + T_GAP = {fr1:.0f} us of a 1000 us frame"
              f" ({'no room for the 300 us RX slot' if fr1 > 700 else 'fits'}{', does not fit' if fr1 > 1000 else ''});"
              f" latency +{2 * (pkt_air_us(td, 1e6) - pkt_air_us(td)) / 1e3:.2f} ms")
    assert max(max_tx_gap_us(True), max_tx_gap_us(False)) < 3500, "non-adaptive >= 10 dBm: impossible for a 1 ms stream"
    frac, obw = psd_stats()
    psd_cap = 10 - 10 * math.log10(frac)
    print(f"  BLE 2M GFSK: worst 1 MHz holds {frac:.0%} of the power, 99 % OBW {obw:.2f} MHz ->"
          f" PSD 10 dBm/MHz (4.3.2.3.3, IR2030/7/1) caps EIRP at {psd_cap:.1f} dBm, adaptive or not")
    assert 11 < psd_cap < 14, "the PSD cap, not the 20 dBm EIRP limit, binds every UK option"
    tl = -70 + 10 * math.log10(100 / 10 ** (psd_cap / 10))
    wifi_10m = 20 - 13 - 40.2 - 20  # 20 dBm over 20 MHz = 7 dBm/MHz, free space 10 m
    print(f"  adaptive at {psd_cap:.1f} dBm: detect threshold {tl:.1f} dBm/MHz (4.3.2.6.3.2.2 step 5); audience Wi-Fi"
          f" at 10 m from the pack {wifi_10m:.1f} dBm/MHz -> in-band copies deferred whenever Wi-Fi is on air")
    for r, v in REGIONS.items():
        print(f"  {r}: pack EIRP {v['eirp_dbm']:.0f} dBm = conducted {v['eirp_dbm'] - WHIP_DBI:.0f} dBm + {WHIP_DBI:.0f} dBi ({v['rule']})")
    uk_cond = REGIONS["UK"]["eirp_dbm"] - WHIP_DBI
    print(f"  FEM: UK needs {uk_cond:.0f} dBm conducted, nRF5340 alone gives {NRF5340_MAX_DBM:.0f} dBm -> the PA adds"
          f" {uk_cond - NRF5340_MAX_DBM:.0f} dB (nRF21540 at low gain: ~38 mA at +10 dBm vs 110 mA at +20, Nordic)")
    assert uk_cond > NRF5340_MAX_DBM, "if this fails the PA is useless in the UK: drop to BT40E"

    print("\n== Audit 3: link budget (body 10 dB, rx antenna 6 dBi, fade margin 10 dB: estimates) ==")
    chain = [(-6, 6), (20, 2), (-10.5, 10.5)]   # RK-2 coax 6 dB, rack LNA 20 dB/NF 2 (est.), 1:8 splitter 10.5 dB (est.)
    nf_lna = cascade_nf_db(chain + [(13, 2.7), (0, 7)])   # module nRF21540 LNA 13 dB/NF 2.7 (Nordic), nRF5340 NF ~7 (est.)
    nf_none = cascade_nf_db(chain + [(0, 7)])
    print(f"  receiver NF at the antenna port: {nf_lna:.1f} dB with the module LNA, {nf_none:.1f} dB without")
    for r, v in REGIONS.items():
        rr = [link_range_m(v["eirp_dbm"], n, nf) for n in (2.0, 3.0) for nf in (nf_lna, nf_none)]
        print(f"  {r}: range free space {rr[0]:4.0f} m (no module LNA {rr[1]:4.0f}),"
              f" indoor n=3 {rr[2]:3.0f} m (no module LNA {rr[3]:3.0f})")
    assert link_range_m(REGIONS["UK"]["eirp_dbm"], 3.0, nf_none) > 20, "UK closes a 20 m stage-to-wing link with margin"

    print("\n== Audit 3: R1 gap-carrier C/I (ADR-0003: pack 10 m, Wi-Fi at 2 m from the rx antenna; need >= 10 dB) ==")
    import yaml
    plan = yaml.safe_load((pathlib.Path(__file__).resolve().parent / "host/channel_plan.yaml").read_text())["packs"]
    gaps = sorted(f for ab in plan.values() for f in (ab["fA"], ab["fB"]) if wifi_mask_dbr(min(
        abs(f - w) for w in REGIONS["US"]["wifi"])) <= -20)
    for r, w13 in (("US", False), ("UK", False), ("UK", True)):
        for w in (15, 20):
            ci = [carrier_ci_db(f, r, w, wifi13=w13) for f in gaps]
            print(f"  {r + (' +ch13' if w13 else ''):<8} Wi-Fi {w} dBm: " + " ".join(f"{f}:{c:+.0f}" for f, c in zip(gaps, ci))
                  + f"  -> {sum(c >= CI_REQ_DB for c in ci)}/{len(gaps)} hold")
    assert len(gaps) == 7 and all(carrier_ci_db(f, "US", 20) >= CI_REQ_DB for f in gaps)
    assert sum(carrier_ci_db(f, "UK", 20) >= CI_REQ_DB for f in gaps) <= 1, "UK worst case: gap carriers fail"
    m = carrier_ci_db(2423, "UK", 20) - CI_REQ_DB
    print(f"  UK worst case margin {m:+.1f} dB: holds with Wi-Fi >= {2 * 10 ** (-m / 20):.1f} m from the rx antenna"
          f" (Q3: 2 m), or pack <= {10 * 10 ** (m / 20):.1f} m (Q3: 10 m); at 15 dBm phones"
          f" {carrier_ci_db(2423, 'UK', 15) - CI_REQ_DB:+.1f} dB")
    tr = _traces()
    for busy in (0.10, 0.40):
        la, lb = tr.trace(0.001, busy)   # gap copy clean (RESULTS s1, 0.1 %)
        ok = tr.metrics(tr.frame_lost(la, lb, True))
        la, lb = tr.trace(busy)          # gap copy lost with its neighbour's bursts = both copies in-band (RESULTS s4)
        bad = tr.metrics(tr.frame_lost(la, lb, True))
        print(f"  TD on, Wi-Fi busy {busy:.0%}: gap holds {ok[0]:.3f} %/{ok[1]}/{ok[2]:.0f} ev/h;"
              f" gap fails {bad[0]:.3f} %/{bad[1]}/{bad[2]:.0f} ev/h  (ADR-0003: <= 0.1 %/2/1)")
    under13 = [f for f in gaps if abs(f - UK_WIFI_13) <= 9]
    print(f"  plan gap carriers under UK Wi-Fi 13 (2463-2481 occupied): {under13} -> packs"
          f" {[k for k, ab in plan.items() if ab['fB'] in under13 or ab['fA'] in under13]} lose their gap copy if 13 is used")


# ---- Audit 4: R1 under UK rules, receive-side isolation (#89, docs/analysis/r1-uk-isolation.md). ----
# EN 300 328 and IR 2030 limit only what the pack radiates. Rack antenna gain, its front-to-back ratio and the
# receiver's filter are not regulated. The interference numbers use the BabbleSim modem tables
# (sim/loss/bsim_modem.py), so they predict the twin; bsim (c) via tests/bsim/scenarios/run.py
# --rx-gain/--wifi-gain/--near-att checks them. Antenna, coax and reflection figures are estimates (est.).
PATCH_DBI = 8.0          # est.: 2.4 GHz flat-panel/patch, 8-9 dBi, ~65-75 deg beamwidth (catalogue class)
FTB_DB = 15.0            # est.: front-to-back design value; catalogue patches state 15-25 dB
SIDE_DB = 10.0           # est.: rejection 90 deg off-axis for a ~70 deg beam (vs boresight)
REFL_PATH_M, REFL_LOSS_DB = 15.0, 6.0   # est.: Wi-Fi via one stage-wall bounce into the front lobe
COAX_DB_M = {"LMR-400": 0.22, "LMR-240": 0.42, "RG-58": 1.0}   # est., 2.4 GHz catalogue attenuation
CONN_DB = 0.5            # est.: two N/BNC connectors
TD_BITS = (81 + PKT_OVH_B) * 8   # TD-length copy, the one (c) asserts on
MARGIN_DB = 3.0          # design margin over the twin's threshold (real phones, multipath)
R1_PLAN = "docs/analysis/r1-uk-plan.yaml"


def _bsim_modem():
    import importlib.util
    spec = importlib.util.spec_from_file_location("bsim_modem", pathlib.Path(__file__).resolve().parent / "sim/loss/bsim_modem.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def rejection_db(direction, ftb=FTB_DB):
    """Wi-Fi rejection of the rack patch relative to its on-axis gain, by where the Wi-Fi sits. One reflection off
    the stage arrives on-axis and caps it: direct at 2 m vs reflected over REFL_PATH_M with REFL_LOSS_DB."""
    direct = {"behind": ftb, "beside": SIDE_DB, "front": 0.0}[direction]
    refl = 20 * math.log10(REFL_PATH_M / 2.0) + REFL_LOSS_DB
    return -10 * math.log10(10 ** (-direct / 10) + 10 ** (-refl / 10))


def wifi_min_dist_m(need_db, direction, ftb=FTB_DB):
    """Closest a Wi-Fi device may be to a rack antenna (Q3: 20 dBm, pack at 10 m) for need_db + MARGIN_DB."""
    return 2.0 * 10 ** (max(0.0, need_db + MARGIN_DB - rejection_db(direction, ftb)) / 20)


if __name__ == "__main__":
    bm = _bsim_modem()
    print("\n== Audit 4: R1 under UK rules, receive-side isolation (#89) ==")
    wanted = REGIONS["UK"]["eirp_dbm"] - (40.2 + 20)          # 9 dBm pack at 10 m, isotropic rack antenna
    wifi = 20.0 - (40.2 + 20 * math.log10(2.0))               # Q3 Wi-Fi 20 dBm at 2 m
    W = REGIONS["UK"]["wifi"]
    r1plan = yaml.safe_load((pathlib.Path(__file__).resolve().parent / R1_PLAN).read_text())["packs"]
    gapc = {k: next(f for f in (ab["fA"], ab["fB"]) if min(abs(f - w) for w in W) >= 11) for k, ab in r1plan.items()}
    need = {f: bm.isolation_needed_db(f, W, wanted, wifi, TD_BITS) for f in sorted(set(gapc.values()) | {2402})}
    print(f"  twin (bsim modem): pack {wanted:.1f} dBm, each Wi-Fi {wifi:.1f} dBm at the rx antenna. Isolation needed"
          f" for a TD-length copy to have PER <= 0.1 % while Wi-Fi is on air:")
    print("   " + "  ".join(f"{f}: {need[f]:.1f}" for f in need) + " dB  (2402: lower band edge)")
    worst = max(need[f] for f in gapc.values())
    assert 12 <= worst <= 13.5, "11 MHz gap carriers need ~12.7 dB (ADR-0015: ~11 dB)"
    assert need[2402] > worst + 4, "the 2402 band-edge carrier (10 MHz from Wi-Fi 1) is worse than any gap carrier"

    print(f"  lever 1, directional rack antennas (patch est. {PATCH_DBI:.0f} dBi, FtB {FTB_DB:.0f} dB;"
          f" reflection caps rejection at {rejection_db('behind', 99):.1f} dB):")
    for d in ("behind", "beside", "front"):
        rj = rejection_db(d)
        ok = sum(rj >= need[f] - 1e-9 for f in gapc.values())
        print(f"    Wi-Fi {d:<6} at 2 m: rejection {rj:4.1f} dB -> {ok}/8 gap carriers hold;"
              f" with {MARGIN_DB:.0f} dB margin Wi-Fi must be >= {wifi_min_dist_m(worst, d):4.1f} m from the antenna")
    assert rejection_db("behind") >= worst and rejection_db("beside") < worst
    assert wifi_min_dist_m(worst, "behind") <= 3.0 and wifi_min_dist_m(worst, "beside") <= 4.0  # install rule
    assert 10 <= wifi_min_dist_m(worst, "front") <= 15, "AP in the antenna's view: keep it >= ~12 m away"
    for name, dbm in COAX_DB_M.items():
        print(f"    coax {name}: <= {(6 - CONN_DB) / dbm:4.1f} m inside the RK-2 6 dB budget")
    nf = cascade_nf_db([(-6, 6), (20, 2), (-10.5, 10.5), (0, 7)])   # Audit 3 chain, BT40E modules (no module LNA)
    rng = link_range_m(REGIONS["UK"]["eirp_dbm"], 3.0, nf, g_rx=PATCH_DBI)
    print(f"    link: system NF {nf:.1f} dB, indoor n=3 range {rng:.0f} m with the patch (Audit 3 used 6 dBi)."
          f" Coax, LNA and splitter scale pack and Wi-Fi alike, so C/I is unchanged")
    assert rng > 20
    lna_in = wifi + PATCH_DBI - CONN_DB      # worst case: Wi-Fi in front at 2 m, before any coax loss
    im3 = 3 * lna_in - 2 * 0.0 - 10 * math.log10(60 / 2)   # IIP3 0 dBm; 1/6/11 products spread over ~60 MHz
    print(f"    rack LNA input, Wi-Fi in front at 2 m: {lna_in:.1f} dBm per channel -> LNA input P1dB >= -10 dBm;"
          f" IM3 at IIP3 0 dBm {im3:.0f} dBm per 2 MHz vs pack {wanted + PATCH_DBI:.0f} dBm")
    assert im3 < wanted + PATCH_DBI - 20, "rack LNA spec for #32: IIP3 >= 0 dBm"

    print("  lever 2, receive selectivity (nRF5340 RADIO: the channel filter is fixed per MODE, so only 1M vs 2M):")
    for off in (10, 11, 12, 13):
        print(f"    Wi-Fi centre {off} MHz away: 2M filter passes {bm.wifi_through_filter_db(off):6.1f} dB,"
              f" 1M {bm.wifi_through_filter_db(off, '1M'):6.1f} dB")
    g1 = need[2423] - bm.isolation_needed_db(2423, W, wanted, wifi, TD_BITS, phy="1M")
    td_1m = RAMP_US + 2 * pkt_air_us(True, 1e6) + 100
    hyb = RAMP_US + pkt_air_us(True) + 100 + pkt_air_us(False, 1e6)
    print(f"    1M on the gap copy gains {g1:.1f} dB at 11 MHz. TD at 1M: {td_1m:.0f} us/frame (does not fit 1000);"
          f" hybrid (copy A 2M with td_audio, copy B 1M v1): {hyb:.0f} us, copy B ends"
          f" {pkt_air_us(False, 1e6) - pkt_air_us(True):+.0f} us later (SYS-2)")
    assert g1 < worst and td_1m > 1000 and hyb < 1000

    psd_cap = 10 - 10 * math.log10(psd_stats()[0])
    gain3 = psd_cap - REGIONS["UK"]["eirp_dbm"]
    print(f"  lever 3, adaptive (LBT/DAA) at the PSD cap {psd_cap:.1f} dBm: +{gain3:.1f} dB, {worst - gain3:.1f} dB short"
          f" of what the 11 MHz carriers need")
    assert gain3 < worst / 4

    print(f"  lever 4, an 8th gap carrier ({R1_PLAN}: pack 1 2414/2482):")
    fr, p = gfsk_spectrum()
    above = lambda c, k: float(p[(fr >= (2483.5 - c + k) * 1e6) & (fr < (2484.5 - c + k) * 1e6)].sum())
    oob = [REGIONS["UK"]["eirp_dbm"] + 10 * math.log10(above(2482, k)) for k in range(2)]
    us_rb = REGIONS["US"]["eirp_dbm"] + 10 * math.log10(float(p[fr >= 1.5e6].sum()))
    print(f"    2482 skirt above 2483.5: {oob[0]:.1f} / {oob[1]:.1f} dBm/MHz (ideal GFSK, 9 dBm) vs EN 300 328 4.3.2.8"
          f" -10 / -20. US at 20 dBm puts {us_rb:.0f} dBm into the 2483.5-2500 restricted band (15.205, ~-41): UK only")
    assert oob[0] <= -20 and oob[1] <= -30 and us_rb > -41
    fs = sorted(f for ab in r1plan.values() for f in (ab["fA"], ab["fB"]))
    assert len(r1plan) == 8 and len(set(gapc.values())) == 8, "all 8 packs have their own gap carrier"
    assert min(b - a for a, b in zip(fs, fs[1:])) >= 3 and all(ab["fB"] >= ab["fA"] + 40 for ab in r1plan.values())
    adj3 = bm.through_filter_db(3, "2M", bm.TX2M)
    sinr_req = next(x / 10 for x in range(400) if bm.per(x / 10, TD_BITS) <= 1e-3)
    hot = -adj3 - sinr_req
    d_near = 10 * 10 ** (-hot / 20)
    print(f"    near-far: a pack 3 MHz away passes {adj3:.1f} dB into the filter and a copy needs SINR {sinr_req:.1f} dB,"
          f" so a gap copy holds while its neighbour is <= {hot:.1f} dB hotter: for packs at 10 m, no pack closer"
          f" than {d_near:.1f} m to an antenna")
    assert 3 <= d_near <= 4.5


# ---- Receiver sub-board BOM (#32, ADR-0014). Written by hw/rx/rx.py from the SKiDL netlist + hw/rx/prices.py ----
def bom_rx():
    """Per-receiver sub-board BOM at qty 100 (USD and GBP, UK distributor per line) from hw/rx/out/bom.csv."""
    import csv, pathlib
    with open(pathlib.Path(__file__).resolve().parent / "hw/rx/out/bom.csv") as f:
        return list(csv.DictReader(f))


if __name__ == "__main__":
    print("\n== Receiver sub-board BOM (qty 100; GBP converted, ex VAT, not a UK quote) ==")
    rx = bom_rx()
    usd, gbp = sum(float(r["ext_usd"]) for r in rx), sum(float(r["ext_gbp"]) for r in rx)
    for r in rx:
        print(f"  {r['value'][:30]:<30} x{r['qty']:<3} {r['refs'][:22]:<22} ${float(r['ext_usd']):5.2f}"
              f"  GBP {float(r['ext_gbp']):5.2f}  {r['uk_distributor']}")
    print(f"  {'TOTAL per sub-board (hw/rx/out/bom.csv)':<58} ${usd:5.2f}  GBP {gbp:5.2f}")
    print(f"  x8 sub-boards ${8 * usd:.0f} (GBP {8 * gbp:.0f}) before main board, splitters, CM4, panel;"
          f" no per-receiver cap in SPEC/AUDIT, so none asserted (QUESTIONS.md Q14 guessed ~$150-250 for the rack)")
    assert all(r["uk_distributor"] for r in rx), "every rx BOM line needs a UK-reachable distributor"


# ---- Audit 6: rack RF chain and backplane BOM (#33, ADR-0018). hw/rack/backplane.py, hw/rack/wilkinson.py ----
# Antenna connector -> coax -> BNC/ESD/bias-T/DC block -> QPL9057 LNA -> QPQ1907 BAW filter -> 1:8 Wilkinson ->
# u.FL cable -> sub-board (DC block, PE4259, u.FL jumper) -> module (nRF21540 LNA or bypass) -> nRF5340.
# QPL9057 (Qorvo datasheet Rev. F, 2020-09-20): EVB typical at 1800 / 2600 MHz, VDD 5 V, 50 mA: gain 21.0 / 22.7 dB,
#   NF 0.50 / 0.47 dB (input trace de-embedded), OP1dB 17.1 / 17.1 dBm, OIP3 33.8 / 37.8 dBm; spec table (3.5 GHz)
#   min/max: gain >= 21.5, NF <= 0.90, OP1dB >= 14.5, OIP3 >= 29. Abs max RF input +27 dBm CW. ESD HBM class 1B.
#   The worst-case (min/max) figures are used for every assert below; the typicals are printed.
# QPQ1907 (Qorvo BAW, DigiKey UK page): passband 2402.5-2481.5 MHz, IL 1.3 dB typ / 2.2 dB max. Its stop-band
#   rejection at 2390 / 2500 MHz was not read (datasheet unreachable): no rejection is credited here.
# Levels: Audit 4 geometry (Wi-Fi 20 dBm at 2 m in front of the patch, worst) and the ADR-0016 install rule
#   (packs >= 4 m from an antenna); the near pack is counted at the US 20 dBm EIRP (same hardware, worst region).
LNA = {"part": "Qorvo QPL9057", "f_mhz": (1800, 2600), "gain": (21.0, 22.7), "nf": (0.50, 0.47),
       "op1db": (17.1, 17.1), "oip3": (33.8, 37.8), "nf_max": 0.90, "op1db_min": 14.5, "oip3_min": 29.0,
       "pin_abs_max_dbm": 27.0}
F_RX_MHZ = 2441.75
FRONT_END_DB = 0.4       # est.: BNC 0.1, ESD103 (0.09 pF) + ESD101 (0.1 pF) 0.05, bias-T choke shunt 0.05, DC block
                         #   0.05, 10 mm of 50 ohm FR-4 microstrip 0.15 (hw/rack/wilkinson.py line loss)
FILTER_DB = 2.2          # QPQ1907 max insertion loss (DigiKey UK page)
WILK_LAYOUT_DB = 0.5     # est.: T-junctions, bends, resistor pads (not in the hw/rack/wilkinson.py model; #34)
UFL_CABLE_DB = 1.0       # est.: 200 mm 1.13 mm coax ~3.5 dB/m + two mated u.FL pairs at 0.07 dB
SUBBOARD_DB = 0.9        # ADR-0014: PE4259 0.5 dB, u.FL jumper ~0.3 dB, three 10 pF blocks ~0.1 dB
MODULE_LNA = (13.0, 2.7) # nRF21540 RX gain / NF (Nordic PS), as Audit 3
MODULE_BYPASS_DB = 1.0   # est.: nRF21540 in bypass
NRF5340_NF = 7.0         # est., as Audit 3 (reproduces the -93 dBm sensitivity with SNR 10 dB)
NRF5340_PMAX_DBM = 0.0   # nRF5340 PS: maximum received signal strength at < 0.1 % PER
COAX_ADR16_DB, COAX_BUDGET_DB = 4.2, 6.0   # ADR-0016 (PR #93): CA3N050 15.2 m + BNC jumper; RK-2 budget
AUDIT4_SYS_NF_DB = cascade_nf_db([(-6, 6), (20, 2), (-10.5, 10.5), (0, 7)])   # what Audit 4's link and R1 used
LTE_UE_DBM = 23.0        # 3GPP power class 3 UE (LTE Band 40, 2300-2400 MHz, used in the UK)


def lna_at(f_mhz=F_RX_MHZ):
    """QPL9057 EVB typicals interpolated to f, plus the input-referred worst-case IP1dB / IIP3 used for asserts."""
    f0, f1 = LNA["f_mhz"]
    lin = lambda k: LNA[k][0] + (LNA[k][1] - LNA[k][0]) * (f_mhz - f0) / (f1 - f0)
    g = lin("gain")
    return {"gain": g, "nf": lin("nf"), "iip3": lin("oip3") - g, "ip1db": lin("op1db") - g + 1,
            "iip3_min": LNA["oip3_min"] - g, "ip1db_min": LNA["op1db_min"] - g + 1, "nf_max": LNA["nf_max"]}


def wilkinson_db():
    """Modelled 1:8 worst-case insertion loss over the band (hw/rack/wilkinson.py) + the layout allowance."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("wk", pathlib.Path(__file__).resolve().parent / "hw/rack/wilkinson.py")
    wk = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(wk)
    return wk.summary(5)["il_db"] + WILK_LAYOUT_DB


def rack_chain(coax_db, module_lna=False, worst=True, splitter_db=None):
    """[(gain dB, NF dB), ...] from the antenna connector inwards. Passive stages: NF = loss."""
    splitter_db = wilkinson_db() if splitter_db is None else splitter_db
    lna = lna_at()
    lossy = lambda d: (-d, d)
    ch = [lossy(coax_db), lossy(FRONT_END_DB), (lna["gain"], lna["nf_max"] if worst else lna["nf"]),
          lossy(FILTER_DB), lossy(splitter_db), lossy(UFL_CABLE_DB), lossy(SUBBOARD_DB)]
    ch += [MODULE_LNA] if module_lna else [lossy(MODULE_BYPASS_DB)]
    return ch + [(0.0, NRF5340_NF)]


def fspl_db(d_m, f_mhz=F_RX_MHZ):
    return 20 * math.log10(d_m) + 20 * math.log10(f_mhz) - 27.55


def dbm_sum(*p):
    return 10 * math.log10(sum(10 ** (x / 10) for x in p))


def r1_noise_cost_db(nf_sys):
    """ADR-0016 holds R1 with MARGIN_DB of C/I margin. Receiver noise adds to the interference: dB of that margin
    used up at the Q3 geometry (UK pack 10 m, body 10 dB, fade 10 dB, patch antenna)."""
    c = REGIONS["UK"]["eirp_dbm"] - 10.0 - 10.0 + PATCH_DBI - (40.2 + 20)
    i_lim = c - CI_REQ_DB - MARGIN_DB
    n = -174 + 10 * math.log10(2e6) + nf_sys
    return 10 * math.log10(1 + 10 ** ((n - i_lim) / 10)), c, n


def bom_rack():
    """Rack main-board BOM (GBP, one rack) from hw/rack/out/bom.csv, written by hw/rack/backplane.py."""
    import csv
    with open(pathlib.Path(__file__).resolve().parent / "hw/rack/out/bom.csv") as f:
        return list(csv.DictReader(f))


if __name__ == "__main__":
    print("\n== Audit 6: rack RF chain (#33, ADR-0018): antenna -> coax -> LNA -> filter -> 1:8 Wilkinson -> sub-board ==")
    lna = lna_at()
    print(f"  {LNA['part']} at {F_RX_MHZ:.0f} MHz: gain {lna['gain']:.1f} dB, NF {lna['nf']:.2f} dB typ"
          f" ({lna['nf_max']:.2f} max), IIP3 {lna['iip3']:+.1f} dBm typ ({lna['iip3_min']:+.1f} worst),"
          f" input P1dB {lna['ip1db']:+.1f} dBm typ ({lna['ip1db_min']:+.1f} worst)")
    assert lna["nf_max"] <= 2.0, "RK-2: LNA NF <= 2 dB"
    assert lna["ip1db_min"] >= -10 and lna["iip3_min"] >= 0, "RK-2: input P1dB >= -10 dBm, IIP3 >= 0 dBm"
    wil = wilkinson_db()
    print(f"  1:8 Wilkinson (hw/rack/wilkinson.py, JLC04161H-7628 er 4.4 tan(d) 0.02) {wil - WILK_LAYOUT_DB:.2f} dB"
          f" + {WILK_LAYOUT_DB} dB layout allowance; Audit 3/4 assumed 10.5 dB")
    for name, coax in (("ADR-0016 coax 4.2 dB", COAX_ADR16_DB), ("RK-2 budget 6.0 dB", COAX_BUDGET_DB)):
        nfs = [cascade_nf_db(rack_chain(coax, m, w, wil)) for m in (False, True) for w in (True, False)]
        print(f"  system NF at the antenna connector, {name}: {nfs[0]:.2f} dB worst / {nfs[1]:.2f} typ (module LNA"
              f" bypassed), {nfs[2]:.2f} / {nfs[3]:.2f} (module LNA on)")
    # 16 dB of loss after the rack LNA (filter, splitter, cable, sub-board) is more than its 22 dB gain can bury:
    # with the module's nRF21540 LNA bypassed the 6 dB-coax case misses Audit 4's NF. So the module LNA stays ON
    # (BT40NE kept, ADR-0018) and firmware bypasses it only for a near pack (RSSI-driven, below).
    nf_byp = cascade_nf_db(rack_chain(COAX_BUDGET_DB, False, True, wil))
    nf_sys = cascade_nf_db(rack_chain(COAX_BUDGET_DB, True, True, wil))
    assert nf_byp > AUDIT4_SYS_NF_DB >= nf_sys, "module LNA needed at the 6 dB coax budget, and sufficient"
    assert cascade_nf_db(rack_chain(COAX_ADR16_DB, False, True, wil)) <= AUDIT4_SYS_NF_DB, "ADR-0016 coax: bypass ok"
    sens = -174 + 10 * math.log10(2e6) + nf_sys + 10
    rng = link_range_m(REGIONS["UK"]["eirp_dbm"], 3.0, nf_sys, g_rx=PATCH_DBI)
    print(f"  worst case (6 dB coax, max NF, module LNA on): NF {nf_sys:.2f} dB vs {AUDIT4_SYS_NF_DB:.2f} assumed"
          f" by Audit 4 (bypassed: {nf_byp:.2f}) -> sensitivity {sens:.1f} dBm at the antenna, indoor n=3 range"
          f" {rng:.0f} m (UK 9 dBm)")
    cost, c, n = r1_noise_cost_db(nf_sys)
    print(f"  R1 margin: pack {c:.1f} dBm (10 m, body 10 dB, fade 10 dB), noise {n:.1f} dBm/2 MHz -> receiver noise"
          f" costs {cost:.2f} dB of the {MARGIN_DB:.0f} dB R1 C/I margin")
    assert cost <= 0.5, "receiver noise must not eat the ADR-0016 R1 margin"

    # ---- compression and intermodulation: levels at the LNA input, no coax (short cable = worst) ----
    near_rule = REGIONS["US"]["eirp_dbm"] - fspl_db(4.0) + PATCH_DBI - CONN_DB
    near_off = REGIONS["US"]["eirp_dbm"] - fspl_db(1.0) + PATCH_DBI - CONN_DB
    wifi_in = 20.0 - fspl_db(2.0) + PATCH_DBI - CONN_DB           # Audit 4 worst: Wi-Fi in front at 2 m
    # install rule (ADR-0016): Wi-Fi >= 4.4 m behind/beside (rear lobe -9 dB) and >= 12.2 m in front
    wifi_rule = max(20.0 - fspl_db(4.4) + PATCH_DBI - 9.0, 20.0 - fspl_db(12.2) + PATCH_DBI) - CONN_DB
    lte_in = LTE_UE_DBM - fspl_db(2.0, 2390) + PATCH_DBI - CONN_DB   # B40 phone in front at 2 m, no patch roll-off
    lte_rule = LTE_UE_DBM - fspl_db(4.4, 2390) + PATCH_DBI - 9.0 - CONN_DB
    tot_rule = dbm_sum(near_rule, wifi_rule, wifi_rule, wifi_rule, lte_rule)   # all on air at once
    tot_off = dbm_sum(near_off, wifi_in, wifi_in, wifi_in, lte_in)
    print(f"  LNA input, install rule: near pack {near_rule:.1f} dBm (4 m), Wi-Fi {wifi_rule:.1f} x3, B40 UE"
          f" {lte_rule:.1f} -> total {tot_rule:.1f} dBm, {lna['ip1db_min'] - tot_rule:.1f} dB below the worst input"
          f" P1dB {lna['ip1db_min']:.1f}")
    print(f"  LNA input, everything off-rule (pack 1 m, Wi-Fi 1/6/11 and a B40 phone 2 m in front): near pack"
          f" {near_off:.1f}, Wi-Fi {wifi_in:.1f} x3, B40 {lte_in:.1f} -> total {tot_off:.1f} dBm,"
          f" {lna['ip1db_min'] - tot_off:.1f} dB below the worst P1dB ({lna['ip1db'] - tot_off:.1f} dB below typical)")
    assert lna["ip1db_min"] - tot_rule >= 10, "install rule: >= 10 dB below the worst-case input P1dB"
    assert tot_off < lna["ip1db_min"], "off-rule pile-up: still below the worst-case input P1dB"
    assert tot_off < LNA["pin_abs_max_dbm"] - 30
    im3 = 3 * wifi_in - 2 * lna["iip3_min"] - 10 * math.log10(60 / 2)   # Audit 4 form, real IIP3
    im3_np = 2 * near_rule + wifi_in - 2 * lna["iip3_min"] - 10 * math.log10(20 / 2)   # near pack x Wi-Fi
    wanted = REGIONS["UK"]["eirp_dbm"] - (40.2 + 20) + PATCH_DBI
    print(f"  IM3 at worst IIP3 {lna['iip3_min']:+.1f} dBm: Wi-Fi x Wi-Fi {im3:.0f} dBm/2 MHz, near pack x Wi-Fi"
          f" {im3_np:.0f} dBm/2 MHz, vs pack at 10 m {wanted:.0f} dBm (Audit 4 asked for 20 dB below)")
    assert max(im3, im3_np) < wanted - 20
    g_mod = sum(g for g, _ in rack_chain(0.0, False, True, wil)[1:-1]) + FRONT_END_DB   # LNA input -> nRF5340
    g_on = g_mod + MODULE_BYPASS_DB + MODULE_LNA[0]
    print(f"  LNA input -> nRF5340: {g_on:+.1f} dB module LNA on / {g_mod:+.1f} bypassed. Near pack at the radio"
          f" (US 20 dBm, short coax): install rule {near_rule + g_on:.1f} dBm with the module LNA on; off-rule (1 m)"
          f" {near_off + g_mod:.1f} dBm bypassed, vs {NRF5340_PMAX_DBM:.0f} dBm max. Firmware: bypass the nRF21540"
          f" LNA when the radio sees > {NRF5340_PMAX_DBM - 6:.0f} dBm (RSSI), back on below {NRF5340_PMAX_DBM - 12:.0f}")
    assert near_rule + g_on <= NRF5340_PMAX_DBM, "install rule: the module LNA can stay on"
    assert near_off + g_mod <= NRF5340_PMAX_DBM - 6, "off-rule: bypassed, the radio keeps 6 dB below its maximum"
    print(f"  LTE B40 UE (2390 MHz) at the radio with no filter credit, module LNA on: {lte_rule + g_on:.1f} dBm"
          f" (install rule, 4.4 m behind) / {lte_in + g_on:.1f} dBm (2 m in front). The QPQ1907 rejection at"
          f" 2390 MHz and the nRF5340 blocking figure decide it: not read, ADR-0018 open item")

    print("\n== Audit 6: rack BOM (one rack, GBP ex VAT; hw/rack/out/bom.csv + 8 sub-boards + ADR-0016 antennas) ==")
    import importlib.util
    spec = importlib.util.spec_from_file_location("rack_prices", pathlib.Path(__file__).resolve().parent / "hw/rack/prices.py")
    rp = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(rp)
    rk = bom_rack()
    for r in rk:
        label = r["value"] if r["mpn"] in ("-", "PCB_TRACE") or r["mpn"].startswith(("R_", "C_")) else r["mpn"]
        print(f"  {label[:46]:<46} x{r['qty']:<3} GBP {float(r['ext_gbp']):7.2f}  {r['uk_distributor']}")
    main_gbp = sum(float(r["ext_gbp"]) for r in rk)
    rx_gbp = sum(float(r["ext_gbp"]) for r in bom_rx())
    est = sum(float(r["ext_gbp"]) for r in rk if r["source"].startswith("est."))
    tot = main_gbp + 8 * rx_gbp + rp.ANTENNA_KIT_GBP
    print(f"  main board + host + cables GBP {main_gbp:.2f} (est. lines GBP {est:.2f}); 8 sub-boards GBP {8 * rx_gbp:.2f}"
          f" (converted, hw/rx/out/bom.csv); antennas + coax GBP {rp.ANTENNA_KIT_GBP:.2f} (ADR-0016)"
          f" -> rack GBP {tot:.2f} ex VAT. No cap in SPEC/AUDIT, so none asserted")
    assert all(r["uk_distributor"] and r["source"] for r in rk), "every rack BOM line needs a UK distributor and source"
