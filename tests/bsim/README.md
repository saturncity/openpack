# tests/bsim

BabbleSim scenario scripts.

- `probe/`: AIR-1 radio probe and the Wi-Fi calibration of `wlan_params.yaml` (#18).
- `sched/`: pack frame schedule from the phy Tx dump (AIR-4, #22).
- `rx/`: receiver lock, tracking, merge, pack reboot (RX-2..RX-4, RX-10, #23).
- `scenarios/run.py`: the G2 gate, scenarios (a)-(e) of PLAN.md Phase 2 (#27). CI job "G2 scenarios" in
  `.github/workflows/fw.yml`. Local: `python3 tests/bsim/scenarios/run.py` (CI lengths, a few minutes) or
  `--long` (minutes of sim time per run); `--only c`, `--no-build`, `--plan <yaml>`, `--keep` (phy dumps).
  Writes `g2-out/g2.json` and `g2-out/g2.md`. Checks print PASS/FAIL; XFAIL/XPASS name the issue that
  explains a known failure (exit code ignores XFAIL). "G2 gate MET" needs every check PASS and RX-7 (#24).
