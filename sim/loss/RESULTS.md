# sim/loss results (issue #14, evidence for ADR-0001)

Reproduce: `python3 sim/loss/traces.py` (about 2 s, fixed seed). Model: `audit.burst_loss` Gilbert-Elliott defaults
(mean burst 2 frames, p_bad 0.9, p_good 0.001), two independent channels, 3.6 M frames = 1 h.
Frame lost = both copies lost; time diversity (TD) also needs packet n+2 to fail (both copies).
Events/h = runs of >= 3 lost frames (ADR-0003 dropout).

## 1. Normal pack: copy A in a gap carrier, copy B under Wi-Fi (ADR-0002)

Per-copy busy fractions (`trace(busy_a, busy_b)`), cells are `residual %/max run/events/h`, PASS = ADR-0003
(residual <= 0.1 %, max run <= 2, <= 1 event/h). Above 50 % busy the GE burst length grows (mean 1/b2g > 2
frames) so time-in-bad still equals the busy fraction. Gap busy values are **estimates** (section 3), not measurements.

| gap busy A | in-band busy B | TD off (resid %/max run/events/h) | TD on |
|---|---|---|---|
| 0.1% | 10% | 0.018/4/11 fail | 0.000/2/0 PASS |
| 0.1% | 40% | 0.071/5/49 fail | 0.003/3/2 fail |
| 0.1% | 70% | 0.120/5/78 fail | 0.009/3/4 fail |
| 0.1% | 90% | 0.152/9/233 fail | 0.014/7/33 fail |
| 0.2% | 10% | 0.026/5/18 fail | 0.001/3/1 fail |
| 0.2% | 40% | 0.104/6/81 fail | 0.006/4/3 fail |
| 0.2% | 70% | 0.183/6/175 fail | 0.019/4/8 fail |
| 0.2% | 90% | 0.226/8/449 fail | 0.027/6/54 fail |
| 0.5% | 10% | 0.049/5/55 fail | 0.003/3/3 fail |
| 0.5% | 40% | 0.200/6/208 fail | 0.013/4/6 fail |
| 0.5% | 70% | 0.346/6/440 fail | 0.043/4/26 fail |
| 0.5% | 90% | 0.449/10/1176 fail | 0.070/8/163 fail |
| 1.0% | 10% | 0.092/6/96 fail | 0.005/4/7 fail |
| 1.0% | 40% | 0.361/7/387 fail | 0.029/5/13 fail |
| 1.0% | 70% | 0.631/7/819 fail | 0.088/5/35 fail |
| 1.0% | 90% | 0.823/9/2276 fail | 0.139/7/273 fail |
| 2.0% | 10% | 0.175/7/197 fail | 0.010/5/9 fail |
| 2.0% | 40% | 0.691/10/846 fail | 0.060/8/23 fail |
| 2.0% | 70% | 1.197/8/1701 fail | 0.177/6/91 fail |
| 2.0% | 90% | 1.525/11/4269 fail | 0.267/9/550 fail |
| 5.0% | 10% | 0.408/7/432 fail | 0.023/5/23 fail |
| 5.0% | 40% | 1.666/8/1904 fail | 0.146/6/69 fail |
| 5.0% | 70% | 2.875/8/4238 fail | 0.452/6/239 fail |
| 5.0% | 90% | 3.724/14/10962 fail | 0.706/12/1379 fail |

Reading: TD off never passes. TD on passes only when the gap carrier is essentially clean (<= 0.1 % busy, B at
10 %). With a 0.5-1 % gap busy and heavy Wi-Fi on B, events/h stay 3-270. The ADR-0003 "1 event/h" bar is
tight against bursts that are both frequent and longer than the 2-frame TD offset covers.

## 2. Gap carriers per rack

2 MHz carriers fully outside Wi-Fi 1/6/11 occupied 20 MHz (2402-2422, 2427-2447, 2452-2472), inside 2402-2480,
2 MHz spacing: gaps 2422-2427, 2447-2452, 2472-2480 give 2 + 2 + 4 = **8 gap carriers** (2423, 2425, 2448, 2450,
2473, 2475, 2477, 2479; matches `audit.gap_carriers(20)` = 8 once the band is cut at 2480). AIR-5 puts fA <= 2440
with fB >= fA + 40: only 2423/2425 can be A, but any gap carrier can be B (e.g. A under Wi-Fi 1 for B = 2448).
So **all 8 packs can get exactly one gap carrier**, and the other 8 carriers (one per pack) sit under Wi-Fi.
No pack gets two. Ignores inter-pack adjacent-carrier interference.

## 3. Gap busy estimate (ESTIMATE, not measured)

Geometry (ADR-0003): interferer ~+20 dBm at 2 m, pack ~+20 dBm at 10 m, same antenna: free-space distance
gap 20*log10(10/2) = 14 dB, so the interferer is 14 dB stronger at the receiver.
- Co-channel (carrier under Wi-Fi): interferer power spread over 20 MHz, 2 MHz of it is -10 dB, so I/C = 14 - 10 =
  +4 dB, C/I = -4 dB vs ~10 dB needed for BLE 2M: carrier is lost whenever Wi-Fi transmits (busy = airtime).
- Gap carrier, 802.11 OFDM mask: -20 dBr at +-11 MHz, -28 dBr at +-20 MHz. Nearest gap carriers sit ~11-13 MHz
  from a Wi-Fi centre, so ~ -20 dBr: I/C = 14 - 10 - 20 = -16 dB, C/I = +16 dB, 6 dB margin over 10 dB.
  Farther gap carriers (2473-2479, 17+ MHz) get ~ -25 dBr, more margin.
- So with a spec-compliant mask the gap busy is ~0 (receiver selectivity and fading ignored).
- Sensitivity: mask rejection R needed for C/I >= 10 dB is R >= 14 dB. Real phones often miss the mask: if
  effective R drops below 14 dB (6 dB worse than spec) the gap carrier starts losing frames during Wi-Fi bursts and
  gap busy rises towards the Wi-Fi airtime. From the table: TD on passes only for gap busy <= ~0.1 %, i.e.
  we need the real mask to hold with margin; 0.5 % or more fails even at 10 % in-band busy.

## 4. Worst case: pack with no gap carrier (both copies under Wi-Fi at the same busy)

| busy % | TD off: residual % | max run | events/h | TD on: residual % | max run | events/h |
|---|---|---|---|---|---|---|
| 5% | 0.214 | 6 | 257 | 0.012 | 4 | 11 |
| 10% | 0.828 | 8 | 972 | 0.051 | 6 | 38 |
| 15% | 1.844 | 7 | 2100 | 0.127 | 5 | 87 |
| 20% | 3.265 | 9 | 3776 | 0.257 | 7 | 151 |
| 25% | 5.094 | 8 | 6094 | 0.460 | 6 | 259 |
| 30% | 7.325 | 9 | 8661 | 0.762 | 7 | 337 |
| 35% | 9.977 | 10 | 11763 | 1.199 | 8 | 478 |
| 40% | 12.998 | 9 | 15423 | 1.836 | 7 | 618 |


ADR-0003 limits: residual <= 0.1 %, max run <= 2, <= 1 event/h. This table fails everywhere; it is the
case ADR-0002 avoids by assigning gap carriers first.

## PLC (RX-6) and quality curve

`sim/loss/plc.py`: repeat last good frame for 10 ms, the 11th lost frame fades it 1 -> 0 over 1 ms, then mute.
(Reading of "1 ms linear fade; mute after 10 ms": the fade is the last repeat before the mute.)

`python3 sim/loss/curve.py` runs codec + trace + PLC on two macOS `say` speech clips (48 kHz) and scores with
`sim/quality.visqol` (ViSQOL v3.3.3 audio mode, built locally per sim/codec/RESULTS.md; ~2 min).

### ViSQOL vs busy fraction (worst case: both copies under Wi-Fi at the same busy, §4 traces)

| busy % | adpcm6 +TD | adpcm6 | adpcm8 | bf8_3 |
|---|---|---|---|---|
| 5% | 4.21 | 4.06 | 4.13 | 4.10 |
| 10% | 4.18 | 3.96 | 4.03 | 4.00 |
| 15% | 4.07 | 3.57 | 3.60 | 3.60 |
| 20% | 4.01 | 3.32 | 3.33 | 3.36 |
| 25% | 4.11 | 3.20 | 3.21 | 3.23 |
| 30% | 3.95 | 3.04 | 3.04 | 3.06 |
| 35% | 3.67 | 2.90 | 2.90 | 2.92 |
| 40% | 3.42 | 2.80 | 2.81 | 2.81 |

Reading: with TD, ViSQOL stays ≥ 4.0 (SYS-4) up to ~25 % busy even with no gap carrier; without TD only up to ~10 %.
Codec choice barely matters once loss dominates. Short clips (a few s) make each cell noisy (±0.1); the trend is the evidence for ADR-0001.
