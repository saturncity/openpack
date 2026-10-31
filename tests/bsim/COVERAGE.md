# BabbleSim coverage (issue #18)

Pinned: Zephyr v4.5.0 (`west.yml`), `nrf_hw_models` 50187f3, WLAN_actmod 9cb6d8e. CI: `.github/workflows/fw.yml` job `bsim`
(container `ghcr.io/zephyrproject-rtos/ci-repo-cache:v0.29.4.20260912`; container pull ~6 min, rest ~2 min with cache).

| Item | Status | Evidence |
|---|---|---|
| Device list builds | CONFIRMED | `bs_2G4_phy_v1`, `bs_device_2G4_WLAN_actmod`, `_burst_interf`, `_playback`, `_empty`, `_handbrake`, `_pause_simu`, `_time_monitor`; libs `Channel_multiatt`, `Channel_NtNcable`, `Modem_BLE_simple`, `Modem_Magic`. **No `Channel_Indoorv1`** in the Zephyr manifest: the twin uses `multiatt` (explicit path loss per device pair, `tests/bsim/probe/run.sh`); PLAN's "Indoorv1" is not available without adding that repo. |
| nrf_hw_models status (nRF5340) | CONFIRMED (docs) | RADIO implemented, TIMER/DPPI complete, UART[E] implemented, RTC/GPIOTE/IPC/CLOCK implemented; **I2S and PDM missing** (matches the plan: I2S behind a driver interface). `NHW_RADIO_timings.c` special-cases `MODE == Ble_2Mbit`. |
| UART -> pty | CONFIRMED | `tests/bsim/probe/uart`: bytes written to `uart0` appear on `/dev/pts/N` (`-uart0_pty -uart_pty_wait`, read by `read_pty.py`). Note `printk` goes to bsim stdout, not the UART, unless the console is routed to the UART. |
| WLAN_actmod device builds and runs | CONFIRMED | binary built, accepts `-channel -ConfigSet -power`; ConfigSet values are a fixed list (5, 10, 25, 50, 100, `_24M/_12M/_6M`, VoIP...), not a percentage knob. |
| AIR-1 raw `Ble_2Mbit` packet end to end | OPEN | `tests/bsim/probe/radio` builds for `nrf5340bsim/nrf5340/cpunet` and boots, but the TIMER0->DPPI->RADIO event chain never fired (sim idles to the end, 0 packets). Not a model gap proven; probe bug or missing clock/enable not yet found. |
| Occupancy per BLE channel at ConfigSet X (in-band 2437/2442, gap 2424/2449/2473) | OPEN | Depends on the line above. `run.sh <cfg>` is ready to produce `PROBE_RESULT freq= ok= crcerr= timeout=` per carrier. `wlan_params.yaml` unchanged (ConfigSet 10 / 50 remain estimates). |
| ADR-0009 fallback | NOT NEEDED YET | Only if AIR-1 proves unsupported in the model. |
