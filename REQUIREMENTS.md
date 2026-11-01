# OpenPack v2: owner's requirements and ranked priorities

Confirmed by the owner on 2026-11-01 after the v1 audit (`docs/audit/2026-11-01-v1-audit.md`) and a priorities session. **This file is the yardstick.** Every ADR scores its options against this ranking. Only the owner edits this file; agents propose changes as a stop-and-ask.

## Purpose

A wireless microphone system that UK university theatre clubs can build and own. Used first in a black-box theatre with no installed sound system (6–16 mics per show), possibly later in a larger theatre with an Allen & Heath console on Dante. Zero profit intent. Published as an open design: hardware under CERN-OHL-S-2.0, firmware and software under GPL-3.0-or-later.

## Ranked priorities

When two requirements conflict, the higher one wins and the ADR says so.

| Rank | ID | Priority | Measure |
|---|---|---|---|
| **1 (joint)** | **P1** | **Reliability.** A dropout mid-show is the worst failure; it affects hundreds of people. | Bench-measured, never simulated-only: ≤ 1 audible artefact per 2-hour show per mic under the hostile test (a room's worth of phones, a hotspot streaming video 1 m from the pack, Wi-Fi on channel 6 at 3 m, wireless DMX, Bluetooth headsets, other wireless mic systems, LED and dimmer noise). Re-acquire within 0.5 s after walking out of range. Watchdogs on both ends; no lockups; a restart takes ≤ 1 s and never affects other mics. Low-battery warning to the booth 30 minutes ahead. Final gate: a real show night. |
| **1 (joint)** | **P2** | **Cost.** The motive for the project. | Budgets, parts at low volume, GBP ex VAT: pack ≤ £30 excluding the cell; base station ≤ £150 fixed plus ≤ £10 per channel of capacity; 32-channel system ≤ £1,500. These are tripwires, not gates: any change that puts a subsystem more than 25 % over budget, or the system over £1,500, stops work and produces a one-page "do we need this" assessment for the owner (what the money buys, cheaper alternatives). |
| **2** | **P3** | **Latency.** | Hard limit 5 ms mic-in to analog or USB out, measured with a logic analyser. Reliability may spend the budget (a repair copy near 4–4.5 ms is expected). Identical delay on every pack within a show (comb filtering and monitor coherence). |
| **3** | **P4** | **Scalability.** 32 mics in one venue is the reference; ideally no ceiling but the one licensing draws. | Capacity maths (channels per radio, radios per venue, spectrum per band) written down and reviewed before any hardware is chosen. Adding capacity must mean adding cheap radios, not a new base station. |
| **4** | **P5** | **Automatic operation.** | A pack switched on with no configuration joins, is assigned a slot or channel, and appears in the booth UI with no manual action. Requires a downlink from day one. |
| **5** | **P6** | **Booth management.** | A web page served over Ethernet or USB, no install: per-mic battery, signal, level, dropouts; trim and mute from the booth. |
| **6** | **P7** | **Pack usability.** | No controls an actor can touch (recessed power only). Locking 3.5 mm jack, Sennheiser pinout, works with headset and lavalier mics including DPA-class via adapter. Hot-swappable 18650 without tools in < 30 s; 16–20 h runtime; an AA variant must be a case swap, not a redesign. |
| **7** | **P8** | **Audio quality.** Medium: do the best the capacity allows; musicals mean singing. | Default 32 kHz sampling (16 kHz bandwidth, matching professional analog radio mics), 8-bit ADPCM in 1 ms frames (~260 kbps per mic), ViSQOL ≥ 4.3 against the 24-bit original on the v1 corpus (speech, singing, belt, whisper-to-scream). 48 kHz as a per-show option when fewer mics are in use. Codecs adding more than ~1 ms of delay are excluded by P3. No clipping at 0.6 Vrms input; gain is managed at the desk, not on the pack. |
| **8** | **P9** | **Looks.** The pack must look like a real theatre pack. | Sennheiser-EW size (about 65 × 85 × 25 mm), belt clip, no visible screws, textured matte print on the owner's Bambu A1 mini. Renders reviewed by the owner before printing. Off-the-shelf ABS enclosure is the fallback. |
| **9** | **P10** | **Outputs.** | USB Audio Class 2 (up to 32 channels) to a laptop first. Optional plug-in 8-channel analog XLR cards (~£35 in parts each). AES67 output from the base station's Linux host later, at zero licence cost, for the big theatre's A&H Dante card in AES67 mode; no Dante hardware on the base board. Nice-to-have, must not add base-station cost. |
| **10** | **P11** | **Legal in the UK.** The band itself is not a priority. | Designed and documented to the relevant standard (EN 300 328 at 2.4 GHz, EN 300 422 at 1785–1805 MHz, DECT rules at 1880–1900 MHz), verified with a cheap spectrum analyser. No formal certification; anyone who sells units certifies them. |
| **11** | **P12** | **Preferences, not requirements.** | Rack form factor, number of antennas, status LEDs, printing method, which band. None may drive cost or reliability. |

## Venue facts

- Base station backstage, stage left or right, with line of sight to the stage; other layouts may be explored.
- Black box: no installed system; mixed on a laptop today (analog mixers in use, non-Dante digital mixers being considered).
- Big theatre: Allen & Heath console with Dante.
- Interference to anticipate: audience phones, hotspots, venue Wi-Fi, wireless DMX, Bluetooth, other mic systems, LED and dimmer noise. Flag anything that performs badly.

## Prototype exit criteria (phase 1)

1. Two real packs into one receiver hub, both heard at once, latency measured under 5 ms with a logic analyser.
2. Capacity demonstrated by one extra board faking the traffic of 30 more packs, so the hub is seen handling a full 32-slot schedule.
3. The hostile bench test (P1) passing.
4. Automatic join (P5): an unconfigured pack appears in the booth UI and gets a slot by itself.

## Deferred to the architecture review

Receiver sizing for the first full build: one 16-channel unit with radio slots to 32, or stackable 8-channel units. Decided by a cost table.

## Explicitly not wanted

A product for sale. Dante hardware or licences. Anything that repeats v1's structural choices listed in the audit §7.2 (one receiver radio per pack, static carrier pairs, one-way link, large RF backplane, wing antennas on stands, 1U-driven mechanics) unless an ADR shows it wins on P1–P4.
