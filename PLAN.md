# OpenPack — Plan (Step 2 onward)

Written 2026-10-31. Inputs: `AUDIT.md`, `AUDIT-2.md`, `QUESTIONS.md`. Rule: **every subsystem is tested digitally with an existing, reputable tool before any hardware is bought beyond two dev kits.** Hardware appears only in Phase 5, and only to calibrate the simulators. Development is hands-off for the owner: see `docs/agents/hands-off.md`. The twin runs in GitHub Actions (Linux); the owner's Mac is not a build host for BabbleSim.

## The digital twin (what makes this possible)

The pack and receiver firmware is Zephyr (nRF Connect SDK). Zephyr builds the *same source* for `nrf5340bsim` (Nordic's BabbleSim simulated nRF5340: app core + net core, RADIO, TIMER, DPPI, CLOCK, UART modelled) and for the real chip. BabbleSim simulates the 2.4 GHz physical layer with multiple devices, path loss, modem models, and interferer devices, in simulated microseconds. The simulated UART attaches to a host pty, so the real host software talks to the simulated receiver. Result: 8 packs + 8 receiver modules + Wi-Fi interferers + the REST/WebSocket host run on one laptop, in CI, with microsecond timestamps, before a PCB exists.

Two constraints this imposes, both good:
- **Air format = RADIO MODE `Ble_2Mbit` with a raw (non-BLE) packet config**, not Nordic's `Nrf_2Mbit` mode. Same GFSK PHY on silicon, and it is what BabbleSim models. First task of Phase 2 is to confirm this against `nrf_hw_models/docs/README_impl_status.md`.
- **I2S is not modelled.** Audio in/out behind a 20-line driver interface; sim build reads/writes WAV files on the host, hardware build uses the real I2S DMA. Latency through I2S is measured in Phase 5 and added to the sim's number.

## Tool table (all existing, all free unless noted)

| Domain | Tool | Used for |
|---|---|---|
| Radio + firmware timing | BabbleSim + Zephyr `nrf5340bsim` (`nrf54l15bsim` if Q6 flips) | Scheduler, sync, retune gaps, copy merge, clock recovery, residual loss, latency, 8-pack co-existence |
| Wi-Fi interference | BabbleSim `2G4_device_WLAN_actmod` (WLAN activity model) + `2G4_channel_Indoorv1` + `2G4_modem_BLE_simple` | Burst loss under 1/6/11 traffic, near-far, both channels jammed |
| Firmware unit tests | Zephyr Twister + ztest on `native_sim` | Codec, PLC, frame parser, jitter buffer, clock PI loop, telemetry packer |
| Codec quality | ViSQOL v3 (Google), PESQ (ITU-T P.862, `pesq` PyPI); POLQA if the user has a licence | ADPCM-6 / ADPCM-8 / block-float bake-off, PLC quality under sim loss traces. ViSQOL runs locally (no CI build); accepted evidence = committed results CSV + the exact command, tool version and patches in `sim/codec/RESULTS.md` |
| DSP models | numpy/scipy | Reference codec implementations, bit-exact vs the C code, filter group delay |
| Analog front end | ngspice (inside KiCad 9) with TI SPICE models | Preamp noise (.noise), bandwidth (.ac), clipping at 0.6 Vrms (.tran), bias network, 5 V boost ripple |
| Power | `audit.py` + Nordic Online Power Profiler + datasheet currents | Runtime estimate; PPK2 in Phase 5 calibrates it |
| Schematic / PCB | KiCad 9 (SKiDL for netlists), KiBot in CI for ERC/DRC/BOM | Pack board, receiver sub-board, backplane, splitter |
| RF layout | None needed: pre-certified module with integrated FEM and u.FL. Optional: openEMS (FDTD) for whip-vs-body | Avoids the one thing agents can't verify digitally |
| Mechanical | CadQuery (code CAD), boolean interference checks, PrusaSlicer CLI for printability | Enclosure, battery door, clip, 1U panel |
| Host API | FastAPI + pytest + Schemathesis (fuzzes the OpenAPI schema) + `websockets` tests | REST/WebSocket contract, telemetry rate, reconnect |
| Whole system | GitHub Actions running Twister, bsim scenarios, pytest, KiBot | Every PR re-runs the twin |

## Phases

### Phase 0: Decide (1 session, Opus)
Take the "Hands-off defaults" in `QUESTIONS.md`. Q1–Q4 become `docs/adr/0001`–`0004`. Q5–Q8 become ADRs when resolved by Phase 1–2 data. Write `GLOSSARY.md` (frame, copy, carrier pair, residual loss, dropout event, lock, time diversity).
**Gate:** four ADRs exist. Time-diversity (Q1) becomes a Kconfig option so Phase 2 measures both answers.

### Phase 1: Models and bake-offs (1 week, Sonnet, Python)
1. `sim/codec/`: ADPCM-6, ADPCM-8, block-float 8+3/16, each frame self-contained. Corpus: public speech (VCTK), singing (VocalSet), synthetic whisper→scream sweep. Score with ViSQOL + PESQ. Output: table + 10 blind A/B clips for the user.
2. `sim/loss/`: Gilbert-Elliott (already in `audit.py`) extended to emit loss traces; PLC (repeat-with-fade) applied to codec output; ViSQOL vs loss pattern. Output: "quality vs busy fraction" curve with and without time diversity. This is the evidence for Q1.
3. `hw/spice/`: preamp (OPA1656 single supply 5 V, +6 dB, 1 kΩ source, bias network) in ngspice. Output: input-referred noise ≤ 1 µV, −3 dB bandwidth 20 Hz–40 kHz, no clipping at 0.6 Vrms. Decides Q7 (single vs dual path).
4. Optional, physical, 1 day: nRF52840 dongle occupancy scan in a packed house to calibrate the WLAN model's busy fraction. Not a blocker; the twin runs with literature values until then.
**Gate:** codec chosen (ADR-0005), front-end topology chosen (ADR-0006), WLAN model parameters written down.

### Phase 2: Firmware in the twin (3–4 weeks, Opus)
`fw/` single Zephyr app, two roles (`pack`, `rx`) by Kconfig, targets `nrf5340bsim` and the DK.
- Net core: frame scheduler (TX copy A, retune, TX copy B, reserved RX window), TIMER+DPPI driven, no busy-waiting.
- App core: codec (bit-exact to Phase 1 Python, tested by Twister), I2S abstraction, telemetry.
- Receiver: acquisition (open RX on channel A), lock, antenna select, copy merge by CRC, jitter buffer, PLC, HFCLKAUDIO PI clock recovery, UART telemetry/command protocol.
- bsim scenarios (`tests/bsim/`): (a) 1 pack, clean channel: latency, lock time; (b) 1 pack, WLAN on both channels at 10/25/40 % busy; (c) 8 packs, 16 carriers, WLAN 1/6/11, near-far with one interferer at −20 dBm at the receiver; (d) 1 h simulated clock drift at ±40 ppm; (e) pack reboot mid-show, re-lock.
**Gate (numbers from Q3, defaults):** sim latency ≤ 1.6 ms excluding I2S (budget leaves 0.6 ms for ADC/DAC filters measured in Phase 5); residual loss ≤ 0.1 % at the Phase 1 busy fraction with time diversity on; lock ≤ 2 s; clock error ≤ 1 sample after lock; 8-pack scenario shows no cross-pack collisions. The ≤ 1 dropout event/h number is a **hardware** gate (G5/G6), not a simulation gate: three of its inputs (per-copy floor loss, phone leakage into gap carriers, receive-antenna directivity) are unmeasured until Phase 5, so in simulation it is reported, not asserted. If the simulated event rate is within 10× of the target, proceed to Phase 5 and measure; if it is worse than 10×, add a PLC upgrade ticket (G.711 Appendix I-style waveform extrapolation) before Phase 5. ADR-0010 records this.

### Phase 3: Host software against the twin (1–2 weeks, Sonnet)
`host/`: FastAPI service on Linux, talks to 8 receiver UARTs. In CI, the UARTs are the bsim ptys. Endpoints: channel plan, trim, telemetry stream (WebSocket), RF health, firmware version. OpenAPI schema fuzzed by Schemathesis; WebSocket telemetry asserted at 10 Hz/pack under 8-pack sim.
**Gate:** Schemathesis clean, telemetry latency ≤ 200 ms sim-to-browser, host survives a receiver module reset.

### Phase 4: Hardware design, verified digitally (2–3 weeks, Opus designs, human reviews layout)
- `hw/pack/`: SKiDL → KiCad. Module with FEM + u.FL, PCM1840, preamp per Phase 1, 5 V boost, protection, locking TRS, USB-C (DFU/config), whip. KiBot ERC/DRC/BOM in CI; BOM cost asserted against `audit.py` target.
- `hw/rx/`: receiver sub-board (nRF5340 module, PCM5102 DAC, balanced driver, SPDT antenna switch, UART), backplane, 2× 1:8 active splitter (LNA + Wilkinson), 1U rear panel.
- `mech/`: CadQuery pack enclosure and 1U panel. Checks in `tests/mech/`: PCB/battery/enclosure boolean interference = 0, wall ≥ 1.6 mm, PrusaSlicer CLI reports no unsupported overhangs > 45°.
**Gate:** ERC/DRC/KiBot clean, mech tests pass, BOM ≤ target, layout reviewed by Opus from `kicad-cli`-rendered layer images (checklist in `hw/REVIEW.md`), fab DFM report clean.

### Phase 5: First hardware, calibration only (2 weeks, ~$250)
2× nRF5340-DK (or nRF54L15-DK), PCM1840 EVM, PCM5102 board, PPK2, a sigrok-compatible logic analyzer. The human plugs them into the Mac once (`docs/human/bench-setup.md`); everything after is CLI (`west flash`, `ppk2-api`, `sigrok-cli`). Same firmware, DK target. Measure what the twin can't: I2S/ADC/DAC group delay (GPIO toggles on sample-in and sample-out captured by the logic analyzer), real retune time, FEM current (PPK2), lock against real crystals, 1 h with a laptop + 2 phones on iperf beside the receiver (the human starts iperf from a checklist). Feed measured numbers back into `audit.py` and the bsim scenario parameters; re-run Phase 2 gates.
**Gate:** measured latency ≤ Q1 ceiling; twin and bench agree within 20 % on residual loss; runtime ≥ 16 h computed from measured current.

### Phase 6: 4-pack build and the hostile-RF gate
Order Phase 4 boards (4 packs, 4 rx sub-boards, 1 backplane, 1 splitter). Assemble, run Phase 3 host, repeat Phase 5's interference test with 4 packs, then a real sold-out house. Pass → v1. Fail → the twin already contains the v1.1 options (downlink beacon, adaptive channels, time diversity) as Kconfig; pick by re-running Phase 2.

## Repo layout (keep it this flat)
```
audit.py  AUDIT.md  AUDIT-2.md  QUESTIONS.md  PLAN.md  SPEC.md  GLOSSARY.md
docs/adr/          decisions
sim/               python models (codec, loss, plc)
fw/                one zephyr app, roles by kconfig, targets bsim + dk
host/              fastapi service
hw/pack hw/rx hw/spice   kicad + skidl + ngspice
mech/              cadquery
tests/bsim tests/mech    scenario scripts; unit tests live beside the code
.github/workflows/ twister + bsim + pytest + kibot
```

## Agent assignment
- **Opus (master):** Phase 0 grilling, ADRs, `SPEC.md`, Phase 2 firmware, Phase 4 schematics, review of everything Sonnet produces.
- **Sonnet:** Phase 1 models and bake-off, Phase 3 host, `GLOSSARY.md`, CI workflows, mech tests.
- **Human:** buying, plugging in the Phase 5 bench once, optional A/B listening, optional venue scan. Nothing else (`docs/agents/hands-off.md`).

## Explicitly not in this plan
Dante/AES67, e-ink, 5 GHz, UHF, encryption, downlink implementation (slot reserved only), in-pack charging, FCC certification (needed only when selling; module approval covers the proto).
