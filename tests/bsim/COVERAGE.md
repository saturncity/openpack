# BabbleSim coverage (issue #18)

Pinned: Zephyr v4.5.0 (`west.yml`), `nrf_hw_models` 50187f3, WLAN_actmod 9cb6d8e. CI: `.github/workflows/fw.yml` job `bsim`
(container `ghcr.io/zephyrproject-rtos/ci-repo-cache:v0.29.4.20260912`). Local: Fedora, west workspace in `.ws/` (git-ignored).

| Item | Status | Evidence |
|---|---|---|
| Device list builds | CONFIRMED | `bs_2G4_phy_v1`, `bs_device_2G4_WLAN_actmod`, `_burst_interf`, `_playback`, `_empty`, `_handbrake`, `_pause_simu`, `_time_monitor`; libs `Channel_multiatt`, `Channel_NtNcable`, `Modem_BLE_simple`, `Modem_Magic`. **No `Channel_Indoorv1`** in the Zephyr manifest: the twin uses `multiatt` (explicit path loss per device pair, `tests/bsim/probe/run.sh`); PLAN's "Indoorv1" is not available without adding that repo. |
| nrf_hw_models status (nRF5340) | CONFIRMED (docs) | RADIO implemented, TIMER/DPPI complete, UART[E] implemented, RTC/GPIOTE/IPC/CLOCK implemented; **I2S and PDM missing** (matches the plan: I2S behind a driver interface). `NHW_RADIO_timings.c` special-cases `MODE == Ble_2Mbit`. |
| UART -> pty | CONFIRMED | `tests/bsim/probe/uart`: bytes written to `uart0` appear on `/dev/pts/N` (`-uart0_pty -uart_pty_wait`, read by `read_pty.py`). Note `printk` goes to bsim stdout, not the UART, unless the console is routed to the UART. |
| WLAN_actmod device builds and runs | CONFIRMED | binary built, accepts `-channel -ConfigSet -power`; ConfigSet values are a fixed list (5, 10, 25, 50, 100, `_24M/_12M/_6M`, VoIP...), not a percentage knob. |
| AIR-1 raw `Ble_2Mbit` packet end to end | CONFIRMED | `tests/bsim/probe/radio`, `run.sh none`: 15 000/15 000 packets OK on 2437/2442/2424/2449/2473, 15 s sim in ~1.5 s wall (Fedora). Two probe bugs, not model gaps: (1) on nrf*bsim only nrfx HAL calls trigger register side effects, raw `NRF_X->TASKS_Y = 1` does nothing; (2) DISABLE in DISABLED state raises a second DISABLED event. The model accepts only the BLE 2M layout (S0 byte, LE, whitening): AIR-2 amended, ADR-0009. |
| Occupancy per BLE channel vs ConfigSet (3 interferers, Wi-Fi 1/6/11, 2 m, 20 dBm) | CONFIRMED | AIR-1 loss on in-band 2437 MHz: ConfigSet 5 → 0.051, 10 → 0.105, 25 → 0.262, 50 → 0.560, 100 → 0.955. Gap carriers 2424/2449/2473 ≤ 0.006 at every set. Calibrated: busy 0.10 = ConfigSet 10 (15 dBm: 0.105/0.087 on 2437/2442); busy 0.40 = ConfigSet 50 `-sigma=0.9` (0.398/0.395). `wlan_params.yaml` updated. One 3000-packet run per point. |
| ADR-0009 | DONE | AIR-2 = BLE 2M PDU layout. Wi-Fi-burst fallback device not needed. |
