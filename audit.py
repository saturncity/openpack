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
