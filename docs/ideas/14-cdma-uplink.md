# 14. CDMA uplink: every pack transmits at once on one carrier, one receiver separates them by code (the GPS/IS-95 trick)

**One sentence.** All 32 packs transmit continuously on the same 20 MHz carrier using different spreading codes; a single SDR receiver correlates against 32 codes and recovers 32 streams, with no slots, no beacon timing, identical latency on every pack by construction and ~15 dB of processing gain against narrowband interference.

**How the air works.** Direct-sequence spread spectrum: 300 kbps data × 64-chip Gold codes = 19.2 Mchip/s, BPSK/QPSK, filling ~20 MHz (fits 1785-1805 MHz exactly, or sits inside the 2.4 GHz band on a Wi-Fi-free 20 MHz block). Near-far control (a pack 2 m from the antenna drowning one at 25 m) needs a downlink power-control loop at ~100 Hz, as cellular CDMA does; the downlink is a low-rate spread or GFSK beacon. Join: the pack picks a code from a pool and announces itself in a spread control channel; the receiver's code search finds it.

**How the receiver works.** One SDR with ≥ 20 MHz bandwidth (AntSDR/Pluto/LimeSDR, £160-220) and a host with enough compute for 32 correlators at 19.2 Mchip/s (GPU or FPGA; a Zynq-based SDR could host the despreaders). Rake fingers for multipath. Zero per-channel radio cost; latency identical for all packs.

**Capacity maths.** Asynchronous CDMA with 64-chip codes supports ~20-25 equal-power users at acceptable interference before multiple-access interference dominates (the classic ~⅓ of the spreading factor); 32 needs 128-chip codes → 38 Mchip/s → 40 MHz, which does not fit the PMSE band and is marginal at 2.4 GHz with Wi-Fi present. Capacity therefore ~20 mics per 20 MHz, below TDMA's.

**Latency budget.** Continuous: codec 300 → bit-level pipeline ~100 → SDR + host transfer 500-1500 → despread/decode 300 → out 250 ≈ 1.5-2.5 ms. Excellent.

**Reliability story.** Processing gain spreads a narrowband interferer's power over 20 MHz: Wi-Fi at 22 MHz gains little (it is as wide as we are), Bluetooth/DMX/phones gain ~13 dB. The near-far problem is the real enemy: power control that lags an actor walking toward the receiver by 100 ms raises everyone's error rate. Code acquisition after a dropout is ~100-300 ms.

**Cost.** Pack: there is no cheap commodity chip that transmits arbitrary DSSS at 20 Mchip/s. Options: a small FPGA/MCU generating chips + an IQ modulator (e.g. a Lattice iCE40 £3 + an RF upconverter/IQ modulator like ADL5375 £8 + LO synth £7 + PA £3) ≈ £25 of RF before the codec; or (ab)use an 802.11b chip's 11 Mchip/s DSSS mode (fixed Barker code, so no code separation). Pack ≈ £40-45 ex cell: over budget by 40 %. Hub £310 fixed, £0 per channel. 32-channel ≈ £1,700.

**UK legality.** Wideband continuous transmission at 2.4 GHz: EN 300 328 wideband non-FHSS, PSD ≤ 10 dBm/MHz, medium utilisation forces ≤ 10 mW at 100 % duty cycle; in 1785-1805 the 50 mW EIRP rule applies with EN 300 422's masks (written for narrowband mics; a 20 MHz signal would need checking against the mask's intent).

**What v1 code or analysis it reuses.** Codec, UI, host.

**Riskiest assumption** and the cheapest experiment. That a DSSS pack transmitter can be built for < £30. Experiment: none under £200 that tests the pack cost; the receive side can be simulated in GNU Radio for free, which is itself informative.

**Why it might be wrong.** It solves the wrong problem: TDMA already gives orthogonality for free with a beacon, and nobody sells a £5 DSSS pack chip because cellular CDMA is dead. Capacity per MHz is worse than TDMA. The only genuine wins (identical latency, graceful degradation, interference averaging) are small compared with a £15 pack penalty.
