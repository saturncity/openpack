# OpenPack — Owner's design requirements

The owner's own requirements, as captured in the design discussions (the "Your Request" items of the Gemini summary, 2026-10-31), restated without the implementation choices. **This file is the yardstick.** Any decision not covered by `QUESTIONS.md` defaults is evaluated against it (`docs/agents/hands-off.md` → "Decisions outside the defaults"). Only the owner edits this file; agents propose changes as a stop-and-ask.

## Priority order

When two requirements conflict, the higher one wins and the ADR says so. This ordering was set by the agents from the owner's wording ("Sennheiser-quality", "survive packed auditoriums", "no accidental mutes"); the owner can reorder it.

| ID | Requirement | Owner's words | Measure |
|---|---|---|---|
| R1 | **Survives a packed auditorium.** Heavy audience Wi-Fi and pocket hotspots must not cause audible dropouts. | "Must survive heavy 2.4 GHz audience Wi-Fi and pocket hotspot interference" | Q3 pass numbers in `QUESTIONS.md` |
| R2 | **Never clips.** Whisper to scream without digital clipping; gain is not managed on the pack. | "No vocal clipping when actors scream or whisper"; "Gain is managed at the soundboard, not on the pack" | No clipping at 0.6 Vrms input (134 dB SPL on a 6 mV/Pa lav) |
| R3 | **Low latency.** Target ≤ 3 ms mic-in to XLR-out; hard limit 5 ms. | "Sub-3ms latency"; "performers hear no comb filtering or echo in monitors" | Logic-analyzer measurement, Phase 5 |
| R4 | **Nothing an actor can touch.** No mute, volume, or user controls on the pack. Power switch recessed. | "Absolutely no physical mute buttons, volume knobs, or user controls" | Inspection |
| R5 | **Sennheiser-quality audio.** Clean, wide dynamic range, theater-usable speech and singing. | "Match top-tier Sennheiser packs"; "clean dynamic range" | ViSQOL ≥ 4.0 on the Phase 1 corpus vs the 24-bit input; noise ≤ 1 µV input-referred |
| R6 | **Standard theater mics.** Locking 3.5 mm jack, Sennheiser pinout, headset and lavalier mics including DPA. | "Must work with standard theater headset/lavalier mics; must be locking" | Works with a Sennheiser ME-2-class electret and a DPA 4060-class capsule via adapter |
| R7 | **Removable 18650, hot-swappable by crew.** | "Standard removable 18650 Li-ion battery for quick crew hot-swaps" | Swap without tools in < 30 s |
| R8 | **Runtime 16–20 h continuous.** | "16 to 20 hours of continuous runtime" | Computed from PPK2 measurement |
| R9 | **8 packs per receiver rack, 1U, one analog XLR per channel.** | "1U rackmount; dedicated analog XLR outputs for every channel"; 8 packs | Inspection |
| R10 | **Two antennas on the rack, not 8–16.** Pack antenna must cope with body blocking. | "Avoid 8–16 separate antennas on the rack; address body-blocking range issues" | 2 BNC on the rack; link holds with the pack on a body (Phase 5/6) |
| R11 | **Remote management from the booth.** Basic REST/WebSocket API over Ethernet: telemetry (battery, RF, peak), trim, configuration. | "Central software control for booth crew; basic REST/WebSocket API" | Schemathesis + telemetry test |
| R12 | **~$30 per pack.** BOM at qty 100, excluding the cell. | "roughly $30 per beltpack" | `audit.py` BOM ≤ $35 |
| R13 | **Designed and tested digitally first.** Agents scrutinize the math, design schematics, CAD, firmware, and test in simulation before a 4-pack prototype. | "Test everything in simulation before building a 4-pack prototype" | `PLAN.md` gates |
| R14 | **Status visible on the pack.** Basic status LEDs. | "basic RGB status LEDs" | Power/battery and peak/clip LEDs minimum |
| R15 | **3D-printed enclosure**, external whip antenna. | "3D-printed enclosure"; "flexible external wire whip" | Inspection |

## Explicitly shelved by the owner (not requirements; do not reintroduce without a stop-and-ask)
E-ink display on the pack · Dante / AES67 · Sub-1 GHz and 5 GHz bands · on-pack gain control.

## Not stated by the owner (agents chose; see `QUESTIONS.md` defaults)
Region (US first) · codec · chip · one-way link in v1 · host platform · enclosure material · encryption (none).
