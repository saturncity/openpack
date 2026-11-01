# Radical idea board

Owner's instruction (2026-11-01): "a radical idea board where we try some extreme approaches and then have a different agent evaluate them."

## Rules

- One file per idea: `docs/ideas/NN-<slug>.md`. One author agent per idea; the author does not evaluate it.
- Each idea is written to the same template (below) so the evaluator can compare like with like.
- A **different** agent evaluates every idea against `REQUIREMENTS.md` P1–P12 and writes `docs/ideas/EVALUATION.md`: a scoring table, the cheapest credible architecture, the riskiest assumption in each idea, and which ideas deserve a bench experiment before the architecture is chosen.
- Nothing is rejected for being strange. Ideas are rejected only by the evaluator, with the P-id that kills them.
- Starting points are in the v1 audit §6 (`docs/audit/2026-11-01-v1-audit.md`) and `docs/audit/detail/market.md`.

## Template

```
# NN. <Idea title>

**One sentence.** What it is.

**How the air works.** Band, modulation, bitrate, frames, how 32 mics share it, how a pack joins, how the downlink works.

**How the receiver works.** Radios, antennas, host, outputs. Why it is cheap.

**Capacity maths.** Mics per radio, radios for 32, spectrum used, airtime per mic, headroom for repair copies.

**Latency budget.** Every stage in microseconds, mic-in to USB/analog out. Where the 5 ms goes.

**Reliability story.** What happens under the hostile test (phones, hotspot at 1 m, Wi-Fi ch 6 at 3 m, wireless DMX, Bluetooth). Repair strategy. Failure modes and recovery times.

**Cost.** Pack parts, base station fixed, per channel, 32-channel total. GBP ex VAT, sources.

**UK legality.** Standard, power, duty cycle, anything that must be measured.

**What v1 code or analysis it reuses.**

**Riskiest assumption** and the cheapest experiment (under £200) that tests it.

**Why it might be wrong.** The author's honest case against the idea.
```

## The board (authored 2026-11-01)

All 27 pages were written in one session by one author agent, from head-knowledge only, with no measurements and no web checks; facts marked **[verify]** or **[estimate]** are the author flagging their own uncertainty. Prices are GBP ex VAT, low volume, from memory of 2025-26 pricing. The evaluator checks facts; the author does not.

| # | Idea | Type | Where it comes from |
|---|---|---|---|
| 01 | [TDMA on commodity GFSK radios, beacon downlink](01-tdma-gfsk-hub.md) | air + hub | Shure ULX-D, 6TiSCH/WirelessHART TSCH |
| 02 | [HARQ: resend only what was lost](02-harq-selective-repair.md) | MAC | LTE/5G hybrid ARQ |
| 03 | [ExpressLRS-style FHSS on SX1280 FLRC](03-fhss-expresslrs-flrc.md) | air | open-source drone control links |
| 04 | [Ultra-cheap nRF24L01+ class links](04-nrf24-ultracheap.md) | air + hub | wireless mice/game controllers |
| 05 | [Raw 802.11 at 5 GHz, monitor-mode dongle receiver](05-raw-80211-5ghz.md) | air + hub | Wi-Fi packet injection, ESP-NOW |
| 06 | [Wi-Fi 6 UL-OFDMA on a £30 router](06-wifi6-ul-ofdma-router.md) | air + hub | 802.11ax scheduler |
| 07 | [UWB (DW3000) with free positioning](07-uwb-dw3000.md) | air + band | car keys, AirTag |
| 08 | [DECT-2020 NR+ on nRF9151](08-dect-nr-plus.md) | air + band | industrial DECT NR+ |
| 09 | [Digital in 1785–1805 MHz by frequency translation + one SDR](09-pmse-1785-translated.md) | band + hub | amateur-radio transverters |
| 10 | [Analog FM packs + SDR receiver bank](10-analog-fm-sdr-bank.md) | air + hub | professional analog mics, broadcast-band SDR |
| 11 | [v1's air interface on one SDR](11-v1-air-on-sdr.md) | hub | ice9 BLE sniffer |
| 12 | [RTL-SDR bank behind a 13 cm downconverter](12-rtlsdr-bank-downconverter.md) | hub | amateur satellite receivers |
| 13 | [Home-made direct-IF receiver (AD9226 + open FPGA)](13-homebrew-direct-if-fpga.md) | hub | hobby SDR, open FPGA toolchains |
| 14 | [CDMA uplink](14-cdma-uplink.md) | air | GPS, IS-95 |
| 15 | [No base station: USB dongles + laptop](15-no-base-station-dongles.md) | hub | BLE sniffer dongles |
| 16 | [Distributed receiver pods](16-distributed-receiver-pods.md) | hub | pro antenna distribution, cellular DAS |
| 17 | [One clock: beacon-disciplined sampling, PTP](17-one-clock-ptp-beacon.md) | time protocol (modifier) | IEEE 1588, 802.1AS, AES67 |
| 18 | [Federated hubs, no ceiling](18-federated-hubs-no-ceiling.md) | architecture (modifier) | cellular handover |
| 19 | [CTS-to-self medium reservation](19-cts-to-self-quiet-room.md) | coexistence (modifier) | Bluetooth/Wi-Fi combo chips |
| 20 | [Concealment first](20-concealment-first.md) | signal processing (modifier) | VoIP/NetEQ, LC3 PLC |
| 21 | [Raw-bit modem: own FEC, combining, rate adaptation](21-raw-bit-modem-fec.md) | signal processing (modifier) | DVB/5G coding, soft combining |
| 22 | [Two radios, two bands per pack](22-two-radios-two-bands.md) | air | multi-band Wi-Fi SoCs |
| 23 | [Packs relay for each other](23-pack-mesh-relay.md) | MAC | 3GPP sidelink, 802.11s |
| 24 | [The £12 pack](24-pack-at-12-pounds.md) | pack cost (modifier) | module-only hobby designs |
| 25 | [Diffuse infrared uplink](25-diffuse-infrared-uplink.md) | medium | IR assistive listening, IrDA |
| 26 | [Stage-floor magnetic induction](26-stage-floor-induction.md) | medium | hearing loops, NFMI |
| 27 | [Repurposed hardware: phones, dev boards](27-smartphones-as-packs.md) | build strategy | second-hand phones, XIAO/ESP dev kits |

"Modifier" ideas (17-21, 24) are not architectures on their own; they attach to one of the air/hub ideas and the evaluator should score them as additions.

## Considered and dismissed by the author (one line each, for the evaluator to overturn if wrong)

- **863–865 MHz wireless-audio sub-band (EN 301 357, 10 mW)**: 2 MHz wide; 32 mics at 260 kbps need 8 Mbps; impossible without a codec that breaks P3.
- **868–870 MHz general SRD**: duty-cycle limits (0.1–10 %) and ≤ 500 kHz channels; fine for a control downlink (idea 22B), not for audio.
- **5.8 GHz SRD at 25 mW (EN 300 440)**: no cheap non-Wi-Fi silicon; covered by idea 05 via Wi-Fi.
- **24 GHz / 60 GHz**: body blocking, expensive, no.
- **Bluetooth LE Audio (LC3, CIS/BIS)**: 7.5/10 ms frames; fails P3. Useful later for actors' in-ear monitoring, out of scope.
- **Zigbee/Thread (802.15.4 at 250 kbps)**: slower than one mic's bitrate.
- **LoRa (not FLRC)**: kbps-class.
- **Opus / LC3plus codecs**: ≥ 2.5 ms frame + lookahead; excluded by P3 unless capacity is desperate.
- **MikroTik Nv2 TDMA Wi-Fi**: proprietary, £30+ and watts per client.
- **Dante/AES67 radios**: none exist at this price.
- **Analog in 2.4 GHz**: not permitted by EN 300 328's digital-modulation assumptions in any useful way.
