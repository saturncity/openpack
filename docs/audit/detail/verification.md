# OpenPack spec-compliance audit (commit 6f0d592, 2026-11-01)

Repo: /home/lenzj/openpack (detached HEAD at the wrap-up commit). Report text: `git show report-ib-ia:docs/report/REPORT.md` (copied to this scratchpad as REPORT.md). Nothing was built; every "pass" is simulation, calculation or design inspection.

Verdict scale used below:
- **VERIFIED-IN-SIM**: a committed, re-runnable test (bsim, ngspice, CadQuery, pytest) asserts the number.
- **CALCULATED**: a datasheet/analytic model in `audit.py` or a Python script, not exercised by firmware or a simulator.
- **DESIGN-ONLY**: inspection of schematic/CAD/text; no test asserts it.
- **CLAIMED-WITHOUT-ARTEFACT**: a number quoted in docs with no committed test output or script that reproduces it.
- **FAILED/PARTIAL**: evidence exists but misses part of the requirement, or the shipped configuration differs from the tested one.

---

## 0. Headline findings

1. **The CI-gated R1 configuration is not the configuration the project ships.** `tests/bsim/scenarios/run.py` asserts SYS-3 only for **TD on** (`run.py:565-574`, `if ... and td:`), at the default **20 dBm (US) EIRP** (`run.py:679`), US channel plan (`run.py:691`), isotropic antennas, **5 s** per run (`run.py:615`, `self.secs(5, 60)`). The last CI-style run on this machine (`.ws/g2-out113/g2.md`, footer: "Pack EIRP 20 dBm ... rx antenna gain 0 dB ... G2 gate met: True") shows **TD-off losses of 0.2–0.65 % for packs 2–6 at 40 % Wi-Fi** (c_40 rows), i.e. the shipped default (TD off, ADR-0017) fails SYS-3 in the CI geometry; only the TD-on rows are asserted. The UK (9 dBm) + wing-antenna evidence that the report quotes (0.086 %) came from a **one-off local run** (`docs/analysis/r1-wing-antennas.md` §4: `run.py --only bc --eirp 9 --plan host/channel_plan_us.yaml --geometry ... --busy 10,40 --c-secs 20`), whose `g2.json`/`g2.md` outputs are **not committed** (`git ls-files` shows only the 12 geometry input JSONs under `docs/analysis/r1-wing/`; outputs live in git-ignored `.ws/` and a stale worktree). PLAN.md Phase 2 gate text still says "G2 at UK power waits on the R1 stop-and-ask in ADR-0015" (PLAN.md:59) and "residual loss ≤ 0.1 % ... with time diversity on" (PLAN.md:59; SPEC.md §9 G2) — the gate was never re-pointed at TD off.
2. **0.086 % vs 0.1 % is not a statistically meaningful pass.** 17 lost frames in 19.7 k (`r1-wing-antennas.md` §4 "17 frames in 19.7 k"). Poisson 95 % CI on the rate: **0.046–0.132 %**. P(≤17 lost | true rate exactly 0.1 %) = 0.32. SYS-3 is specified "for 1 h" (3.6 M frames); the run covers 0.55 % of that. Design log TS-13 and open risk 15 admit "runs are 20–60 s, not the 1 h the gate names".
3. **The project's own analytic model contradicts the bsim result for the shipped default.** `sim/loss/RESULTS.md` §1 (Gilbert-Elliott, 1 h): "TD off never passes", even at 0.1 % gap-carrier busy and 10 % in-band busy (0.018 % loss but 11 events/h; at 0.2 %/40 % → 0.104 % loss). bsim gives 0.000 % TD-off for packs 2–8 (ADR-0017) because bsim's gap carriers are essentially perfectly clean (probe: ≤ 0.006 loss at every ConfigSet, `tests/bsim/COVERAGE.md`). The R1 pass therefore rests entirely on the gap carrier staying clean, which rests on (a) bsim's WLAN spectrum table and (b) the install geometry. Neither was ever measured; the venue scan that would have calibrated it (PLAN Phase 1 item 4, AUDIT-2 D1) was "made optional and not done" (design log TS-11).
4. **The R1 acceptance geometry was redefined to one the design can pass.** ADR-0003 fixes the interference setup ("laptop + 2 phones ... 2 m from the receiver antenna; pack at 10 m") and says "Changing them needs a new ADR". At UK power that setup fails (design log RF-5: "only 2 of 8 packs met SYS-3 at 40 % Wi-Fi", 12.7 dB short). ADR-0016/0021 kept the loss numbers but replaced the geometry with a modelled theatre (worst seat per antenna, 8 dBi panels 4 m up in the wings, no Wi-Fi in the wings, phones in airplane mode). The pass numbers are unchanged; what they are measured against is not.
5. **Latency (R3) is sound as a budget but only 885 µs of 2670 µs was ever measured in any simulator**; the rest is datasheet group delay (ADC 160, DAC 458/73, DMA 167) plus the structural 1000 µs frame. bsim executes firmware in zero simulated time, so the 100 µs "encode + IPC" lead is a *scheduled deadline*, not a measured compute time (ADR-0020, `fw/Kconfig:67-74`). The "as built 2.28 ms" number depends on the PCM5102A FLT=1 IIR filter whose audio effect was never checked (open risk 7).
6. **Python test suite: 204 passed, 19 skipped, 0 failed** (3 min 19 s). But on this host ngspice is not installed, so all four SPICE tests that back R2/R5 (PK-2, RX-8) **skipped**; ViSQOL and PESQ tests skipped; 11 bsim pty tests skipped (firmware exe env var not set); 1 mech test skipped (trimesh). The R2/R5 analog evidence could not be reproduced locally; it ran in CI (`.github/workflows/ci.yml:11` apt ngspice).
7. **Internal inconsistencies** between SPEC, STATUS, report and audit.py are listed in §3; the most material are the SYS-2 number (2.65 / 2.67 / 2.28 ms depending on document), the RK-5 noise figure (11.5 in SPEC vs 12.86 in the report), `audit.py` containing an exact duplicate of its 130-line latency section (lines 192–323 == 792–923, kept deliberately per design log PR-5), and `hw/REVIEW.md` contradicting itself on LCSC numbers.

---

## 1. Requirement-by-requirement table

Columns: ID → what SPEC demanded → evidence in repo → verdict. File references are to the repo root.

### System

| ID | Demand | Evidence | Verdict |
|---|---|---|---|
| SYS-1 | 8 packs → 1U rack, 8 balanced outputs | `mech/rack.py`, `tests/mech/test_rack_fit.py` (106 box checks, 3.39 mm under lid); backplane netlist `hw/rack/backplane.py` | DESIGN-ONLY (CAD-checked) |
| SYS-2 | ≤ 3.0 ms target / 5.0 ms hard; design 2.67 ms (2.28 FLT=1); TD on 4.60 | bsim (a): radio part 884 µs (`.ws/g2-out113/g2.md` row a; `run.py:519-523`, limit 1600). Rest from datasheets in `audit.py:192-323` (`sys2_stages`). I2S not modelled (PLAN "I2S is not modelled"). | CALCULATED (sim-anchored for 33 % of the budget). See §5. |
| SYS-3 | 1 h under Q3 interference: ≤ 0.1 % loss, ≤ 2 consecutive, ≤ 1 event/h | CI gate: TD-on only, 20 dBm, 5 s (`run.py:565-574, 615, 679`). Shipped config (TD off, 9 dBm, wings): one local 20 s run per case, outputs uncommitted (`docs/analysis/r1-wing-antennas.md` §4). 7 of 8 packs; pack 1 "by equivalence". Events/h reported, not asserted (ADR-0010). | PARTIAL / CLAIMED-WITHOUT-ARTEFACT for the shipped configuration. See §4. |
| SYS-4 | 48 kHz, 20 Hz–20 kHz ±0.5 dB, ViSQOL ≥ 4.0 vs 24-bit | ViSQOL: `sim/codec/RESULTS.md` worst 4.20 (codec alone, no loss, no FLT=1, no analog chain; macOS build, `tests/test_quality.py` skips without binary). Flatness: rx driver SPICE ±0.2 dB (`tests/test_spice_rx_driver.py:72`); preamp only asserts −3 dB at 20 Hz/40 kHz (`tests/test_spice_preamp.py:43`); ADC/DAC digital filter response not included; FLT=1 IIR (non-linear phase, −52 dB stopband) unchecked (design log AU-3). | ViSQOL: VERIFIED-IN-SIM (codec only). ±0.5 dB whole-chain: PARTIAL. |
| SYS-5 | UK 9 dBm EIRP, EN 300 328 OBW/OOB; 2482 edge ≤ 2483.28 MHz | `audit.py:324-520, 637-770` clause analysis; OBW extrapolated from a **different product's** test report (Fanstel BT840/nRF52840, BLE, "rate not stated", `audit.py:645`). Build-time power cap (design log FW-10). Whip gain 2 dBi assumed. | CALCULATED. 2482 legality: DESIGN-ONLY (open risk 2). |
| SYS-6 | FDMA, one pair per pack, no inter-pack sync | By construction; `host/channel_plan.py` validator | DESIGN-ONLY (trivially true) |
| SYS-7 | 300 µs RX slot reserved per frame | `tests/bsim/sched` (AIR-4 schedule). TD builds set `OP_RX_WINDOW_US=0` because the 81 B copy B ends at t0+877 (`docs/analysis/td-latency.md` §1) | PARTIAL: slot exists only with TD off |

### Air interface

| ID | Demand | Evidence | Verdict |
|---|---|---|---|
| AIR-1 | Raw `Ble_2Mbit` GFSK 2 Mbps | `tests/bsim/probe` 15 000/15 000 packets (COVERAGE.md) | VERIFIED-IN-SIM |
| AIR-2 | BLE 2M PDU layout, CRC-24 | Same probe; ADR-0009 (layout forced by the simulator, design log FW-1) | VERIFIED-IN-SIM |
| AIR-3 | Payload layout incl. td_audio | `fw/tests/td`, bsim (b_inband) RX-4 recovery rows | VERIFIED-IN-SIM |
| AIR-4 | 1000 µs ±20 ppm frame; A at t0, B at t0+T_A+T_GAP | `tests/bsim/sched` (fw.yml:91) | VERIFIED-IN-SIM |
| AIR-5 | Channel plan rules (≥ 3 MHz, ≥ 5 MHz near-far, gap carriers) | `host/channel_plan.py`, `tests/test_host.py` | VERIFIED (Python validator) |
| AIR-6 | UK +7 dBm conducted / 9 dBm EIRP | Build-time Kconfig assert (design log FW-10); FEM MODE/ANT_SEL pins unverified (open risk 4) | DESIGN-ONLY |
| AIR-7 | Airtime ≤ 45 % | `audit.py` `carrier_airtime` assert | CALCULATED |

### Bodypack

| ID | Demand | Evidence | Verdict |
|---|---|---|---|
| PK-1 | Locking 3.5 mm, Sennheiser pinout, 5 V bias via 2.2 kΩ | Pinout from ew100 G4 manual p.137 (design log PK-13); lock fit "unverified; DPA datasheet not reachable" | DESIGN-ONLY |
| PK-2 | 0.6 Vrms no clip; noise ≤ 1 µV A-wtd | `tests/test_spice_preamp.py:39-44` (0.967 µV; generic OPA1656 macromodel, TI model needs login; supply noise and 1/f not modelled, design log PK-4/TS-9). Skipped locally (no ngspice). | VERIFIED-IN-SIM, 3 % margin on an admittedly incomplete model |
| PK-3 | PCM1840, DRE, +6 dB preamp | ngspice + schematic | DESIGN-ONLY + SIM |
| PK-4 | nRF5340 module w/ FEM + u.FL | BOM (BT40NE) | DESIGN-ONLY |
| PK-5 | 31 mm whip ≥ 40 mm from cell | `hw/pack/fit.py` 40.9 mm (hw/REVIEW.md) | VERIFIED (CAD) |
| PK-6 | 18650 holder, reverse protection, no charger | SKiDL ERC (`tests/test_pack_sch.py`). Note: ERC passed while the battery divider was commented out (design log PK-8) — ERC is weak evidence. | DESIGN-ONLY |
| PK-7 | ≥ 16 h at max TX, ≤ 0.6 W | `audit.py` runtime model 17.5 h from datasheet currents | CALCULATED |
| PK-8 | Recessed switch only; LED thresholds | Inspection | DESIGN-ONLY |
| PK-9 | USB CDC protocol, MCUboot serial DFU | Protocol tested over bsim UART pty in CI (fw.yml:62, `tests/bsim/proto`). USB CDC and DFU are **build-only** (design log FW-14/FW-15: "not run on hardware: build-verified only (no USB or MCUboot in bsim)"). `chan` saved but does not retune radio (#132). | PARTIAL |
| PK-10 | Telemetry every frame | bsim protocol test | VERIFIED-IN-SIM |
| PK-11 | ≤ 100×65×25 mm, PETG, tool-free door | `tests/mech/test_pack_fit.py` (96×62×22.8) | VERIFIED (CAD); door usability untested |
| PK-12 | BOM ≤ $35 at qty 100 | `audit.py` $33.34 at Fanstel direct price; $36.3–36.63 at Digi-Key (design log SC-1). Excludes assembly and coating. R12 target was ~$30. | CALCULATED; PARTIAL vs R12 |
| PK-13 | Boot → transmitting ≤ 1 s | No check in `run.py` (only RX-2 lock ≤ 2 s at `run.py:526`). bsim boots instantly; ADC coupling-cap settle ~0.1 s not modelled (design log PK-10). | CLAIMED-WITHOUT-ARTEFACT |

### Receiver module

| ID | Demand | Evidence | Verdict |
|---|---|---|---|
| RX-1 | Module, SPDT switch, UART, I2S | Schematic (`hw/rx/rx.py`) | DESIGN-ONLY |
| RX-2 | Lock ≤ 2 s | bsim (a) 0.00125 s | VERIFIED-IN-SIM (trivial in sim: no real crystal start-up) |
| RX-3 | Tracking ±50 µs, re-acquire after 100 misses | `tests/bsim/rx`, (d) tracking | VERIFIED-IN-SIM |
| RX-4 | First-valid merge; TD recovery | bsim b_inband rows: fw recovers 1683 frames | VERIFIED-IN-SIM |
| RX-5 | Antenna selection (6 dB rule; miss-triggered switch; probe every 1000) | `fw/tests/rx_ant` (6/6 native_sim). In the wing runs **RX-5 is replayed in Python** (`run.py` `rx5_replay`, `tests/test_wing.py`), firmware sees one antenna only (`run.py:589` comment). | PARTIAL: firmware unit-tested; system result is a model replay |
| RX-6 | PLC repeat+fade, mute after 10 ms | `sim/loss/plc.py`, `tests/test_loss.py:35-44`; ViSQOL curve on two macOS `say` clips (RESULTS.md, "each cell noisy ±0.1") | VERIFIED-IN-SIM (Python), thin corpus |
| RX-7 | ≤ 1 sample/h, 0 slips over 1 h at ±40 ppm | ztest `fw/tests/rx_clk` (1 h); bsim (d) 300 s per PR, 1 h nightly (fw.yml:5, 172). HFCLKAUDIO/I2S not modelled: software DAC clock on TIMER2 stands in (ADR-0013, design log TS-2). | VERIFIED-IN-SIM with a stand-in clock |
| RX-8 | +18 dBu, Zout ≤ 100 Ω, trim | `tests/test_spice_rx_driver.py` (skipped locally) | VERIFIED-IN-SIM |
| RX-9 | 10 Hz reports | `tests/test_host.py:175` (7–13 msgs, fake modules); protocol over pty | VERIFIED (fake receivers) |
| RX-10 | Survives host reset / pack reboot | bsim (e) | VERIFIED-IN-SIM |

### Rack

| ID | Demand | Evidence | Verdict |
|---|---|---|---|
| RK-1 | 1U, 12 V, 8 XLR, 2 BNC, bias-T, RJ45, USB-C | Backplane netlist, CAD | DESIGN-ONLY |
| RK-2 | LNA NF ≤ 2 dB, coax within 21.1 dB NF need, install rule | `audit.py` Audit 6/7 (LNA proxy spec "tested at 3.5 GHz ONLY", `audit.py:1048-1049`); Wilkinson as routed 13.7 dB modelled (`hw/rack/rf_routed.py`, scikit-rf); patterns read off plots (open risk 6) | CALCULATED |
| RK-3 | CM4 host, boots ≤ 60 s | Design; no boot-time test | DESIGN-ONLY |
| RK-4 | Front LEDs | Design | DESIGN-ONLY |
| RK-5 | Chain, NF ≤ 21.1 dB (design 11.5), no compression, keyed slot | `audit.py` Audit 6 (report D1 says 12.86 dB as routed); `tests/test_rack_rf.py`, `tests/test_rack_layout.py:177` (keyed slot test) | CALCULATED |

### Host API

| ID | Demand | Evidence | Verdict |
|---|---|---|---|
| API-1 | REST endpoints, OpenAPI 3.1 | `tests/test_host_schemathesis.py` against fake receivers | VERIFIED (fake receivers) |
| API-2 | WebSocket 10 Hz, ≤ 200 ms end-to-end "from the module" | `tests/test_host.py:178` `age_ms ≤ 200` with fake ptys; `tests/bsim/host/test_host_bsim.py` runs in CI against bsim ptys (skipped locally) | VERIFIED (host-side); module-to-browser never measured on silicon |
| API-3 | channel_plan.yaml single source | `tests/test_host.py` | VERIFIED |
| API-4 | No auth, documented | README | DESIGN-ONLY |
| API-5 | RF scan, 10 s cache | `tests/test_host.py:181-192` | VERIFIED (fake receivers) |

### Firmware structure

| ID | Demand | Evidence | Verdict |
|---|---|---|---|
| FW-1 | One app, two roles, bsim + DK targets | Twister (fw.yml:219-225); DK target build-only | VERIFIED (build) |
| FW-2 | Net core RADIO/TIMER/DPPI; app core codec/I2S; IPC 1 frame/msg | bsim sched + ADR-0020 | VERIFIED-IN-SIM |
| FW-3 | `op_audio.h` with I2S and WAV backends | WAV backend exercised in bsim; I2S backend build-only | PARTIAL |
| FW-4 | Codec bit-exact to Python | `fw/codec/tests` golden vectors; `tests/test_codec.py` | VERIFIED |
| FW-5 | Timing constants in Kconfig | Inspection | DESIGN-ONLY |
| FW-6 | MCUboot both roles, serial/UART DFU | Build-only; dev signing key (open risk 11); net core not updatable via MCUboot (design log FW-15) | DESIGN-ONLY / PARTIAL |
| FW-7 | Frame lead ±3 µs, 0 skips over 1 h | `tests/bsim/sched/lead.sh` 300 s per PR, 1 h nightly; test-only rate offset stands in for HFCLKAUDIO (TS-2) | VERIFIED-IN-SIM with a stand-in clock |

### Gates (SPEC §9 / PLAN)

| Gate | Status |
|---|---|
| G1 | Met: codec (ViSQOL CSV committed), ngspice PK-2, `tests/bsim/wlan_params.yaml` committed. Caveat: busy fractions are estimates (`wlan_params.yaml` "Honest limit: no primary source gives one busy fraction"). |
| G2 | "Met" in CI **at 20 dBm, TD on** (`.ws/g2-out113/g2.md` footer). UK-power / TD-off / wing geometry: not a CI gate; one-off local run, outputs not committed. |
| G3 | Met against fake receivers and bsim ptys (`tests/test_host*.py`, `tests/bsim/host`). |
| G4 | Not fully met: DRC clean via `kicad-cli` (not KiBot as SPEC/PLAN say, design log TS-6); image review done (`hw/REVIEW.md`); **fab DFM never run** (open risk 16; report D1 "Pass, except the fab DFM check"). G4 is the purchase gate (PLAN.md Phase 4), so strictly the purchase gate was not passed. |
| G5, G6 | Never run (no hardware). All of R1, R3, R5, R8, R10 were explicitly deferred to these gates. |

---

## 2. Owner requirements (REQUIREMENTS.md R1–R15) summary

| R | Report D1 says | Honest verdict |
|---|---|---|
| R1 | "Pass in sim" | PARTIAL / unproven. See §4. The report's own D4 says the bench tests "None of them will run". |
| R2 | "Pass in sim" | VERIFIED-IN-SIM (SPICE, generic macromodel; CM-range bug was only caught by review, design log PK-5). |
| R3 | "Pass by calc + sim" | CALCULATED (33 % measured in bsim). See §5. |
| R4 | "Pass (design)" | DESIGN-ONLY; genuinely satisfied by inspection. |
| R5 | "Pass in sim" | ViSQOL codec-only; noise 0.967 µV on an incomplete noise model (3 % margin, open risk 8). PARTIAL. |
| R6 | "Pass (design)" | DESIGN-ONLY; lock fit and DPA adapter unverified. |
| R7 | "Pass (design)" | DESIGN-ONLY; printed cradle with unrated contacts (hw/REVIEW.md). |
| R8 | "Pass by calc" | CALCULATED; 17.5 h vs 16 h from datasheet currents and an estimated FEM current. |
| R9 | "Pass in CAD" | DESIGN-ONLY; case side-lug interference unresolved (open risk 18). |
| R10 | "Pass (design)" | DESIGN-ONLY; body blocking assumed 10 dB in NF budget only, **not in the C/I model** (`sim/loss/wing_geometry.py:11` "no body loss, no fading"). Design log AN-7: "real body loss can be 15–20 dB". |
| R11 | "Pass in CI" | VERIFIED against fake receivers / bsim ptys. |
| R12 | "Partial" | Agreed: $33.34 (Fanstel) / ~$36.5 (Digi-Key) vs ~$30 target. |
| R13 | "Pass" | The digital-first process was followed. But R13's purpose ("before a 4-pack prototype") never arrived. |
| R14 | "Pass (design)" | DESIGN-ONLY. |
| R15 | "Pass (design)" | DESIGN-ONLY. |

---

## 3. Where the documents disagree with each other

1. **SYS-2 latency number.** SPEC.md SYS-2 and §2: 2.67 ms / 4.60 ms. ADR-0017 and report B4: 2.65 ms / 4.58 ms (pre-#98 numbers). Report C6/D2: "2.28 ms as built" (FLT=1). `audit.py:194` model: 2670 / 4577 (FLT=1). `run.py` a_td projection: 4596 µs vs limit 4600 (`run.py:105`) — 4 µs of margin in the gate, 23 µs in audit.py; the two use different filter constants (`run.py:103-104` vs `audit.py:204-205`). Design log AU-4 quotes both.
2. **RK-5 noise figure.** SPEC RK-5: "design: 11.5 dB". Report D1: "NF 12.86 dB". `docs/analysis/r1-wing-antennas.md` §3: 11.48 dB. Design log RK-7c: 13.7 dB Wilkinson as routed, "NF margin stays 8.2 dB" (→ ~12.9). SPEC was not updated after #126.
3. **Rack lid clearance.** Report D1/C4: 3.39 mm under the lid; report C8 and design log ME-3: "4.9 mm spare under the lid line". Two different measurements (sub-board top vs. receivers) presented with the same wording.
4. **G2 gate definition vs. shipped default.** SPEC §9 G2 and PLAN.md:59 require SYS-3 "with time diversity on"; ADR-0017 ships TD off. `run.py:565` still asserts TD on only. STATUS/report present the TD-off 0.086 % as the headline result.
5. **R1 acceptance geometry.** ADR-0003 (2 m / 10 m, isotropic) vs ADR-0021 (modelled theatre, 8 dBi panels). ADR-0003 says numbers "live in a test, not prose" and changes need a new ADR; the geometry change is in ADR-0016/0021 but ADR-0003 was never amended or superseded.
6. **`audit.py` duplicate block.** Lines 192–323 and 792–923 are byte-identical (`diff` clean). Design log PR-5: "keep both audit sections". Audit 7 (line 924) precedes Audit 6 (line 1043).
7. **`hw/REVIEW.md` self-contradiction.** Pack "S3 (JLC outputs, done)": "`bom_jlc.csv` has an LCSC # on every line". Pack open item 9: "`bom_jlc.csv` has no LCSC numbers yet". Pack open item 2 (BT40NE antenna wiring) is stale per design log TS-15.
8. **KiBot vs kicad-cli.** SPEC §9 G4 and PLAN tool table say KiBot; CI uses `kicad-cli` (design log TS-6).
9. **Region.** REQUIREMENTS.md footer: "Region (US first)"; ADR-0015 and everything else: UK (design log CO-6). REQUIREMENTS is owner-only so it was never fixed.
10. **GE model vs bsim on TD-off robustness.** `sim/loss/RESULTS.md` §1: TD off fails at every gap-busy ≥ 0.1 %. ADR-0017: TD off 0.000 % in bsim. Both are in the repo as evidence; the design log never reconciles them.
11. **STATUS.md "All design work is merged"** vs. G4/purchase gate not passed (no DFM), and open issues #128, #132 (host DFU path, console retune) still open at close.
12. **OBW evidence provenance.** SPEC SYS-5 cites "ADR-0016" for the 2482 edge; `audit.py:645-647` shows the OBW (1.84 MHz) comes from a BT840/nRF52840 BLE report with "rate not stated", scaled to the nRF5340 at 2 Mbps by assumption.
13. **`tests/test_rack_rf.py:41`** asserts the ideal Wilkinson model IL ≤ 11.0 dB, while SPEC RK-5 now says "≤ 14 dB as routed". Not a contradiction (different models) but the test does not guard the as-routed figure; `tests/test_rack_layout.py:177` does.

---

## 4. R1 evidence quality (packed-auditorium Wi-Fi survival)

### How Wi-Fi was modelled
- **Three** `2G4_device_WLAN_actmod` interferers, one each on Wi-Fi 1/6/11, 20 MHz each (`tests/bsim/wlan_params.yaml`, `run.py:438-446`). Busy fraction is "ConfigSet" presets calibrated so that AIR-1 **in-band** packet loss equals the busy fraction: 10 % = ConfigSet 10 at 15 dBm; 40 % = ConfigSet 50 with `-sigma=0.9` at 20 dBm (`COVERAGE.md`, `wlan_params.yaml`). One 3000-packet probe run per calibration point.
- Both busy values are **estimates** (`wlan_params.yaml`: `estimate: true`; "no primary source gives one busy fraction for a packed auditorium"). The planned venue occupancy scan was dropped (design log TS-11).
- Spectrum: bsim's `TxSpectrum_WLAN` table (`sim/loss/bsim_modem.py`), −12…−15 dB at 11 MHz offset. The 802.11 mask allows −20 dB there, so bsim is pessimistic *versus the mask*; real handset ACLR at 11–17 MHz offset is unknown (design log RF-13, open risk 9). `sim/loss/RESULTS.md` §3 shows the design needs ≥ 14 dB effective rejection; if phones are 6 dB worse than the mask the gap carrier starts losing frames.
- Modem: `2G4_modem_BLE_simple` — "This is the twin's physics, not the silicon's" (`bsim_modem.py` docstring). C/I threshold for an 11 MHz gap copy: −12.3 dB (`wing_geometry.ci_threshold_db`), with a 3 dB design margin on top; worst stage point keeps only 1.5 dB of that 3 dB (ADR-0021 Evidence).
- Gilbert-Elliott (`audit.py:89`, `sim/loss/traces.py`) was the Phase 1 analytic model and is the evidence for *needing* TD; it was not used for the final pass claim.

### What the pass depends on (all unmeasured)
1. **Install rule** (ADR-0021, `docs/human/antenna-install.md`): panel 1 m offstage, ¼ depth back, **4.0 m up (never below 3.5)**, aimed at the far upstage corner, 10° down. Tolerance table (`r1-wing-antennas.md` §2): any single deviation stays above threshold; "several at once can fall below it". At 3.2 m the 12 m house is already under.
2. **No Wi-Fi transmitter in either wing or on stage; backstage Wi-Fi ≥ 6 m; crew phones in airplane mode.** With one crew AP 3 m from a panel: −6.8 to −10.3 dB (row W1-crew) — a hard fail. Real wings contain SM desks, comms, wireless DMX, IEM transmitters and crew phones.
3. **Venue Wi-Fi on 1/6/11, not 13.** Wi-Fi 13 (common in the UK) costs packs 1, 6–8 their gap carrier (SPEC AIR-5). Audience pocket hotspots pick channels automatically (often 3/8/9/13) and may use 40 MHz channels; neither is modelled.
4. **Only 1/6/11 modelled; nothing else in the band.** No Bluetooth/BLE (every phone in the house hops across all 40 BLE channels including every gap carrier), no Zigbee, no HT40, no microwave ovens, no other wireless-mic/IEM systems.
5. **Free space, static geometry.** `wing_geometry.py:11`: "no body loss, no fading". bsim holds each geometry still for 20 s; RX-5 "replayed from a converged state", walking transients "aren't timed" (§6). Body loss (10 dB) and fade (10 dB) appear only in the NF budget, not in the C/I budget that decides R1.
6. **Antenna pattern read off a datasheet plot**; 60–90° points interpolated; 3-D pattern unknown (open risk 6). Rear lobes −9 dB.
7. **7 of 8 packs.** bsim refuses carriers above 2480 MHz; pack 1 runs the US in-band pair in bsim and shows 21.5 % loss TD-off at 40 %; it is "credited by equivalence" with 2476/2479 (ADR-0016, design log RF-6/TS-1). Its 2482 carrier is also on the QPQ1907 BAW skirt (RF-11, +2 dB estimate).
8. **Receiver compression/PIMD** analytic only (`audit.py` Audit 6/7); bsim does not model it.
9. **Run length and statistics.** 19.7 k frames per case vs 3.6 M in the specified hour. 17 lost → 95 % CI 0.046–0.132 %. The result is consistent with a true rate above the limit.
10. **The CI-gated configuration is a different one** (20 dBm, TD on, isotropic, 5 s) — see §0.1.

### Honest judgement
The twin answers "does the firmware schedule, merge, PLC and antenna-select correctly against a 20 MHz OFDM-shaped interferer at a given received power?" — and it does, repeatably. It does not answer "will a packed UK theatre produce ≤ 1 audible dropout per hour?" The pass is a single-point result under an idealised, static, 3-source interference model, with one of the project's own models (GE) saying the shipped default has no margin once the gap carrier is even 0.2 % busy. In a real house: hotspots and APs on non-1/6/11 channels, Bluetooth, body loss of 10–20 dB, moving actors, and ordinary backstage Wi-Fi each individually break an assumption the pass depends on. TD on recovers roughly 4× (0.020 %) at the cost of exceeding the R3 target (4.6 ms), and even that is "fallback", not margin. My judgement: R1 was **not demonstrated**; what was demonstrated is that the architecture *can* be made to pass a simulator under a rule set the venue must enforce.

---

## 5. Latency (R3) evidence quality

Budget (`SPEC.md` §2, `audit.py:212-231`), TD off, FLT=0: 160 + 1000 + 120 + 41 + 212 + 100 + 212 + 200 + 167 + 458 = **2670 µs**.

| Stage | µs | Source | Measured in bsim? |
|---|---|---|---|
| ADC decimation filter | 160 | PCM1840 SBAS989 Table 18 (7.7/fs, MD0=1 strap) | No (I2S/ADC not modelled) |
| Frame accumulation | 1000 | Structural (48 samples) | No (structural) |
| Frame clock → TXEN | 120 | Kconfig lead 100 + latch 20 | Yes, but see note A |
| TX ramp | 41 | bsim model (40 on silicon) | Yes (bsim model) |
| Copy A, gap, copy B | 212+100+212 | bit count at 2 Mbps; T_GAP is a parameter | Yes (bsim timestamps) |
| Decode + jitter slot | 200 | Fixed deadline (ADR-0013 setpoint 125) | Yes (deadline; slack 133 µs) |
| DAC DMA block | 167 | 8 samples | No |
| DAC interpolation | 458 (FLT=0) / 73 (FLT=1) | PCM5102A SLAS859C Table 4/7 | No |
| **Measured share** | 885 of 2670 (33 %) | | |

Note A: BabbleSim executes firmware instructions in **zero simulated time**; "encode + IPC = 100 µs" is the lead the frame clock is phased ahead of the latch (ADR-0020, `fw/Kconfig:67-74` "ADPCM-6 encode + IPC must finish inside it"). Real Cortex-M33 encode time + IPC on silicon was never measured. If it exceeds 100 µs the symptom is skipped frames (R1), not added latency — the negative-control stress test shows this (ADR-0020: "A higher-priority load of 300 us > lead skips").

What could make the real number worse:
- I2S path on silicon: at least one sample period of latching at each converter (~21 µs ×2) plus I2S DMA double-buffering on the app core — explicitly "measured in Phase 5 and added to the sim's number" (PLAN.md "I2S is not modelled"). Never added.
- PCM1840 160 µs assumes MD0=1 low-latency decimation; its passband/phase effect on SYS-4 unchecked. Linear-phase alternative is 356 µs (+196).
- PCM5102A FLT=1 (73 µs) is the only way to the "2.28 ms as built" and to TD-on ≤ 4.6 ms; it is an IIR with unspecified phase and −52 dB stopband; design log AU-3 "audible effect unchecked".
- T_GAP = 100 µs retune "needs silicon measurement" (`td-latency.md` row 10); nRF5340 RADIO disable→ramp→enable timings are bsim-model values.
- Jitter slot 125 µs setpoint assumes µs-level arrival jitter; real crystal/clock-loop behaviour unknown (TS-2: HFCLKAUDIO not modelled).
- HFCLKAUDIO software stand-in: the real audio PLL step quantisation (3311 ppb) and its settling are modelled, not measured.
- TD on: `run.py` asserts 4596 ≤ 4600 (4 µs margin); hard limit 5000 leaves 404 µs for every unmodelled item above. Mixed TD/non-TD packs differ by 2.3 ms (design log AU-7).
- Historical: the budget was wrong twice before (SYS-2 text 2.6 vs table 2.72; 435 µs latch wait missed, FW-3) — found by measurement in bsim, which is the process working, but it also shows how much of the budget was bookkeeping.

Verdict: the TD-off design has ~330 µs of headroom to the 3 ms target with FLT=0, ~700 µs with FLT=1, which is probably enough for the I2S items. TD-on at 4.6 ms is tight against 5 ms. R3 is credible but CALCULATED, not verified.

---

## 6. Python test suite run

Command: `cd /home/lenzj/openpack && source .ws/env.sh && .ws/.venv/bin/python -m pytest tests -q -x --timeout=600 -p no:cacheprovider`
Result: **204 passed, 19 skipped, 0 failed**, 199 s (second run with `-rs` identical: 204/19).

Skipped (all environment, none are failures):
- `tests/test_spice_preamp.py:18`, `tests/test_spice_rx_driver.py:30,86,112` — **ngspice not installed** on this host (`which ngspice` empty). These are the PK-2/RX-8 (R2, R5) evidence; CI installs ngspice via apt (`ci.yml:11`).
- `tests/test_quality.py:9,17` — ViSQOL binary not built; `pesq` not installed. ViSQOL never runs in CI by design (PLAN tool table: "accepted evidence = committed results CSV").
- `tests/bsim/host/test_host_bsim.py` ×5, `tests/bsim/proto/test_proto.py` ×6 — "BSIM_OUT_PATH / firmware exe not set" (need a built firmware exe path; run in `fw.yml` CI).
- `tests/test_fw_board_pins.py:64` — needs `OPENPACK_FW_BUILDS` (CI twister step).
- `tests/mech/test_mech.py:9` — `trimesh` not in the venv.

Not attempted (time box): a full bsim `run.py` or Twister run locally. Existing local artefacts `.ws/g2-out95/103/113` were inspected instead. GitHub CI (`gh run list`) shows `ci` and `fw` workflows green on the final commits.

---

## 7. Lessons about the verification process

**What was good**
1. Same firmware source runs in BabbleSim and on the DK target; CI re-runs the twin on every PR with hard asserts (G2 scenario runner, lead-loop, clock-recovery nightly 1 h). The scheduler, merge, TD recovery and clock loop are genuinely exercised, and bsim found real bugs (k_timer phase sweep FW-2, 435 µs latch wait FW-3, RX-5 probe cost and intermittent-block, design log §4 of r1-wing-antennas.md).
2. Numbers live in code (`audit.py` asserts, `run.py` checks, SPICE asserts), and the latency model is asserted against the bsim measurement (`audit.py:271-276`).
3. Independent datasheet-level review of every hardware PR caught faults that automated checks passed: op-amp CM range (PK-5), QPQ1907 with no RF path (RK-1), bias-T burnout (RK-2), battery path on inner copper (PK-11), unkeyed mezzanine (RX-1), rules file silently not loaded (TS-8). Design log PR-3 is the right lesson: "ERC/DRC clean is weak evidence".
4. The design log is candid: TS-13 and open risk 15 state exactly what the twin does not model; ADR-0010 explicitly refuses to assert events/h in simulation. The report's D4 lists the bench tests that will never run.
5. Honest labelling of estimates in `wlan_params.yaml` (`estimate: true/false` per parameter).

**What was theatre**
1. **"Pass in simulation" for R1 was a pass of the simulator, not of the requirement.** The acceptance geometry was changed (ADR-0003 → ADR-0021) until the design passed, the gate asserts a configuration (TD on, 20 dBm) that is not what ships, the shipped-configuration evidence is an uncommitted local run, and 0.086 % vs 0.1 % on 20 k frames is noise.
2. **Margins quoted to three significant figures from models with ±several-dB unknowns.** "1.5 dB over the twin threshold", "0.967 µV vs 1 µV (3 %)", "23 µs under 4.6 ms", "4 µs" in run.py. Each is reported as a pass; each is within the uncertainty of its inputs (generic op-amp macromodel without supply/1-f noise; antenna pattern read off a plot; datasheet group delays).
3. **Deferring every physical input to a Phase 5 that then never happened.** Body loss, phone leakage, FEM pin polarity (ANT_SEL — a wrong guess kills the link), OBW at 2482, coax and Wilkinson loss, ADC/DAC delay, encode time. ADR-0019 (single purchase at the end) made the whole verification chain hostage to a buy the owner then declined, so nothing was ever calibrated.
4. **Replacing the venue measurement with a literature guess** (TS-11) and then building a 3-source interference model on it. The one cheap physical step that would have anchored R1 (a dongle occupancy scan in a packed house) was optional and skipped.
5. **Document drift as a verification risk.** Five different SYS-2 numbers, two RK-5 NFs, stale open items, a duplicated 130-line block in `audit.py` kept "to avoid conflicts". For an owner with no electronics background, inconsistent numbers in the "yardstick" documents are indistinguishable from errors.
6. **Model-in-the-loop presented as firmware-in-the-loop.** The decisive wing-antenna runs replay RX-5 in Python because bsim's receiver sees one antenna; the firmware's own antenna logic is only unit-tested.
7. **"By equivalence" for one pack in eight** on the one carrier that also carries the regulatory edge risk.

Bottom line for the owner: against *its own* SPEC the project verified the digital parts it could simulate (frame schedule, merge, clock recovery, codec quality, latency bookkeeping, host API) and designed everything else to a clean DRC. The top-ranked requirement, R1, is supported by a carefully built but idealised model whose critical inputs were never measured, and the configuration the project ships was never gated in CI. The report's "Pass in sim" column is accurate in its literal wording and misleading in its weight.
