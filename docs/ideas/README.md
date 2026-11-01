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

## Seed list (extend freely)

- TDMA on commodity 2 Mbps / 4 Mbps GFSK radios with a 4–8 radio hub (nRF52840 / nRF54L15), beacon downlink.
- Adaptive frequency hopping at 20 dBm EIRP, one copy per frame plus a delayed repair copy.
- 1785–1805 MHz (UK licence-exempt since April 2026) using a 2.4 GHz radio and a mixer, or an SDR receiver.
- One wideband SDR receiver demodulating every pack at once (channeliser on a mini-PC or FPGA).
- DECT-2020 NR+ on nRF9151 with a self-written MAC.
- Packs that relay for each other (mesh) so a blocked pack is still heard.
- Two cheap radios per pack on two bands at once.
- Ultra-cheap nRF24L01+ class links (£1 radios) with heavy redundancy.
- Anything else extreme enough to be worth a page.
