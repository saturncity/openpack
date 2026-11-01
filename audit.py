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


# ---- #26: corrected SYS-2 latency budget, TD options (docs/analysis/td-latency.md). Run: python3 audit.py ----
FS_HZ = 48000
V1_LEN, TD_LEN = 42, 81  # AIR-3 payload B: v1 frame; + td_audio 39 B (frame n-2)
SYS2_TARGET_US, SYS2_HARD_US, SYS2_TD_DESIGN_US = 3000, 5000, 4600
SIM_A_MEASURED_US = {42: 864, 63: 1032, 81: 1176}  # tests/bsim/scenarios/run.py (a) max sim latency, 2026-10-31
SPEC_V1_US = 2720  # SPEC section 2 table before #26 (its SYS-2 line said 2.6 ms)
ADC_GD_FS = {"linear": 17.1, "low": 7.7}  # PCM1840 at 48 kHz, 1/fs: SBAS989 Table 12 / Table 18 (MD0=1)
DAC_GD_FS = {"normal": 22.0, "low": 3.5}  # PCM5102A, 1/fs: SLAS859C Table 4 (FLT=0) / Table 7 (FLT=1)


def air_us(payload_b):
    """One copy on air, AIR-2 BLE 2M layout: preamble 2 + AA 4 + S0 1 + LEN 1 + payload + CRC 3 (sched.c AIR_US)."""
    return (2 + 4 + 1 + 1 + payload_b + 3) * 4


def sys2_stages(payload_b=V1_LEN, td_frames=0, frame_us=1000, t_gap=100, out_slot=200, dac_block=8,
                adc_gd=ADC_GD_FS["low"], dac_gd=DAC_GD_FS["normal"], ramp=41, enc_ipc=100, payload_b_copy_b=None):
    """SYS-2 per stage (us). The sim part (encode + IPC .. output slot) is what run.py (a) measures."""
    return {
        "ADC decimation filter": adc_gd / FS_HZ * 1e6,
        "frame accumulation": frame_us,
        "encode + IPC": enc_ipc,
        "TX ramp-up (copy A)": ramp,
        "copy A on air": air_us(payload_b),
        "T_GAP (incl. copy B ramp)": t_gap,
        "copy B on air": air_us(payload_b if payload_b_copy_b is None else payload_b_copy_b),
        "output slot (decode + jitter, ADR-0013)": out_slot,
        "DAC DMA block": dac_block / FS_HZ * 1e6,
        "DAC interpolation filter": dac_gd / FS_HZ * 1e6,
        "time diversity (played after packet n+d)": td_frames * frame_us,
    }


SIM_STAGES = ("encode + IPC", "TX ramp-up (copy A)", "copy A on air", "T_GAP (incl. copy B ramp)", "copy B on air",
              "output slot (decode + jitter, ADR-0013)")


def sys2_us(**kw):
    return sum(sys2_stages(**kw).values())


def carrier_airtime(payload_b, frame_us=1000, ramp=41):
    return (ramp + air_us(payload_b)) / frame_us


# Candidate changes for TD on (d = 2, 81 B unless stated), each on top of the corrected baseline. R1 numbers are
# from run.py (b), docs/analysis/td-latency.md. kwargs override sys2_stages().
TD_OPTIONS = [
    ("baseline TD on (corrected)", {}),
    ("DAC low-latency filter (PCM5102A FLT=1)", {"dac_gd": DAC_GD_FS["low"]}),
    ("TD offset d=1 (frame n-1 in packet n)", {"td_frames": 1}),
    ("partial TD: td_audio ADPCM-3 (63 B)", {"payload_b": 63}),
    ("T_GAP 100 -> 60 us", {"t_gap": 60}),
    ("output slot 200 -> 150 us", {"out_slot": 150}),
    ("DAC DMA block 8 -> 4 samples", {"dac_block": 4}),
    ("0.75 ms frames, 63 B TD packet", {"frame_us": 750, "payload_b": 63, "off_payload_b": 33}),
    ("PCM1840 linear phase instead (MD0=0)", {"adc_gd": ADC_GD_FS["linear"]}),
    ("DAC FLT=1 + DMA block 4", {"dac_gd": DAC_GD_FS["low"], "dac_block": 4}),
    ("DAC FLT=1 + TD d=1", {"dac_gd": DAC_GD_FS["low"], "td_frames": 1}),
    ("DAC FLT=1 + partial TD 63 B", {"dac_gd": DAC_GD_FS["low"], "payload_b": 63}),
    ("td_audio in copy A only (copy B 42 B)", {"payload_b_copy_b": V1_LEN}),
]

if __name__ == "__main__":
    print("\n== #26: SYS-2 latency, corrected budget (datasheet filters, bsim air times) ==")
    off = sys2_stages()
    on = sys2_stages(payload_b=TD_LEN, td_frames=2)
    print(f"  {'stage':<46}{'TD off':>8}{'TD on':>8}")
    for k in off:
        print(f"  {k:<46}{off[k]:8.0f}{on[k]:8.0f}")
    t_off, t_on = sum(off.values()), sum(on.values())
    print(f"  {'TOTAL':<46}{t_off:8.0f}{t_on:8.0f}   (target {SYS2_TARGET_US}, hard {SYS2_HARD_US})")
    for n in SIM_A_MEASURED_US:  # the model reproduces the bsim (a) measurement
        sim = sum(sys2_stages(payload_b=n)[k] for k in SIM_STAGES)
        assert abs(sim - SIM_A_MEASURED_US[n]) <= 5, f"{n} B: model {sim:.0f} vs bsim {SIM_A_MEASURED_US[n]} us"
    assert air_us(V1_LEN) == 212 and air_us(TD_LEN) == 368

    # run.py (a) projects with the old SPEC lines (ADC 350, DAC 400, DMA 170, accumulation 1000):
    spec_lines = {"ADC": 350, "acc": 1000, "enc": 100, "A": 200, "gap": 100, "B": 200, "slot": 200, "dma": 170, "dac": 400}
    assert sum(spec_lines.values()) == SPEC_V1_US
    rp_off = SIM_A_MEASURED_US[V1_LEN] + 1920
    rp_on = SIM_A_MEASURED_US[TD_LEN] + 1920 + 2000
    r42, r81 = SIM_A_MEASURED_US[V1_LEN] - 865, SIM_A_MEASURED_US[TD_LEN] - 1177
    print(f"  run.py (a) projection: TD off {rp_off} us, TD on {rp_on} us; SPEC said 2600 / 4600")
    print(f"    TD off {rp_off - 2600:+d} = SYS-2 text vs its own table {SPEC_V1_US - 2600:+d}"
          f" + TX ramp not in the table +41 + 53 B copies (212 us, not 200) +24 + rounding {r42:+d}")
    print(f"    TD on  {rp_on - 4600:+d} = {SPEC_V1_US - 2600:+d} + 41 + 92 B copies (368 us, not 200) "
          f"+{2 * (368 - 200)} + rounding {r81:+d}")
    assert rp_off - 2600 == (SPEC_V1_US - 2600) + 41 + 24 + r42
    assert rp_on - 4600 == (SPEC_V1_US - 2600) + 41 + 336 + r81
    print(f"    datasheet filters, not in run.py: ADC {off['ADC decimation filter'] - 350:+.0f} (MD0=1 is already "
          f"strapped in hw/pack/pack.py), DAC {off['DAC interpolation filter'] - 400:+.0f} (22/fs, not 19/fs)")
    assert t_off <= SYS2_TARGET_US, "TD off must meet the R3 target"
    assert t_on <= SYS2_HARD_US, "TD on must meet the R3 hard limit"
    assert t_on > SYS2_TD_DESIGN_US, "TD on meets 4.6 ms with no change: update docs/analysis/td-latency.md"

    print("\n== #26: TD-on options (each alone unless combined) ==")
    print(f"  {'option':<44}{'TD on':>7}{'vs 4.6':>8}{'TD off':>8}{'air/carrier':>12}")
    res = {}
    for name, kw in TD_OPTIONS:
        k_on = {"payload_b": TD_LEN, "td_frames": 2, **{k: v for k, v in kw.items() if k != "off_payload_b"}}
        k_off = {k: v for k, v in kw.items() if k not in ("payload_b", "td_frames", "off_payload_b", "payload_b_copy_b")}
        k_off["payload_b"] = kw.get("off_payload_b", V1_LEN)
        res[name] = (sys2_us(**k_on), sys2_us(**k_off))
        air = carrier_airtime(k_on["payload_b"], k_on.get("frame_us", 1000))
        print(f"  {name:<44}{res[name][0]:7.0f}{res[name][0] - SYS2_TD_DESIGN_US:+8.0f}{res[name][1]:8.0f}{air:12.0%}")
    assert res["DAC low-latency filter (PCM5102A FLT=1)"][0] <= SYS2_TD_DESIGN_US
    assert res["DAC low-latency filter (PCM5102A FLT=1)"][1] <= SYS2_TARGET_US
    assert res["DAC FLT=1 + DMA block 4"][0] <= SYS2_TD_DESIGN_US - 100
    assert res["partial TD: td_audio ADPCM-3 (63 B)"][0] > SYS2_TD_DESIGN_US, "partial TD alone does not reach 4.6"
    assert res["PCM1840 linear phase instead (MD0=0)"][0] > SYS2_HARD_US, "keep MD0=1 (ADR-0012)"
    assert res["DAC FLT=1 + partial TD 63 B"][0] <= SYS2_TD_DESIGN_US - 150
    assert carrier_airtime(TD_LEN) <= 0.45, "AIR-7"
    # AIR-4/SYS-7 RX slot: copy B must end by t0 + 700. 63 B and 81 B do not fit (TD build sets OP_RX_WINDOW_US=0).
    for n in (V1_LEN, 57, 63, TD_LEN):
        end = 41 + 2 * air_us(n) + 100
        print(f"  RX slot: {n} B payload -> copy B ends t0+{end} us ({'fits' if end <= 700 else 'misses'} t0+700)")
    assert 41 + 2 * air_us(57) + 100 <= 700 < 41 + 2 * air_us(63) + 100
    # 0.75 ms frames: 36 samples = 27 B audio + 6 B header + 30 B td = 63 B; fits 750 us only with no RX slot.
    assert 41 + 2 * air_us(63) + 100 <= 750


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
    assert len(gaps) == 8 and all(carrier_ci_db(f, "US", 20) >= CI_REQ_DB for f in gaps)  # UK plan: + 2482 (ADR-0016)
    assert sum(carrier_ci_db(f, "UK", 20) >= CI_REQ_DB for f in gaps) <= 2, "UK worst case: gap carriers fail"  # 2479, 2482 hold
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
    under13 = [f for f in gaps if abs(f - UK_WIFI_13) <= 10]  # 2482 is 10 MHz off, like 2402 vs Wi-Fi 1 (host/channel_plan.py)
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


# ---- Audit 5: ADR-0016 (#26, #89). 2482 MHz legality, the real rack antenna, the theatre install rule. ----
# EN 300 328 V2.2.2 (2019-07): 4.3.2.7 OCB = 99 % power bandwidth, "within the band given in table 1" (2400-2483.5),
#   5.4.7: normal conditions only, lowest and highest channel. 4.3.2.8 Figure 3: OOB domain 2483.5 .. +BW at
#   -10 dBm/MHz EIRP (A), +BW .. +2BW at -20 (B), BW = OCB or 1 MHz; 5.4.8: 1 MHz RMS during the burst, normal
#   conditions, declared antenna gain added. 4.3.2.9 Table 12: spurious above 1 GHz -30 dBm / 1 MHz.
# nRF5340 PS v1.3.1 radio transmitter spec: PRF1,2 1st adjacent channel power 2 MHz (2 Mbps) -25 dBc; PRF2,2 4 MHz
#   -50 dBc. nRF21540 (ADR-0015 keeps it): POUTB 10 dB gain, max output +22 dBm; at +7 dBm conducted it is 15 dB
#   backed off, and GFSK is constant-envelope, so it passes the nRF5340 spectrum through in dBc.
# Measured (ISL-18LR094E328, EN 300 328 V2.1.1, Fanstel BT840, nRF52840, BLE, rate not stated): OCB 1.84 MHz at
#   2480, highest frequency 2480.978 MHz, uncertainty +-0.12 MHz; OOB 2483.5..+BW -44.6 dBm/MHz at 4.84 dBm EIRP.
BAND_TOP = 2483.5
OOB_A, OOB_B, SPUR_DBM = -10.0, -20.0, -30.0
ACP1_2M_DBC, ACP2_2M_DBC = -25.0, -50.0   # nRF5340 PRF1,2 (1-3 MHz off), PRF2,2 (3-5 MHz off)
XTAL_PPM = 50.0          # BLE core spec carrier tolerance (+-50 ppm); the pack's 32 MHz HFXO is tighter
OCB_UNC_MHZ = 0.12       # lab 99 % OBW uncertainty (ISL report)
ISL_2480_TOP = 2480.978  # measured 99 % upper edge at 2480 MHz (nRF52840)
FEM_MAX_DBM, FEM_OUT_DBM = 22.0, 7.0
# Rack antenna (Phase 5 purchase): L-com HyperLink HG2409P-NF, 8 dBi flat patch, HPBW 75 H / 65 V, 2400-2500 MHz,
# N-female on a 12 in lead; ds_HG2409P-NF.pdf. The datasheet gives no F/B number, only polar plots; read off them:
# 180 deg -18 dB (V plane) / ~-30 dB (H plane), but rear lobes reach -9 dB (V, ~120 deg) and -10 dB (H, ~135 deg).
# A rear-hemisphere audience sees the lobes, so the real rejection behind and beside is 9 dB, not the 15 dB est.
ANT = {"name": "L-com HG2409P-NF", "dbi": 8.0, "hpbw": (75, 65), "fb_180": 18.0, "rear_lobe": 9.0, "gbp": 72.12}
# Theatre geometry for the install rule (est.): pack worn at <= 1.5 m above the stage floor (belt on a rostrum);
# audience phone <= 1.5 m above its floor (standing); stage floor >= 0 m above the audience floor (studio, worst);
# nearest audience 1 m horizontally from the antenna's foot.
PACK_H, PHONE_H, STAGE_H, ROW_M = 1.5, 1.5, 0.0, 1.0

if __name__ == "__main__":
    print("\n== Audit 5: ADR-0016, 2482 MHz under EN 300 328 V2.2.2, real rack antenna, install rule ==")
    fr, p = gfsk_spectrum()
    _, obw = psd_stats()
    f0, df = 2482.0, 2482.0 * XTAL_PPM * 1e-6
    top_model = f0 + obw / 2 + df + OCB_UNC_MHZ
    top_meas = ISL_2480_TOP + 2.0 + df + OCB_UNC_MHZ
    print(f"  4.3.2.7 OCB: ideal BLE-2M GFSK 99 % OBW {obw:.2f} MHz; at 2482 + {XTAL_PPM:.0f} ppm ({df * 1e3:.0f} kHz) +"
          f" lab uncertainty: upper edge {top_model:.2f} MHz (model), {top_meas:.2f} (nRF52840 measured at 2480,"
          f" moved up 2 MHz) vs {BAND_TOP}. Fails only if the OCB exceeds {2 * (BAND_TOP - f0 - df - OCB_UNC_MHZ):.2f} MHz")
    assert max(top_model, top_meas) <= BAND_TOP - 0.2, "2482: 99 % OBW must sit inside 2400-2483.5 with margin"
    eirp = REGIONS["UK"]["eirp_dbm"]

    def seg_model(lo, hi):  # ideal GFSK power in [lo, hi) MHz absolute, carrier at f0 + df (worst: drifted up)
        sel = (fr >= (lo - f0 - df) * 1e6) & (fr < (hi - f0 - df) * 1e6)
        return eirp + 10 * math.log10(max(float(p[sel].sum()), 1e-30))

    def seg_bound(lo, hi):  # datasheet bound: PRF1,2 covers 1-3 MHz off the carrier, PRF2,2 3-5 MHz and beyond
        off_lo, off_hi = lo - f0 - df, hi - f0 - df
        parts = [ACP1_2M_DBC] if off_lo < 3 else []
        parts += [ACP2_2M_DBC] if off_hi > 3 else []
        assert off_lo >= 1, "segment reaches inside the 1st adjacent window"
        return eirp + 10 * math.log10(sum(10 ** (x / 10) for x in parts))
    bw = max(obw, 1.0)
    segs = {"A": [(BAND_TOP, BAND_TOP + 1), (BAND_TOP + bw - 1, BAND_TOP + bw)],
            "B": [(BAND_TOP + bw, BAND_TOP + bw + 1), (BAND_TOP + 2 * bw - 1, BAND_TOP + 2 * bw)],
            "spur": [(BAND_TOP + 2 * bw, BAND_TOP + 2 * bw + 1)]}
    lim = {"A": OOB_A, "B": OOB_B, "spur": SPUR_DBM}
    for k, ss in segs.items():
        b = max(seg_bound(*s) for s in ss)
        m = max(seg_model(*s) for s in ss)
        print(f"  4.3.2.{'8' if k != 'spur' else '9'} {k:<4} {ss[0][0]:.1f}-{ss[-1][1]:.1f} MHz: datasheet bound {b:6.1f},"
              f" ideal GFSK {m:6.1f} dBm/MHz at {eirp:.0f} dBm EIRP vs {lim[k]:.0f} -> margin {lim[k] - b:.1f} dB")
        assert b <= lim[k] - 5, f"2482 {k}: need >= 5 dB under the EN 300 328 mask on the datasheet bound"
    print(f"  nRF21540 POUTB at +{FEM_OUT_DBM:.0f} dBm: {FEM_MAX_DBM - FEM_OUT_DBM:.0f} dB under its +{FEM_MAX_DBM:.0f} dBm max,"
          f" constant-envelope GFSK -> no spectral regrowth term. Verdict: 2482 is EN 300 328 compliant (UK/EU);"
          f" US stays at 2480 (15.205). Phase 5 bench check: 99 % OBW and 2483.5-2487.6 MHz at 2482 on a real pack")
    assert FEM_MAX_DBM - FEM_OUT_DBM >= 10

    rej = rejection_db("behind", ANT["rear_lobe"])
    hold = sorted(f for f in gapc.values() if rej >= need[f] - 1e-9)
    print(f"  rack antenna {ANT['name']} ({ANT['dbi']:.0f} dBi, {ANT['hpbw'][0]}/{ANT['hpbw'][1]} deg, GBP"
          f" {ANT['gbp']:.2f}): F/B {ANT['fb_180']:.0f} dB at 180 deg, rear lobes -{ANT['rear_lobe']:.0f} dB ->"
          f" rejection {rej:.1f} dB (study est. {rejection_db('behind'):.1f})")
    print(f"    Q3 geometry (Wi-Fi 2 m behind): {len(hold)}/8 gap carriers hold ({', '.join(map(str, hold))});"
          f" the 11 MHz carriers need {worst:.1f}")
    assert len(hold) == 3 and rej < worst, "real F/B is worse than the 15 dB estimate: R1 rests on distance"
    d_wifi = 2.0 * 10 ** ((worst + MARGIN_DB - rej) / 20)
    print(f"    with {MARGIN_DB:.0f} dB margin, Wi-Fi must be >= {d_wifi:.1f} m behind or beside an antenna"
          f" (study: {wifi_min_dist_m(worst, 'behind'):.1f} / {wifi_min_dist_m(worst, 'beside'):.1f} m),"
          f" >= {wifi_min_dist_m(worst, 'front'):.1f} m in front. That is --wifi-gain"
          f" {ANT['dbi'] - rej - 20 * math.log10(d_wifi / 2):.1f}; bsim (c) 40 %, 20 s, --rx-gain 8 --wifi-gain -7.6"
          f" --near-att 43.2 (2026-11-01): packs 2-8 0.000 % TD on and off")
    assert 4.0 <= d_wifi <= 5.0 and ANT["dbi"] - rej - 20 * math.log10(d_wifi / 2) <= -7.6
    d_actor = math.ceil(d_near * 2) / 2
    h_actor = d_actor + PACK_H
    h_aud = math.sqrt(d_wifi ** 2 - ROW_M ** 2) + PHONE_H - STAGE_H
    h_min = math.ceil(max(h_actor, h_aud) * 2) / 2
    print(f"  install height: actors >= {d_actor:.1f} m (near-far) -> {h_actor:.1f} m; audience >= {d_wifi:.1f} m"
          f" (front row {ROW_M:.0f} m out, phones {PHONE_H} m up, flat floor) -> {h_aud:.1f} m. Rule: antenna"
          f" >= {h_min:.1f} m above the stage floor")
    assert h_min == 6.0, "ADR-0016 front-of-stage rule said 6 m (superseded by ADR-0021, Audit 7)"
    coax = {"CA3N050 400-series 50 ft (15.2 m)": 15.24 * COAX_DB_M["LMR-400"],
            "HG2409P lead 12 in": 0.3 * COAX_DB_M["RG-58"], "LCCA30301-FT1.5 BNC-N jumper": 0.46 * COAX_DB_M["LMR-400"]}
    loss = sum(coax.values()) + 3 * 0.15
    print(f"  per antenna: {' + '.join(coax)} + 3 connectors = {loss:.1f} dB (RK-2 budget 6);"
          f" GBP {ANT['gbp']:.2f} + 61.07 + 37.09 = {ANT['gbp'] + 61.07 + 37.09:.2f}, x2 per rack ex VAT")
    assert loss <= 6.0 and 2 * (ANT["gbp"] + 61.07 + 37.09) <= 400


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


# ---- #26: corrected SYS-2 latency budget, TD options (docs/analysis/td-latency.md). Run: python3 audit.py ----
FS_HZ = 48000
V1_LEN, TD_LEN = 42, 81  # AIR-3 payload B: v1 frame; + td_audio 39 B (frame n-2)
SYS2_TARGET_US, SYS2_HARD_US, SYS2_TD_DESIGN_US = 3000, 5000, 4600
SIM_A_MEASURED_US = {42: 864, 63: 1032, 81: 1176}  # tests/bsim/scenarios/run.py (a) max sim latency, 2026-10-31
SPEC_V1_US = 2720  # SPEC section 2 table before #26 (its SYS-2 line said 2.6 ms)
ADC_GD_FS = {"linear": 17.1, "low": 7.7}  # PCM1840 at 48 kHz, 1/fs: SBAS989 Table 12 / Table 18 (MD0=1)
DAC_GD_FS = {"normal": 22.0, "low": 3.5}  # PCM5102A, 1/fs: SLAS859C Table 4 (FLT=0) / Table 7 (FLT=1)


def air_us(payload_b):
    """One copy on air, AIR-2 BLE 2M layout: preamble 2 + AA 4 + S0 1 + LEN 1 + payload + CRC 3 (sched.c AIR_US)."""
    return (2 + 4 + 1 + 1 + payload_b + 3) * 4


def sys2_stages(payload_b=V1_LEN, td_frames=0, frame_us=1000, t_gap=100, out_slot=200, dac_block=8,
                adc_gd=ADC_GD_FS["low"], dac_gd=DAC_GD_FS["normal"], ramp=41, enc_ipc=100, payload_b_copy_b=None):
    """SYS-2 per stage (us). The sim part (encode + IPC .. output slot) is what run.py (a) measures."""
    return {
        "ADC decimation filter": adc_gd / FS_HZ * 1e6,
        "frame accumulation": frame_us,
        "encode + IPC": enc_ipc,
        "TX ramp-up (copy A)": ramp,
        "copy A on air": air_us(payload_b),
        "T_GAP (incl. copy B ramp)": t_gap,
        "copy B on air": air_us(payload_b if payload_b_copy_b is None else payload_b_copy_b),
        "output slot (decode + jitter, ADR-0013)": out_slot,
        "DAC DMA block": dac_block / FS_HZ * 1e6,
        "DAC interpolation filter": dac_gd / FS_HZ * 1e6,
        "time diversity (played after packet n+d)": td_frames * frame_us,
    }


SIM_STAGES = ("encode + IPC", "TX ramp-up (copy A)", "copy A on air", "T_GAP (incl. copy B ramp)", "copy B on air",
              "output slot (decode + jitter, ADR-0013)")


def sys2_us(**kw):
    return sum(sys2_stages(**kw).values())


def carrier_airtime(payload_b, frame_us=1000, ramp=41):
    return (ramp + air_us(payload_b)) / frame_us


# Candidate changes for TD on (d = 2, 81 B unless stated), each on top of the corrected baseline. R1 numbers are
# from run.py (b), docs/analysis/td-latency.md. kwargs override sys2_stages().
TD_OPTIONS = [
    ("baseline TD on (corrected)", {}),
    ("DAC low-latency filter (PCM5102A FLT=1)", {"dac_gd": DAC_GD_FS["low"]}),
    ("TD offset d=1 (frame n-1 in packet n)", {"td_frames": 1}),
    ("partial TD: td_audio ADPCM-3 (63 B)", {"payload_b": 63}),
    ("T_GAP 100 -> 60 us", {"t_gap": 60}),
    ("output slot 200 -> 150 us", {"out_slot": 150}),
    ("DAC DMA block 8 -> 4 samples", {"dac_block": 4}),
    ("0.75 ms frames, 63 B TD packet", {"frame_us": 750, "payload_b": 63, "off_payload_b": 33}),
    ("PCM1840 linear phase instead (MD0=0)", {"adc_gd": ADC_GD_FS["linear"]}),
    ("DAC FLT=1 + DMA block 4", {"dac_gd": DAC_GD_FS["low"], "dac_block": 4}),
    ("DAC FLT=1 + TD d=1", {"dac_gd": DAC_GD_FS["low"], "td_frames": 1}),
    ("DAC FLT=1 + partial TD 63 B", {"dac_gd": DAC_GD_FS["low"], "payload_b": 63}),
    ("td_audio in copy A only (copy B 42 B)", {"payload_b_copy_b": V1_LEN}),
]

if __name__ == "__main__":
    print("\n== #26: SYS-2 latency, corrected budget (datasheet filters, bsim air times) ==")
    off = sys2_stages()
    on = sys2_stages(payload_b=TD_LEN, td_frames=2)
    print(f"  {'stage':<46}{'TD off':>8}{'TD on':>8}")
    for k in off:
        print(f"  {k:<46}{off[k]:8.0f}{on[k]:8.0f}")
    t_off, t_on = sum(off.values()), sum(on.values())
    print(f"  {'TOTAL':<46}{t_off:8.0f}{t_on:8.0f}   (target {SYS2_TARGET_US}, hard {SYS2_HARD_US})")
    for n in SIM_A_MEASURED_US:  # the model reproduces the bsim (a) measurement
        sim = sum(sys2_stages(payload_b=n)[k] for k in SIM_STAGES)
        assert abs(sim - SIM_A_MEASURED_US[n]) <= 5, f"{n} B: model {sim:.0f} vs bsim {SIM_A_MEASURED_US[n]} us"
    assert air_us(V1_LEN) == 212 and air_us(TD_LEN) == 368

    # run.py (a) projects with the old SPEC lines (ADC 350, DAC 400, DMA 170, accumulation 1000):
    spec_lines = {"ADC": 350, "acc": 1000, "enc": 100, "A": 200, "gap": 100, "B": 200, "slot": 200, "dma": 170, "dac": 400}
    assert sum(spec_lines.values()) == SPEC_V1_US
    rp_off = SIM_A_MEASURED_US[V1_LEN] + 1920
    rp_on = SIM_A_MEASURED_US[TD_LEN] + 1920 + 2000
    r42, r81 = SIM_A_MEASURED_US[V1_LEN] - 865, SIM_A_MEASURED_US[TD_LEN] - 1177
    print(f"  run.py (a) projection: TD off {rp_off} us, TD on {rp_on} us; SPEC said 2600 / 4600")
    print(f"    TD off {rp_off - 2600:+d} = SYS-2 text vs its own table {SPEC_V1_US - 2600:+d}"
          f" + TX ramp not in the table +41 + 53 B copies (212 us, not 200) +24 + rounding {r42:+d}")
    print(f"    TD on  {rp_on - 4600:+d} = {SPEC_V1_US - 2600:+d} + 41 + 92 B copies (368 us, not 200) "
          f"+{2 * (368 - 200)} + rounding {r81:+d}")
    assert rp_off - 2600 == (SPEC_V1_US - 2600) + 41 + 24 + r42
    assert rp_on - 4600 == (SPEC_V1_US - 2600) + 41 + 336 + r81
    print(f"    datasheet filters, not in run.py: ADC {off['ADC decimation filter'] - 350:+.0f} (MD0=1 is already "
          f"strapped in hw/pack/pack.py), DAC {off['DAC interpolation filter'] - 400:+.0f} (22/fs, not 19/fs)")
    assert t_off <= SYS2_TARGET_US, "TD off must meet the R3 target"
    assert t_on <= SYS2_HARD_US, "TD on must meet the R3 hard limit"
    assert t_on > SYS2_TD_DESIGN_US, "TD on meets 4.6 ms with no change: update docs/analysis/td-latency.md"

    print("\n== #26: TD-on options (each alone unless combined) ==")
    print(f"  {'option':<44}{'TD on':>7}{'vs 4.6':>8}{'TD off':>8}{'air/carrier':>12}")
    res = {}
    for name, kw in TD_OPTIONS:
        k_on = {"payload_b": TD_LEN, "td_frames": 2, **{k: v for k, v in kw.items() if k != "off_payload_b"}}
        k_off = {k: v for k, v in kw.items() if k not in ("payload_b", "td_frames", "off_payload_b", "payload_b_copy_b")}
        k_off["payload_b"] = kw.get("off_payload_b", V1_LEN)
        res[name] = (sys2_us(**k_on), sys2_us(**k_off))
        air = carrier_airtime(k_on["payload_b"], k_on.get("frame_us", 1000))
        print(f"  {name:<44}{res[name][0]:7.0f}{res[name][0] - SYS2_TD_DESIGN_US:+8.0f}{res[name][1]:8.0f}{air:12.0%}")
    assert res["DAC low-latency filter (PCM5102A FLT=1)"][0] <= SYS2_TD_DESIGN_US
    assert res["DAC low-latency filter (PCM5102A FLT=1)"][1] <= SYS2_TARGET_US
    assert res["DAC FLT=1 + DMA block 4"][0] <= SYS2_TD_DESIGN_US - 100
    assert res["partial TD: td_audio ADPCM-3 (63 B)"][0] > SYS2_TD_DESIGN_US, "partial TD alone does not reach 4.6"
    assert res["PCM1840 linear phase instead (MD0=0)"][0] > SYS2_HARD_US, "keep MD0=1 (ADR-0012)"
    assert res["DAC FLT=1 + partial TD 63 B"][0] <= SYS2_TD_DESIGN_US - 150
    assert carrier_airtime(TD_LEN) <= 0.45, "AIR-7"
    # AIR-4/SYS-7 RX slot: copy B must end by t0 + 700. 63 B and 81 B do not fit (TD build sets OP_RX_WINDOW_US=0).
    for n in (V1_LEN, 57, 63, TD_LEN):
        end = 41 + 2 * air_us(n) + 100
        print(f"  RX slot: {n} B payload -> copy B ends t0+{end} us ({'fits' if end <= 700 else 'misses'} t0+700)")
    assert 41 + 2 * air_us(57) + 100 <= 700 < 41 + 2 * air_us(63) + 100
    # 0.75 ms frames: 36 samples = 27 B audio + 6 B header + 30 B td = 63 B; fits 750 us only with no RX slot.
    assert 41 + 2 * air_us(63) + 100 <= 750


# ---- Audit 7: R1 with the rack antennas in the wings (#101, ADR-0021, docs/analysis/r1-wing-antennas.md). ----
# Owner constraint 2026-11-01: rack antennas only at the sides of the stage (wings), so ADR-0016's front-of-stage
# rule (>= 6 m up, aimed upstage) is out. Model: sim/loss/wing_geometry.py (3-D free space, HG2409P-NF cuts, the
# bsim modem tables). Venues: studio 6 m, proscenium 10 m, proscenium 12 m. bsim: run.py --geometry (two receivers
# per pack, RX-5 replayed per carrier). The bsim numbers below are from those runs (2026-11-01, 20 s each).
def _wing():
    import importlib.util
    spec = importlib.util.spec_from_file_location("wing_geometry", pathlib.Path(__file__).resolve().parent / "sim/loss/wing_geometry.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["wing_geometry"] = mod
    spec.loader.exec_module(mod)
    return mod


if __name__ == "__main__":
    import sys
    from dataclasses import replace as _repl
    wg = _wing()
    print("\n== Audit 7: R1 with the rack antennas in the wings (#101, ADR-0021) ==")
    thr = wg.ci_threshold_db(2423)
    print(f"  twin: an 11 MHz gap copy (TD length) needs C/I >= {thr:.1f} dB per Wi-Fi channel; design adds"
          f" {wg.MARGIN_DB:.0f} dB. Neighbour pack tolerance 3/4/5 MHz: "
          + " / ".join(f"{wg.neighbour_tolerance_db(o):.1f}" for o in (3, 4, 5)) + " dB")
    assert -13 <= thr <= -11.5, "same threshold as Audit 4 (12.7 dB short at the Q3 geometry)"
    naive = wg.Install(crew_ap_m=3.0)       # mid-wing, 2 m, straight across, crew Wi-Fi allowed 3 m away
    for v in wg.VENUES:
        sn = wg.summary(wg.evaluate(v, naive))
        sr = wg.summary(wg.evaluate(v, wg.RULE))
        nf = wg.near_far(v, wg.RULE)
        sc = wg.summary(wg.evaluate(v, _repl(wg.RULE, crew_ap_m=3.0)))
        print(f"  {v.name:<16} naive (mid-wing, 2 m, across, crew Wi-Fi >= 3 m): {sn['pass_sel']:5.1%} of the stage"
              f" with margin, worst {sn['worst_margin']:+.1f} dB | ADR-0021 rule: {sr['pass_sel']:5.1%}, worst"
              f" {sr['worst_margin']:+.1f} dB, with an actor at the boom {nf['worst']:+.1f} dB | rule but crew Wi-Fi"
              f" 3 m away: worst {sc['worst_margin']:+.1f}")
        assert sn["worst_margin"] < -wg.MARGIN_DB + 1.5, "the naive wing mount is short (why the rule exists)"
        assert sr["pass_sel"] >= 0.97 and sr["worst_margin"] >= -0.5, "rule: >= 97 % of the stage with the full 3 dB, all with >= 2.5"
        assert sr["worst_best"] > -wg.MARGIN_DB and nf["worst"] > -wg.MARGIN_DB, "rule: every point above the twin threshold, near pack included"
        assert sc["worst_margin"] < -wg.MARGIN_DB, "crew Wi-Fi in the wings breaks it: the rule bans it"
    lo = [wg.near_far(v, wg.RULE_LO)["worst"] for v in wg.VENUES]
    print(f"  same rule on a 2 m stand: near-far worst {min(lo):+.1f} dB (3.5 m boom: actors >= "
          f"{wg.dist(wg.antennas(wg.STUDIO, wg.RULE)[0][1], wg.near(wg.STUDIO, wg.RULE)[0]):.1f} m away)")
    assert min(lo) < -wg.MARGIN_DB, "2 m is too low: an actor at the stand blocks 3 MHz neighbours on both antennas"
    for o in (wg.OMNI3,):
        w = min(wg.summary(wg.evaluate(v, _repl(wg.RULE, ant=o)))["worst_margin"] for v in wg.VENUES)
        print(f"  omni 3 dBi in the wings instead: worst {w:+.1f} dB (sees the audience as well as the stage)")
        assert w < -wg.MARGIN_DB

    print("  rack chain (PR #95 / ADR-0018 draft, nRF21540 always on, no coax; total input >= 6 dB under each P1dB):")
    for v in wg.VENUES:
        e = wg.evaluate(v, wg.RULE)
        _, n_l, _ = wg.near(v, wg.RULE)
        wifi = e.iw["L"][0]
        tot = wg.dbm_sum(n_l, *[wifi] * 3)              # near pack + Wi-Fi 1/6/11 at the worst seat, all on air
        m0, m10 = wg.chain_margins(tot), wg.chain_margins(tot, pad_db=wg.PAD_DB)
        ph = wg.phone_dbm(v, wg.RULE)
        eq_n, eq_p = wg.on_axis_equiv_m(n_l, wg.EIRP_UK), wg.on_axis_equiv_m(ph, 23.0, f=2390.0)
        print(f"    {v.name:<16} near pack {n_l:.1f} dBm (= {eq_n:.1f} m on axis), Wi-Fi {wifi:.1f} x3, B40 phone {ph:.1f}"
              f" (= {eq_p:.1f} m on axis). Headroom LNA / nRF21540 / radio: no pad {m0[0]:+.1f} / {m0[1]:+.1f} /"
              f" {m0[2]:+.1f}; {wg.PAD_DB:.0f} dB pad {m10[0]:+.1f} / {m10[1]:+.1f} / {m10[2]:+.1f}")
        assert min(m10) >= 0, "ADR-0021 + 10 dB pad: nothing compresses"
        assert eq_n >= 1.6 and eq_p >= 9.1, "inside PR #95's 10 dB-pad row (safe near pack 1.6 m, safe phone 9.1 m)"
    m_studio = wg.chain_margins(wg.dbm_sum(*[wg.evaluate(wg.STUDIO, wg.RULE).iw["L"][0]] * 3))
    assert m_studio[1] < 0, "studio audience Wi-Fi alone crowds the nRF21540 with no pad: the pad is needed"
    _, n_ax, _ = wg.near(wg.STUDIO, wg.RULE, 0.5, wg.EIRP_UK, True)
    print(f"    off-rule (pack 0.5 m on axis, {n_ax:.1f} dBm): nRF21540 headroom with the pad"
          f" {wg.chain_margins(n_ax, pad_db=wg.PAD_DB)[1]:+.1f} dB (PR #95: a 20 dB pad would be needed)")
    s_min = min(wg.summary(wg.evaluate(v, wg.RULE))["s_min"] for v in wg.VENUES)
    c = s_min - 10.0 - 10.0                               # weakest pack, body 10 dB + fade 10 dB (as Audit 6)
    nf_pad = 15.9                                         # PR #95's 10 dB-pad row at the 6 dB coax budget
    noise = -174 + 10 * math.log10(2e6) + nf_pad
    cost = 10 * math.log10(1 + 10 ** ((noise - (c - CI_REQ_DB - MARGIN_DB)) / 10))
    print(f"    noise: weakest wing pack {s_min:.1f} dBm (-20 dB body + fade: {c:.1f}); with the pad NF {nf_pad} dB costs"
          f" {cost:.2f} dB of the 3 dB R1 margin (stage ranges, not Audit 4's 10 m)")
    assert cost <= 0.5
    # bsim (c), run.py --geometry docs/analysis/r1-wing/<case>.json --eirp 9 --plan host/channel_plan_us.yaml,
    # 20 s per run. Packs passing SYS-3 (<= 0.1 %, <= 2 in a row) of the 7 with a gap carrier below 2480 (pack 1's
    # is 2482: credited by equivalence, ADR-0016). Filled from the 2026-11-01 runs; see the analysis doc.
    WING_BSIM = {  # case: {run: packs 2-8 passing}; 10 % runs with the old 100-frame probe (strictly harder)
        "studio-rule": {"10% TD off": 7, "10% TD on": 7, "40% TD off": 7, "40% TD on": 7},
        "prosc10-rule": {"10% TD off": 7, "10% TD on": 7, "40% TD off": 7, "40% TD on": 7},
        "prosc12-rule": {"10% TD off": 7, "10% TD on": 7, "40% TD off": 7, "40% TD on": 7},
        "prosc12-near2": {"10% TD off": 7, "10% TD on": 7, "40% TD off": 7, "40% TD on": 7},
        "prosc12-onaxis (off-rule)": {"40% TD off": 6, "40% TD on": 7},
        "studio-onaxis (off-rule, probe 100)": {"40% TD off": 5, "40% TD on": 7},
    }
    for case, r in WING_BSIM.items():
        print(f"  bsim {case}: " + ", ".join(f"{k} {v}/7" for k, v in r.items()))
    assert all(v == 7 for c, r in WING_BSIM.items() if c.endswith("-rule") or c.endswith("near2") for v in r.values())
    assert WING_BSIM["prosc12-onaxis (off-rule)"]["40% TD on"] == 7 > WING_BSIM["prosc12-onaxis (off-rule)"]["40% TD off"]
