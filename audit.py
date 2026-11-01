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
    # Cell path (#34 review M1). Spring: MY-18650-05-J drawing, ~4 turns of ~9 mm diameter = ~113 mm of wire, assumed
    # 0.5 mm phosphor bronze (1.1e-7 ohm m) -> 63 mOhm (not published: bench-measure). + plate 2, 2 x 60 mm 24 AWG leads
    # 10, ground return through the L2 plane ~5, + the battery-path tracks measured from hw/pack/pack.kicad_pcb (L1).
    import math, pathlib, sys
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent / "hw" / "pack"))
    import layout as _layout
    r_tracks = _layout.battery_path_ohm()
    r_spring = 1.1e-7 * (4 * math.pi * 9e-3) / (math.pi * 0.25e-3 ** 2)
    r_contacts = r_spring + 0.002 + 0.010 + 0.005 + r_tracks
    R_CELL_PATH_BUDGET = 0.10   # ohm: contacts + leads + tracks allowance used before the layout existed
    r_path = 0.023 + 0.10 + 0.03 + r_contacts   # ohm: SF-1206F300 fuse, DMG2305UX Rds(on) at -2.5 V, JS102011SAQN contact, cell path
    i_peak = i_3v3 + i_5v_in
    print(f"  cell path {r_contacts * 1e3:.0f} mOhm (spring {r_spring * 1e3:.0f} est., battery tracks {r_tracks * 1e3:.0f} measured on L1)"
          f" vs {R_CELL_PATH_BUDGET * 1e3:.0f} mOhm budget: {'OVER' if r_contacts > R_CELL_PATH_BUDGET else 'within'};"
          f" {i_peak ** 2 * r_contacts * 1e3:.1f} mW, {i_peak * r_contacts * 1e3:.0f} mV at the {i_peak * 1e3:.0f} mA peak")
    assert i_peak < 1.0, "MYOUNG contacts carry no stated rating; ~1 A is the class figure for 0.3 mm phosphor-bronze cell contacts"
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
    # Usable charge above the cutoff, under the ~0.2 A pack load (0.06 C): typical protected 3.5 Ah 18650 discharge
    # curves leave ~10 % below 3.2 V and ~15 % below 3.3 V (estimate from datasheet curves; bench-check on the PPK2, G5).
    usable = {3.2: 0.90, 3.3: 0.85}[CELL_CUTOFF_V]
    runtime_h = usable * wh / 0.55
    print(f"  runtime at {CELL_CUTOFF_V:.1f} V cutoff, {usable:.0%} of the cell usable, 0.55 W: {runtime_h:.1f} h (PK-7 >= 16 h)")
    assert runtime_h >= 16, "PK-7 fails at this cutoff"


# ---- #26: corrected SYS-2 latency budget, TD options (docs/analysis/td-latency.md). Run: python3 audit.py ----
FS_HZ = 48000
V1_LEN, TD_LEN = 42, 81  # AIR-3 payload B: v1 frame; + td_audio 39 B (frame n-2)
SYS2_TARGET_US, SYS2_HARD_US, SYS2_TD_DESIGN_US = 3000, 5000, 4600
# tests/bsim/scenarios/run.py (a) max sim latency. #26 (2026-10-31) counted encode + IPC as a flat 100 us from t0:
SIM_A_26_US = {42: 864, 63: 1032, 81: 1176}
# #98 (2026-11-01): measured from the app core's audio frame clock; payload latched OP_PACK_LATCH_LEAD_US before TXEN
FRAME_LEAD_US, LATCH_LEAD_US = 100, 20  # fw/Kconfig OP_PACK_FRAME_LEAD_US, OP_PACK_LATCH_LEAD_US
FCLK_TO_TXEN_US = FRAME_LEAD_US + LATCH_LEAD_US  # SPEC section 2 "frame clock -> TXEN"; run.py (a) measures 120
SIM_A_MEASURED_US = {42: 884, 81: 1196}
SPEC_V1_US = 2720  # SPEC section 2 table before #26 (its SYS-2 line said 2.6 ms)
ADC_GD_FS = {"linear": 17.1, "low": 7.7}  # PCM1840 at 48 kHz, 1/fs: SBAS989 Table 12 / Table 18 (MD0=1)
DAC_GD_FS = {"normal": 22.0, "low": 3.5}  # PCM5102A, 1/fs: SLAS859C Table 4 (FLT=0) / Table 7 (FLT=1)


def air_us(payload_b):
    """One copy on air, AIR-2 BLE 2M layout: preamble 2 + AA 4 + S0 1 + LEN 1 + payload + CRC 3 (sched.c AIR_US)."""
    return (2 + 4 + 1 + 1 + payload_b + 3) * 4


def sys2_stages(payload_b=V1_LEN, td_frames=0, frame_us=1000, t_gap=100, out_slot=200, dac_block=8,
                adc_gd=ADC_GD_FS["low"], dac_gd=DAC_GD_FS["normal"], ramp=41, enc_ipc=FCLK_TO_TXEN_US, payload_b_copy_b=None):
    """SYS-2 per stage (us). The sim part (encode + IPC .. output slot) is what run.py (a) measures."""
    return {
        "ADC decimation filter": adc_gd / FS_HZ * 1e6,
        "frame accumulation": frame_us,
        "frame clock -> TXEN (encode + IPC, latch)": enc_ipc,
        "TX ramp-up (copy A)": ramp,
        "copy A on air": air_us(payload_b),
        "T_GAP (incl. copy B ramp)": t_gap,
        "copy B on air": air_us(payload_b if payload_b_copy_b is None else payload_b_copy_b),
        "output slot (decode + jitter, ADR-0013)": out_slot,
        "DAC DMA block": dac_block / FS_HZ * 1e6,
        "DAC interpolation filter": dac_gd / FS_HZ * 1e6,
        "time diversity (played after packet n+d)": td_frames * frame_us,
    }


SIM_STAGES = ("frame clock -> TXEN (encode + IPC, latch)", "TX ramp-up (copy A)", "copy A on air", "T_GAP (incl. copy B ramp)", "copy B on air",
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
    print(f"  {'stage':<48}{'TD off':>8}{'TD on':>8}")
    for k in off:
        print(f"  {k:<48}{off[k]:8.0f}{on[k]:8.0f}")
    t_off, t_on = sum(off.values()), sum(on.values())
    print(f"  {'TOTAL':<46}{t_off:8.0f}{t_on:8.0f}   (target {SYS2_TARGET_US}, hard {SYS2_HARD_US})")
    for n in SIM_A_MEASURED_US:  # the model reproduces the bsim (a) measurement
        sim = sum(sys2_stages(payload_b=n)[k] for k in SIM_STAGES)
        assert abs(sim - SIM_A_MEASURED_US[n]) <= 5, f"{n} B: model {sim:.0f} vs bsim {SIM_A_MEASURED_US[n]} us"
    for n in SIM_A_26_US:  # and the #26 one, with its flat 100 us
        sim = sum(sys2_stages(payload_b=n, enc_ipc=100)[k] for k in SIM_STAGES)
        assert abs(sim - SIM_A_26_US[n]) <= 5, f"{n} B: model {sim:.0f} vs bsim #26 {SIM_A_26_US[n]} us"
    print(f"  frame clock -> TXEN {FCLK_TO_TXEN_US} us = frame lead {FRAME_LEAD_US} + latch {LATCH_LEAD_US} (#98);"
          f" bsim (a) {SIM_A_MEASURED_US[V1_LEN]} / {SIM_A_MEASURED_US[TD_LEN]} us (TD off / on)")
    assert air_us(V1_LEN) == 212 and air_us(TD_LEN) == 368

    # run.py (a) projects with the old SPEC lines (ADC 350, DAC 400, DMA 170, accumulation 1000):
    spec_lines = {"ADC": 350, "acc": 1000, "enc": 100, "A": 200, "gap": 100, "B": 200, "slot": 200, "dma": 170, "dac": 400}
    assert sum(spec_lines.values()) == SPEC_V1_US
    rp_off = SIM_A_26_US[V1_LEN] + 1920
    rp_on = SIM_A_26_US[TD_LEN] + 1920 + 2000
    r42, r81 = SIM_A_26_US[V1_LEN] - 865, SIM_A_26_US[TD_LEN] - 1177
    print(f"  #26 run.py (a) projection: TD off {rp_off} us, TD on {rp_on} us; SPEC said 2600 / 4600")
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
    assert res["DAC FLT=1 + DMA block 4"][0] <= SYS2_TD_DESIGN_US - 80
    assert res["partial TD: td_audio ADPCM-3 (63 B)"][0] > SYS2_TD_DESIGN_US, "partial TD alone does not reach 4.6"
    assert res["PCM1840 linear phase instead (MD0=0)"][0] > SYS2_HARD_US, "keep MD0=1 (ADR-0012)"
    assert res["DAC FLT=1 + partial TD 63 B"][0] <= SYS2_TD_DESIGN_US - 140
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


# Pack feed (#34): the link budget declares EIRP = conducted + WHIP_DBI with no feed loss; the u.FL -> whip pigtail's
# loss is made up by conducted-power headroom, allowed up to PIGTAIL_IL_MAX_DB. Pigtail: BWIPX1-SMA-1.13L150 cut to
# ~0.10 m of 1.13 mm coax (~3.6 dB/m at 2.45 GHz, typical 1.13 mm data) + one mated IPEX/MHF1 pair (~0.1 dB at 3 GHz,
# I-PEX MHF spec class) -> 0.46 dB.
PIGTAIL_IL_MAX_DB = 0.6
PIGTAIL_IL_DB = 0.10 * 3.6 + 0.10


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
    print(f"  pigtail: {PIGTAIL_IL_DB:.2f} dB <= {PIGTAIL_IL_MAX_DB} dB allowance; UK conducted becomes {uk_cond + PIGTAIL_IL_DB:.1f} dBm,"
          f" US {REGIONS['US']['eirp_dbm'] - WHIP_DBI + PIGTAIL_IL_DB:.1f} dBm (BT40NE max 19.1)")
    assert PIGTAIL_IL_DB <= PIGTAIL_IL_MAX_DB
    assert REGIONS["US"]["eirp_dbm"] - WHIP_DBI + PIGTAIL_IL_DB <= 19.1, "US EIRP needs the conducted headroom to cover the pigtail"

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
# Wing coax (#34 cost-down; ADR-0021 rule: antenna 1 m offstage, 1/4 of the stage depth back, 4.0 m up). The rack sits
# in one wing at the prompt corner (downstage, 0.5 m offstage, 1.0 m up in its case). Cable route: along the floor
# to the boom, up the boom; the far wing's run crosses the stage overhead at grid height (BOOM_Z_M), never through the
# acting area. L-com CA-400 (L-com CA-400 datasheet: 6.8 dB / 100 ft at 2500 MHz, 6.0 at 2000), ITM Components UK
# prices ex VAT read 2026-11-01. The rack end uses an N-socket/BNC-plug adapter (RS 285-6398) instead of a jumper.
STAGE_W_M, STAGE_D_M = (6.0, 9.0, 12.0), 12.0     # widths 6-12 m (coordinator), depth up to 12 m
BOOM_Z_M, RACK_Z_M, RUN_SLACK, RUN_DRESS_M = 4.0, 1.0, 0.05, 1.0
CA400_DB_M = 6.8 / 30.48                 # 0.223 dB/m at 2.5 GHz (the 2.4 GHz figure is lower; worst case kept)
CA400 = (("CA3N025", 7.62, 38.96), ("CA3N030", 9.14, 45.80), ("CA3N050", 15.24, 61.07), ("CA3N075", 22.86, 88.02),
         ("CA3N100", 30.48, 114.96))
HG2409P_LEAD_DB, NBNC_ADAPTER_DB, MATED_PAIR_DB = 0.3 * 1.0, 0.1, 0.15   # 12 in RG-58 lead; N-BNC adapter; per pair
RK2_COAX_DB = 6.0        # RK-2 coax budget


def wing_runs_m(stage_w, stage_d=STAGE_D_M):
    """cable metres from the rack to the near- and far-wing booms (Manhattan route, slack, dressing)"""
    up = BOOM_Z_M - RACK_Z_M
    near = 0.5 + stage_d / 4 + up
    far = (stage_w + 1.0 + 0.5) + stage_d / 4 + up
    f = lambda m: m * (1 + RUN_SLACK) + RUN_DRESS_M
    return {"near": f(near), "far": f(far)}


def wing_coax_db(cable_m):
    return cable_m * CA400_DB_M + HG2409P_LEAD_DB + NBNC_ADAPTER_DB + 3 * MATED_PAIR_DB


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
    # #34 cost-down: size each wing's coax from the ADR-0021 geometry instead of one 50 ft run per antenna
    runs = {w: wing_runs_m(w) for w in STAGE_W_M}
    near_need = max(r["near"] for r in runs.values())
    far_need = max(r["far"] for r in runs.values())
    near = next(c for c in CA400 if c[1] >= near_need)
    far = next(c for c in CA400 if c[1] >= far_need)
    print(f"  coax runs, rack in a wing (prompt corner), booms {BOOM_Z_M} m up, 1 m offstage, 1/4 stage depth back,"
          f" cable along the floor/up the boom/over the stage at grid height, x{1 + RUN_SLACK:.2f} + {RUN_DRESS_M} m dressing:")
    for w, r in runs.items():
        print(f"    stage {w:>4.1f} m wide: near wing {r['near']:4.1f} m, far wing {r['far']:4.1f} m")
    for label, (pn, m, gbp) in (("near", near), ("far", far)):
        print(f"    {label}: {pn} ({m:.2f} m, GBP {gbp:.2f}) -> {wing_coax_db(m):.2f} dB with the HG2409P lead, the N-BNC"
              f" adapter and 3 mated pairs (RK-2 budget {RK2_COAX_DB:.0f} dB)")
    assert near[1] >= near_need and far[1] >= far_need
    assert wing_coax_db(far[1]) <= RK2_COAX_DB, "RK-2: the longest wing run stays inside the 6 dB coax budget"
    assert (near[0], far[0]) == ("CA3N030", "CA3N075"), "hw/rack/prices.py ANTENNA_KIT carries these two lengths"


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
# tests/bsim/scenarios/run.py (a) max sim latency. #26 (2026-10-31) counted encode + IPC as a flat 100 us from t0:
SIM_A_26_US = {42: 864, 63: 1032, 81: 1176}
# #98 (2026-11-01): measured from the app core's audio frame clock; payload latched OP_PACK_LATCH_LEAD_US before TXEN
FRAME_LEAD_US, LATCH_LEAD_US = 100, 20  # fw/Kconfig OP_PACK_FRAME_LEAD_US, OP_PACK_LATCH_LEAD_US
FCLK_TO_TXEN_US = FRAME_LEAD_US + LATCH_LEAD_US  # SPEC section 2 "frame clock -> TXEN"; run.py (a) measures 120
SIM_A_MEASURED_US = {42: 884, 81: 1196}
SPEC_V1_US = 2720  # SPEC section 2 table before #26 (its SYS-2 line said 2.6 ms)
ADC_GD_FS = {"linear": 17.1, "low": 7.7}  # PCM1840 at 48 kHz, 1/fs: SBAS989 Table 12 / Table 18 (MD0=1)
DAC_GD_FS = {"normal": 22.0, "low": 3.5}  # PCM5102A, 1/fs: SLAS859C Table 4 (FLT=0) / Table 7 (FLT=1)


def air_us(payload_b):
    """One copy on air, AIR-2 BLE 2M layout: preamble 2 + AA 4 + S0 1 + LEN 1 + payload + CRC 3 (sched.c AIR_US)."""
    return (2 + 4 + 1 + 1 + payload_b + 3) * 4


def sys2_stages(payload_b=V1_LEN, td_frames=0, frame_us=1000, t_gap=100, out_slot=200, dac_block=8,
                adc_gd=ADC_GD_FS["low"], dac_gd=DAC_GD_FS["normal"], ramp=41, enc_ipc=FCLK_TO_TXEN_US, payload_b_copy_b=None):
    """SYS-2 per stage (us). The sim part (encode + IPC .. output slot) is what run.py (a) measures."""
    return {
        "ADC decimation filter": adc_gd / FS_HZ * 1e6,
        "frame accumulation": frame_us,
        "frame clock -> TXEN (encode + IPC, latch)": enc_ipc,
        "TX ramp-up (copy A)": ramp,
        "copy A on air": air_us(payload_b),
        "T_GAP (incl. copy B ramp)": t_gap,
        "copy B on air": air_us(payload_b if payload_b_copy_b is None else payload_b_copy_b),
        "output slot (decode + jitter, ADR-0013)": out_slot,
        "DAC DMA block": dac_block / FS_HZ * 1e6,
        "DAC interpolation filter": dac_gd / FS_HZ * 1e6,
        "time diversity (played after packet n+d)": td_frames * frame_us,
    }


SIM_STAGES = ("frame clock -> TXEN (encode + IPC, latch)", "TX ramp-up (copy A)", "copy A on air", "T_GAP (incl. copy B ramp)", "copy B on air",
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
    print(f"  {'stage':<48}{'TD off':>8}{'TD on':>8}")
    for k in off:
        print(f"  {k:<48}{off[k]:8.0f}{on[k]:8.0f}")
    t_off, t_on = sum(off.values()), sum(on.values())
    print(f"  {'TOTAL':<46}{t_off:8.0f}{t_on:8.0f}   (target {SYS2_TARGET_US}, hard {SYS2_HARD_US})")
    for n in SIM_A_MEASURED_US:  # the model reproduces the bsim (a) measurement
        sim = sum(sys2_stages(payload_b=n)[k] for k in SIM_STAGES)
        assert abs(sim - SIM_A_MEASURED_US[n]) <= 5, f"{n} B: model {sim:.0f} vs bsim {SIM_A_MEASURED_US[n]} us"
    for n in SIM_A_26_US:  # and the #26 one, with its flat 100 us
        sim = sum(sys2_stages(payload_b=n, enc_ipc=100)[k] for k in SIM_STAGES)
        assert abs(sim - SIM_A_26_US[n]) <= 5, f"{n} B: model {sim:.0f} vs bsim #26 {SIM_A_26_US[n]} us"
    print(f"  frame clock -> TXEN {FCLK_TO_TXEN_US} us = frame lead {FRAME_LEAD_US} + latch {LATCH_LEAD_US} (#98);"
          f" bsim (a) {SIM_A_MEASURED_US[V1_LEN]} / {SIM_A_MEASURED_US[TD_LEN]} us (TD off / on)")
    assert air_us(V1_LEN) == 212 and air_us(TD_LEN) == 368

    # run.py (a) projects with the old SPEC lines (ADC 350, DAC 400, DMA 170, accumulation 1000):
    spec_lines = {"ADC": 350, "acc": 1000, "enc": 100, "A": 200, "gap": 100, "B": 200, "slot": 200, "dma": 170, "dac": 400}
    assert sum(spec_lines.values()) == SPEC_V1_US
    rp_off = SIM_A_26_US[V1_LEN] + 1920
    rp_on = SIM_A_26_US[TD_LEN] + 1920 + 2000
    r42, r81 = SIM_A_26_US[V1_LEN] - 865, SIM_A_26_US[TD_LEN] - 1177
    print(f"  #26 run.py (a) projection: TD off {rp_off} us, TD on {rp_on} us; SPEC said 2600 / 4600")
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
    assert res["DAC FLT=1 + DMA block 4"][0] <= SYS2_TD_DESIGN_US - 80
    assert res["partial TD: td_audio ADPCM-3 (63 B)"][0] > SYS2_TD_DESIGN_US, "partial TD alone does not reach 4.6"
    assert res["PCM1840 linear phase instead (MD0=0)"][0] > SYS2_HARD_US, "keep MD0=1 (ADR-0012)"
    assert res["DAC FLT=1 + partial TD 63 B"][0] <= SYS2_TD_DESIGN_US - 140
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
    T = -wg.MARGIN_DB                         # twin threshold, in "dB over the design margin" units

    def worst_all(v, ins):
        """Wi-Fi-only worst, then near-far with the hot pack anywhere (boom or stage), then two hot packs (mirror)."""
        return (wg.summary(wg.evaluate(v, ins)), wg.near_far_any(v, ins, k_hot=40)["worst"],
                wg.near_far_any(v, ins, both=True, k_hot=12)["worst"], wg.near_far_both(v, ins)["worst"])

    naive = wg.Install(crew_ap_m=99.0)        # mid-wing, 2 m, straight across
    for v in wg.VENUES:
        sn, an, bn, _ = worst_all(v, naive)
        sr, ar, br, wr = worst_all(v, wg.RULE)
        sc = wg.summary(wg.evaluate(v, _repl(wg.RULE, crew_ap_m=3.0)))
        print(f"  {v.name:<16} naive (mid-wing, 2 m, across): Wi-Fi worst {sn['worst_margin']:+.1f}, near-far {an:+.1f},"
              f" both sides {bn:+.1f} dB | ADR-0021 rule: {sr['pass_sel']:5.1%} of the stage with the full margin,"
              f" worst Wi-Fi {sr['worst_margin']:+.1f}, near-far {ar:+.1f}, both sides {br:+.1f}, both booms {wr:+.1f}"
              f" | rule but crew Wi-Fi 3 m away: {sc['worst_margin']:+.1f}")
        assert bn < T, "the naive wing mount fails with actors on both sides (why the rule exists)"
        assert min(sr["worst_best"], ar, br, wr) >= T + 1.4, "rule: >= 1.4 dB over the twin threshold, all cases"
        assert sr["pass_sel"] >= 0.9
        assert sc["worst_margin"] < T, "crew Wi-Fi in the wings breaks it: the rule bans it"
    floor = {z: min(min(x if isinstance(x, float) else x["worst_best"] for x in worst_all(v, _repl(wg.RULE, z=z)))
                    for v in wg.VENUES) for z in (3.2, 3.5)}
    lo = min(min(x if isinstance(x, float) else x["worst_best"] for x in worst_all(v, wg.RULE_LO)) for v in wg.VENUES)
    q, n_l, _ = wg.near(wg.STUDIO, wg.RULE)
    print(f"  boom height: 3.2 m {floor[3.2]:+.1f}, 3.5 m {floor[3.5]:+.1f}, 2 m stand {lo:+.1f} dB (floor 3.5 m). An actor"
          f" at the 4 m boom's foot is {wg.dist(wg.antennas(wg.STUDIO, wg.RULE)[0][1], q):.1f} m away, {n_l:.1f} dBm")
    assert floor[3.5] > T > floor[3.2] and lo < T
    for o in (wg.OMNI3,):
        w = min(wg.summary(wg.evaluate(v, _repl(wg.RULE, ant=o)))["worst_margin"] for v in wg.VENUES)
        print(f"  omni 3 dBi in the wings instead: worst {w:+.1f} dB (sees the audience as well as the stage)")
        assert w < T

    print("  rack chain (PR #95 chain at 01570d9; no coax for levels, 6 dB coax + band edge for NF; every stage's total"
          " input >= 6 dB under its worst P1dB, nRF5340 PIMD scaled as PR #95):")
    s_min = min(wg.summary(wg.evaluate(v, wg.RULE))["s_min"] for v in wg.VENUES)
    weak = s_min - 10.0 - 10.0                            # weakest wing pack, body 10 dB + fade 10 dB (as Audit 6)
    nf_need = wg.nf_needed_db(weak)
    print(f"    NF the wings need: weakest pack {s_min:.1f} dBm free space, {weak:.1f} with body + fade -> NF <= {nf_need:.1f}"
          f" dB costs <= 0.5 dB of the R1 margin (RK-5's 9.30 dB was Audit 4's 10 m assumption, not an R1 need)")
    assert 18 <= nf_need <= 24

    def levels(v, eirp=wg.EIRP_UK, on_axis=False):
        e = wg.evaluate(v, wg.RULE)
        _, n_l, _ = wg.near(v, wg.RULE, 0.5, eirp, on_axis)
        w, ph = e.iw["L"][0], wg.phone_dbm(v, wg.RULE)
        return wg.dbm_sum(n_l, w, w, w, ph), [n_l, w, w, w, ph]

    opts = {"(c) rule, BT40NE, no pad": ("BT40NE", 0.0), "(c) + fixed 10 dB pad, BT40NE": ("BT40NE", 10.0),
            "(c) + switched 0/20 dB pad, BT40NE (studio Wi-Fi alone keeps it at 20)": ("BT40NE", 20.0),
            "(c) + (b) BT40E receivers, no pad (chosen)": ("BT40E", 0.0)}
    res = {}
    for name, (mod, pad) in opts.items():
        nf = wg.system_nf_db(6.0, pad, mod)
        cost = wg.noise_cost_db(nf, weak)
        head = min(min(min(wg.chain_margins(levels(v)[0], 0.0, pad, module=mod)),
                       wg.imd_margin_db(levels(v)[1], weak, 0.0, pad, mod)) for v in wg.VENUES)
        tot_ax, sig_ax = levels(wg.STUDIO, on_axis=True)
        off = min(min(wg.chain_margins(tot_ax, 0.0, pad, module=mod)), wg.imd_margin_db(sig_ax, weak, 0.0, pad, mod))
        comp_ax = min(wg.chain_margins(tot_ax, 0.0, pad, module=mod))
        us = min(min(wg.chain_margins(levels(v, wg.EIRP_US)[0], 0.0, pad, module=mod)) for v in wg.VENUES)
        usd = 8 * (wg.MODULES[mod]["usd"] - wg.MODULES["BT40NE"]["usd"])
        res[name] = (nf, cost, head, comp_ax, off, us)
        print(f"    {name:<74} NF {nf:5.2f} dB (R1 cost {cost:.2f} dB) | rule: worst headroom {head:+5.1f} dB, US"
              f" {us:+5.1f} | off-rule 0.5 m on axis: compression {comp_ax:+5.1f}, incl. PIMD {off:+5.1f} | modules"
              f" {usd:+.0f} USD/rack")
    ch = res["(c) + (b) BT40E receivers, no pad (chosen)"]
    assert ch[0] <= nf_need and ch[2] >= 0 and ch[5] >= 0, "BT40E + rule: NF inside the wing need, nothing compresses"
    assert ch[3] >= 0, "BT40E: even a pack 0.5 m on axis does not compress any stage (PIMD aside)"
    assert res["(c) rule, BT40NE, no pad"][2] < 0, "BT40NE with no pad: studio Wi-Fi + phone crowd the nRF21540"
    assert res["(c) + fixed 10 dB pad, BT40NE"][3] < 0 <= res["(c) + fixed 10 dB pad, BT40NE"][2]
    assert res["(c) + switched 0/20 dB pad, BT40NE (studio Wi-Fi alone keeps it at 20)"][0] > nf_need
    _, n_l, _ = wg.near(wg.STUDIO, wg.RULE)
    print(f"    near pack under the rule: {n_l:.1f} dBm = {wg.on_axis_equiv_m(n_l, wg.EIRP_UK):.1f} m on axis (PR #95"
          f" option c); BT40E rx-only is enough: the receiver never transmits in v1 (ADR-0004)")
    # bsim (c), run.py --geometry docs/analysis/r1-wing/<case>.json --eirp 9 --plan host/channel_plan_us.yaml,
    # 20 s per run. Packs passing SYS-3 (<= 0.1 %, <= 2 in a row) of the 7 with a gap carrier below 2480 (pack 1's
    # is 2482: credited by equivalence, ADR-0016). Filled from the 2026-11-01 runs; see the analysis doc.
    # bsim (c), 2026-11-01: run.py --geometry docs/analysis/r1-wing/<case>.json --eirp 9 --plan
    # host/channel_plan_us.yaml --busy 10,40 --c-secs 20, RX-5 replayed with the fw/src/rx/Kconfig defaults (probe 1000,
    # miss switch 12 dB, hold 1000). Packs 2-8 passing SYS-3 (<= 0.1 %, <= 2 in a row) at 10 / 40 % Wi-Fi, TD off / on,
    # and the worst pack's TD-off loss at 40 %. Pack 1 (2482) is credited by equivalence (ADR-0016).
    WING_BSIM = {
        "studio-rule": (7, 7, 7, 7, 0.000), "prosc10-rule": (7, 7, 7, 7, 0.005), "prosc12-rule": (7, 7, 7, 7, 0.005),
        "prosc12-near2": (7, 7, 7, 7, 0.000), "prosc12-both": (7, 7, 7, 7, 0.015), "studio-both": (7, 7, 7, 7, 0.005),
        "prosc12-any": (7, 7, 7, 7, 0.086), "prosc12-any-both": (7, 7, 7, 7, 0.066),
        "studio-any-both": (7, 7, 7, 7, 0.000), "prosc10-any-both": (7, 7, 7, 7, 0.025),
        "prosc12-onaxis (off-rule, 40 % only)": (None, None, 7, 7, 0.051),
        "studio-onaxis (off-rule, 40 % only)": (None, None, 7, 7, 0.051),
    }
    for case, r in WING_BSIM.items():
        print(f"  bsim {case:<38} 10 % off/on {r[0]}/{r[1]}, 40 % off/on {r[2]}/{r[3]} of 7; worst 40 % TD off {r[4]:.3f} %")
    assert all(x == 7 for r in WING_BSIM.values() for x in r[:4] if x is not None), "R1: 7/7 + pack 1 everywhere"
    assert max(r[4] for r in WING_BSIM.values()) < 0.1, "SYS-3 with TD off (the shipping default, ADR-0017)"


# ---- Audit 6: rack RF chain, gain plan and backplane BOM (#33, ADR-0018). hw/rack/backplane.py, wilkinson.py ----
# Antenna connector -> coax -> BNC/ESD/bias-T/DC block -> QPL9057 LNA -> QPQ1907 BAW -> 1:8 Wilkinson ->
# u.FL cable -> sub-board (DC block, PE4259, u.FL jumper) -> BT40E (no FEM, ADR-0021) -> nRF5340.
# Sources (numbers below carry their row):
#   QPL9057 datasheet Rev. F (2020-09-20): S-parameters at the device pins (|S21| 14.058 at 2.4 GHz = 22.96 dB);
#     EVB typ 1800/2600 MHz: NF 0.50/0.47, OP1dB 17.1, OIP3 33.8/37.8; spec table, tested at 3.5 GHz ONLY (used here
#     as the worst-case proxy at 2.4 GHz): gain >= 21.5, NF <= 0.90, OP1dB >= 14.5, OIP3 >= 29. Abs max +27 dBm.
#   QPQ1907 Data Sheet 040820: pins 1 INPUT, 2/3/5 GND, 4 OUTPUT; IL max 2.2 (CH1 2402.5-2421.5), 1.3 (CH3-11
#     2412.5-2471.5), 1.5 (CH12), 2.2 (CH13 2462.5-2481.5) dB; attenuation min 34 (925-960, 1559-1606), 44
#     (2110-2170), 38 (2300-2370), 30/10 (2500-2505 hot/cold), 43/40 (2505-2570), 48 (2570-2690), 37 (4800-5000).
#     NOT specified: below 2402.5 and above 2481.5 MHz in-band, 2370-2400, 1606-2110, 2690-4800 MHz.
#   nRF21540 OPS v0.5.2 (2019-12-12, objective, the only released figure found): RX gain 13 dB, input P1dB -18.0 min /
#     -13.5 typ. Current PB: NF 2.7 dB. Nordic nRF21540 webinar (2022): "no bypass mode support", so in RX the
#     nRF21540 LNA is always in the path.
#   nRF5340 PS v1.1 (4406_640) 7.26.16.5-7: PRX,MAX 0 dBm; PSENS 2M BLE -95 dBm (<= 37 B); RX selectivity (wanted
#     -67 dBm, equal modulation) C/I 2M BLE: co 7.1, -2 MHz -2, +2 -11, -4 -22, +4 -47, >=6 MHz -54, image -22 dB;
#     PIMD,5TH,2M,BLE -22 dBm (wanted -64 dBm, two equal interferers). No out-of-band blocking figure is given.
# Geometry: owner constraint 2026-11-01: rack antennas in the wings; actors pass the panel, so the worst near pack
#   is at 0.5 m (UK 9 dBm EIRP; US 20 dBm printed). Short coax in the wings is the worst case for levels (CONN_DB).
#   Wi-Fi at the ADR-0016 rule distance; one crew phone (3GPP class 3, 23 dBm) 2 m in front of the panel per band.
LNA_S21_DB = {1700: 21.40, 1900: 21.71, 2000: 21.91, 2300: 22.68, 2400: 22.96, 2500: 23.24, 2600: 23.52,
              3500: 22.86}          # 20 log10 |S21|, datasheet table (device pins, 5 V, 50 mA)
LNA = {"part": "Qorvo QPL9057", "g_nf": 21.5, "nf_max": 0.90, "nf_typ": 0.48, "op1db_min": 14.5, "oip3_min": 29.0,
       "pin_abs_max_dbm": 27.0}
F_RX_MHZ = 2441.75
CARRIERS = (2403.0, 2441.75, 2482.0)   # UK plan band-edge carriers (ADR-0016) and the centre
FRONT_END_DB = 0.4       # est.: BNC 0.1, ESD103 + ESD101 0.05, bias-T choke shunt 0.05, DC block 0.05, 10 mm line 0.15
BAW_SKIRT_EST_DB = 2.0   # est.: extra loss of a carrier whose 2 MHz extends past the specified IL band (S2P not read)
BAW_IL = ((2402.5, 2421.5, 2.2), (2412.5, 2471.5, 1.3), (2457.5, 2476.5, 1.5), (2462.5, 2481.5, 2.2))
BAW_REJ = ((925, 960, 34), (1559, 1606, 34), (2110, 2170, 44), (2300, 2370, 38), (2505, 2570, 40), (2570, 2690, 48),
           (4800, 5000, 37))     # 2505-2570: the cold (-20..25 C) 40 dB row
WILK_LAYOUT_DB = 0.5     # est. until hw/rack/out/rf_routed.json exists (#34: the tree as routed, scikit-rf), see wilkinson_db()
UFL_CABLE_DB = 0.5       # #34: 100 mm 1.13 mm jumper, Taoglas 3.1 dB/m at 2.4 GHz -> 0.31 dB + two mated u.FL pairs
SUBBOARD_DB = 0.9        # ADR-0014: PE4259 0.5 dB, u.FL jumper ~0.3 dB, three 10 pF blocks ~0.1 dB
NRF21540 = {"g": 13.0, "nf": 2.7, "ip1db_min": -18.0}   # BT40NE FEM, for reference (ADR-0021 dropped it on rx)
RX_MODULES = {"BT40E": {"g": -0.3, "nf": 0.3, "ip1db_min": None},   # u.FL straight to the nRF5340 (est. 0.3 dB)
              "BT40NE": NRF21540}
RX_MODULE = "BT40E"      # ADR-0021: receivers on the BT40E, no pad
NRF5340 = {"nf": 7.0, "prx_max": 0.0, "sens_2m": -95.0, "ci_test_wanted": -67.0, "pimd": -22.0, "pimd_wanted": -64.0,
           "ci": {0: 7.1, -2: -2.0, 2: -11.0, -4: -22.0, 4: -47.0, 6: -54.0}}   # NRF5340["nf"] est. (Audit 3)
BACKOFF_DB = 6.0         # "does not compress": every stage's total input >= 6 dB below its worst-case input P1dB
COAX_BUDGET_DB = RK2_COAX_DB
COAX_ADR16_DB = round(wing_coax_db(22.86), 2)   # #34: the far-wing CA3N075 run (worst wing), see Audit 5
AUDIT4_SYS_NF_DB = cascade_nf_db([(-6, 6), (20, 2), (-10.5, 10.5), (0, 7)])   # 9.30 dB: Audit 4 / RK-5
UE_DBM = 23.0
UE_BANDS = {"B40 2390": (2390.0, PATCH_DBI), "B7 UL 2535": (2535.0, PATCH_DBI), "B1 UL 1950": (1950.0, 0.0),
            "B3 UL 1747": (1747.0, 0.0), "n78 3500": (3500.0, 0.0)}   # patch gain out of 2.3-2.6 GHz: 0 dBi est.
NEAR_M = (0.5, 1.0, 1.5)


def fspl_db(d_m, f_mhz=F_RX_MHZ):
    return 20 * math.log10(d_m) + 20 * math.log10(f_mhz) - 27.55


def dbm_sum(*p):
    return 10 * math.log10(sum(10 ** (x / 10) for x in p))


def lna_gain_db(f_mhz):
    """QPL9057 |S21| (datasheet table) interpolated; the level calculations use it (higher than the 21.5 dB proxy)."""
    ks = sorted(LNA_S21_DB)
    f = min(max(f_mhz, ks[0]), ks[-1])
    lo = max(k for k in ks if k <= f); hi = min(k for k in ks if k >= f)
    return LNA_S21_DB[lo] if hi == lo else LNA_S21_DB[lo] + (LNA_S21_DB[hi] - LNA_S21_DB[lo]) * (f - lo) / (hi - lo)


def lna_at(f_mhz=F_RX_MHZ):
    g = lna_gain_db(f_mhz)
    return {"gain": g, "nf": LNA["nf_typ"], "nf_max": LNA["nf_max"], "iip3_min": LNA["oip3_min"] - g,
            "ip1db_min": LNA["op1db_min"] - g + 1}


def baw_db(f_mhz):
    """QPQ1907 loss at a carrier (2 MHz wide) or a blocker: the worst specified IL row covering [f-1, f+1]; a carrier
    reaching past 2402.5 / 2481.5 MHz gets BAW_SKIRT_EST_DB more; out of band, the stated attenuation or 0 if none."""
    if 2400 <= f_mhz <= 2483.5:
        rows = [il for lo, hi, il in BAW_IL if lo <= f_mhz <= hi]
        out = f_mhz - 1 < BAW_IL[0][0] or f_mhz + 1 > BAW_IL[-1][1]
        return max(rows or [2.2]) + (BAW_SKIRT_EST_DB if out else 0.0)
    return next((rej for lo, hi, rej in BAW_REJ if lo <= f_mhz <= hi), 0.0)


def wilkinson_db():
    """1:8 worst-case insertion loss over the band, port to port as routed (hw/rack/out/rf_routed.json: the drawn tree,
    its 50 ohm distribution lines, bends, junctions, resistor parasitics and the port net ties, scikit-rf; #34), or the
    hw/rack/wilkinson.py model + the layout allowance when that record is missing."""
    import importlib.util, json
    rec = pathlib.Path(__file__).resolve().parent / "hw/rack/out/rf_routed.json"
    if rec.exists():
        return json.loads(rec.read_text())["worst"]["il_db"]
    spec = importlib.util.spec_from_file_location("wk", pathlib.Path(__file__).resolve().parent / "hw/rack/wilkinson.py")
    wk = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(wk)
    return wk.summary(5)["il_db"] + WILK_LAYOUT_DB


def rack_chain(coax_db, f_mhz=F_RX_MHZ, module=RX_MODULE, splitter_db=None):
    """[(gain dB, NF dB), ...] from the antenna connector to the nRF5340, worst case (21.5 dB / 0.9 dB proxy)."""
    splitter_db = wilkinson_db() if splitter_db is None else splitter_db
    lossy = lambda d: (-d, d)
    m = RX_MODULES[module]
    return [lossy(coax_db), lossy(FRONT_END_DB), (LNA["g_nf"], LNA["nf_max"]), lossy(baw_db(f_mhz)),
            lossy(splitter_db), lossy(UFL_CABLE_DB), lossy(SUBBOARD_DB), (m["g"], m["nf"]), (0.0, NRF5340["nf"])]


def worst_nf(coax_db, module=RX_MODULE, wil=None):
    return max(cascade_nf_db(rack_chain(coax_db, f, module, wil)) for f in CARRIERS)


import sys  # noqa: E402  (Audit 7's _wing() registers its module in sys.modules; it is imported only under __main__)


def nf_need_wings_db():
    """ADR-0021 / Audit 7: the largest system NF whose noise costs <= 0.5 dB of the R1 margin for the weakest pack
    under the wing rule (free-space minimum over the three venues, minus 10 dB body and 10 dB fade)."""
    wg = _wing()
    s_min = min(wg.summary(wg.evaluate(v, wg.RULE))["s_min"] for v in wg.VENUES)
    return wg.nf_needed_db(s_min - 10.0 - 10.0)


def signals_at_lna(d_near, eirp=None, ue_m=None):
    """[(name, f MHz, dBm at the LNA input, in-band?)]: the near pack ON AXIS (worst; ADR-0021's rule puts it well
    off axis), Wi-Fi 1/6/11 at the ADR-0021 6 m backstage distance in the main beam (worst), and (if ue_m) one class-3
    phone per UK uplink band at ue_m in front of the panel."""
    eirp = REGIONS["UK"]["eirp_dbm"] if eirp is None else eirp
    s = [("near pack", 2426.0, eirp - fspl_db(d_near) + PATCH_DBI - CONN_DB, True)]
    wifi = 20.0 - fspl_db(6.0) + PATCH_DBI - CONN_DB
    s += [(f"Wi-Fi {c}", w, wifi, True) for c, w in ((1, 2412.0), (6, 2437.0), (11, 2462.0))]
    if ue_m:
        s += [(f"UE {b}", f, UE_DBM - fspl_db(ue_m, f) + g - CONN_DB, False) for b, (f, g) in UE_BANDS.items()]
    return s


def wanted_at_lna():
    """Weakest pack R1 must carry: UK 9 dBm at 10 m, body 10 dB, fade 10 dB (as r1_noise_cost_db), short coax."""
    return REGIONS["UK"]["eirp_dbm"] - (40.2 + 20) + PATCH_DBI - 10.0 - 10.0 - CONN_DB


def gain_plan(d_near, module=RX_MODULE, wil=None, eirp=None, ue_m=None):
    """Stage-by-stage headroom (dB, >= 0 passes): rack LNA, module LNA (none on a BT40E), nRF5340 PRX,MAX, PIMD."""
    wil = wilkinson_db() if wil is None else wil
    m = RX_MODULES[module]
    post = lambda f: -baw_db(f) - wil - UFL_CABLE_DB - SUBBOARD_DB     # LNA output -> module input
    sig = signals_at_lna(d_near, eirp, ue_m)
    lna_in = dbm_sum(*[p for _, _, p, _ in sig])
    lna = lna_at()
    mod = [(n, f, p + lna_gain_db(f) + post(f)) for n, f, p, _ in sig]
    mod_in = dbm_sum(*[p for _, _, p in mod])
    radio = sorted(((p + m["g"], n) for n, _, p in mod), reverse=True)
    total = dbm_sum(*[p for p, _ in radio])
    w = wanted_at_lna() + lna_gain_db(F_RX_MHZ) + post(F_RX_MHZ) + m["g"]
    a, b = radio[0][0], radio[1][0]
    im_allowed = NRF5340["pimd"] + (w - NRF5340["pimd_wanted"]) / 3      # 3rd order: IMD rises 3 dB per dB
    near = next(p for p, n in radio if n == "near pack")
    return {"lna_in": lna_in, "lna_margin": lna["ip1db_min"] - BACKOFF_DB - lna_in, "fem_in": mod_in,
            "fem_margin": math.inf if m["ip1db_min"] is None else m["ip1db_min"] - BACKOFF_DB - mod_in,
            "radio_total": total, "radio_margin": NRF5340["prx_max"] - BACKOFF_DB - total,
            "imd_margin": 3 * im_allowed - (2 * a + b),
            "wanted_radio": w, "near_radio": near, "strongest": radio[0][1],
            "ci_6mhz_margin": -NRF5340["ci"][6] - (near - w), "ci_4mhz_margin": -NRF5340["ci"][-4] - (near - w)}


def compression_margin(g):
    return min(g["lna_margin"], g["fem_margin"], g["radio_margin"])


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
    print("\n== Audit 6: rack RF chain (#33, ADR-0018/0021): antenna -> coax -> LNA -> BAW -> 1:8 Wilkinson -> BT40E ==")
    lna = lna_at()
    print(f"  {LNA['part']} at {F_RX_MHZ:.0f} MHz: |S21| {lna['gain']:.1f} dB (21.5 min, 3.5 GHz proxy, for NF),"
          f" NF {lna['nf']:.2f} typ / {lna['nf_max']:.2f} max, IIP3 >= {lna['iip3_min']:+.1f} dBm,"
          f" input P1dB >= {lna['ip1db_min']:+.1f} dBm (OIP3/OP1dB minima over |S21|)")
    assert lna["nf_max"] <= 2.0, "RK-2: LNA NF <= 2 dB"
    assert lna["ip1db_min"] >= -10 and lna["iip3_min"] >= 0, "RK-2: input P1dB >= -10 dBm, IIP3 >= 0 dBm"
    wil = wilkinson_db()
    print(f"  1:8 Wilkinson as routed {wil:.2f} dB worst port (hw/rack/out/rf_routed.json); QPQ1907 at the carriers: "
          + ", ".join(f"{f:.0f} {baw_db(f):.1f} dB" for f in CARRIERS)
          + f" (2403/2482 reach past the specified 2402.5-2481.5 MHz: +{BAW_SKIRT_EST_DB} dB est.)")
    nf_need = nf_need_wings_db()
    print(f"  system NF at the antenna connector, receivers on the {RX_MODULE} (ADR-0021), worst-case LNA, by carrier"
          f" (RK-5: <= {nf_need:.1f} dB, the wing need from Audit 7):")
    for coax in (COAX_ADR16_DB, COAX_BUDGET_DB):
        nfs = [cascade_nf_db(rack_chain(coax, f, RX_MODULE, wil)) for f in CARRIERS]
        print(f"    coax {coax} dB: " + ", ".join(f"{f:.0f}: {n:.2f}" for f, n in zip(CARRIERS, nfs)) + " dB")
    nf_worst = worst_nf(COAX_BUDGET_DB, RX_MODULE, wil)
    assert nf_worst <= nf_need, "RK-5: every carrier, band edges with the skirt allowance, inside the wing NF need"
    print(f"    -> worst {nf_worst:.2f} dB at the 6 dB budget, {nf_need - nf_worst:.1f} dB inside the need"
          f" (BT40NE would give {worst_nf(COAX_BUDGET_DB, 'BT40NE', wil):.2f} dB, but its FEM compresses: ADR-0021)")

    print(f"  stage headroom, near pack UK 9 dBm ON AXIS (worst; the rule keeps it off axis), Wi-Fi x3 at 6 m in the"
          f" beam; margins vs P1dB - {BACKOFF_DB:.0f} dB, PRX,MAX - {BACKOFF_DB:.0f} dB, PIMD scaled to the wanted:")
    for d in NEAR_M + (4.0,):
        g = gain_plan(d, RX_MODULE, wil)
        print(f"    {d:>3} m: LNA in {g['lna_in']:6.1f} dBm ({g['lna_margin']:+5.1f}); radio {g['radio_total']:6.1f}"
              f" ({g['radio_margin']:+5.1f}); PIMD {g['imd_margin']:+6.1f}; near/wanted"
              f" {g['near_radio'] - g['wanted_radio']:4.1f} dB -> C/I margin >= 6 MHz {g['ci_6mhz_margin']:+5.1f},"
              f" -4 MHz {g['ci_4mhz_margin']:+5.1f}")
        assert compression_margin(g) >= 0, f"no stage compresses with a pack {d} m on axis (BT40E, no pad)"
    for d in (1.5, 4.0):
        assert gain_plan(d, RX_MODULE, wil)["imd_margin"] >= 0, "PIMD holds once the pack is >= 1.5 m on axis"
    bt40ne = gain_plan(NEAR_M[0], "BT40NE", wil)
    print(f"    BT40NE instead (nRF21540 always on): module margin {bt40ne['fem_margin']:+.1f} dB at 0.5 m -> why"
          f" ADR-0021 moved the receivers to the BT40E")
    assert bt40ne["fem_margin"] < 0
    ue = gain_plan(10.0, RX_MODULE, wil, ue_m=2.0)
    ue_lna_m = next(i / 10 for i in range(1, 400) if gain_plan(10.0, RX_MODULE, wil, ue_m=i / 10)["lna_margin"] >= 0)
    print(f"  class-3 phones (B40 2390, B7, B1, B3, n78) 2 m in front of a panel: LNA {ue['lna_margin']:+.1f} dB, radio"
          f" {ue['radio_margin']:+.1f} dB (B40 2370-2400 unfiltered ahead of the LNA): phones keep >= {ue_lna_m:.1f} m,"
          f" which ADR-0021's crew-airplane-mode rule covers in the wings; the audience phone case is in Audit 7")
    assert 2.0 < ue_lna_m <= 3.0


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
          f" (converted, hw/rx/out/bom.csv); antennas, coax, stands GBP {rp.ANTENNA_KIT_GBP:.2f} (hw/rack/prices.py ANTENNA_KIT)"
          f" -> rack GBP {tot:.2f} ex VAT. No cap in SPEC/AUDIT, so none asserted")
    assert all(r["uk_distributor"] and r["source"] for r in rk), "every rack BOM line needs a UK distributor and source"
