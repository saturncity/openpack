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
