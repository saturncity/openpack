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
