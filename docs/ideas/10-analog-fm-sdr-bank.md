# 10. Analog FM packs (what the professionals use) with a software-defined receiver bank

**One sentence.** Transmit plain companded analog FM in 1785-1805 MHz exactly as Sennheiser EW-class systems do, where the pack is a VCO, a PLL, a compander and a PA, and replace the 32 expensive receivers with one 20 MHz SDR demodulating 32 FM carriers in software.

**How the air works.** 1785-1805 MHz, 200 kHz channel spacing (32 carriers = 6.4 MHz; the band holds 100 at that spacing), ±40 kHz deviation, 50 µs pre-emphasis and a 2:1 compander (NE571/SA571 class, or the pack's MCU doing compression digitally before the FM modulator). A 32 kHz pilot/ID tone identifies the pack and carries 100 bit/s of telemetry (battery). No framing, no slots, no digital latency. Downlink: a separate low-rate 2.4 GHz link (nRF52 at £3) for carrier assignment, mute and trim; or none (fixed carriers set by DIP switch) in the simplest variant.

**How the receiver works.** One SDR (AntSDR E200 £180, Pluto £190, or HackRF £220) with a band-pass filter and LNA; host runs a polyphase channeliser and 32 FM discriminators + de-emphasis + expanders. Analog FM demod is ~100 lines of code and the GNU Radio FM-broadcast-band examples do exactly this for 20 stations at once. For diversity, two antennas into two SDR channels (E200 has 2 RX) with per-carrier selection. Audio out as UAC2/AES67.

**Capacity maths.** 32 carriers at 200 kHz = 6.4 MHz; 96 at 200 kHz in the full band (spectral efficiency as good as pro systems because it is one). Intermodulation planning (the classic analog headache) is a solved problem with free tools (Shure Wireless Workbench, Sennheiser WSM).

**Latency budget.** Pack: compander + pre-emphasis ~100 µs → FM is instantaneous → SDR ADC/FPGA 100 → host transfer 500-1500 → channeliser/demod ~200 → out 250 ≈ 1.2-2.2 ms. The lowest latency on the board by a factor of two.

**Reliability story.** Analog degrades gracefully: a weak signal hisses, it does not mute, and the companding masks it; no concealment code is needed. Interference immunity in a Wi-Fi-free band is high; the enemies are intermodulation between our own carriers (plan the frequencies) and multipath nulls (diversity receive, which the SDR gives cheaply). No lockups in a pack with no software in the audio path. The dropout behaviour theatres know from decades of analog systems is, honestly, acceptable to them.

**Cost.** Pack: this is the hard part. A 1.79 GHz VCO+PLL (ADF4113 + discrete varactor VCO, or a MAX2871 synth £7 whose VCO cannot be audio-modulated, so FM must be applied via a separate mixer stage), PA to 50 mW, SA571 £1.50, preamp, low-noise regulators: £15-20 of RF that must be designed and laid out by someone competent in RF. Realistic pack ≈ £28-32 ex cell. Hub: SDR £180 + host £110 + filter/LNA £20 = £310 fixed (tripwire), £0 per channel. 32-channel ≈ £1,250.

**UK legality.** The band and standard (EN 300 422) were written for exactly this device; 50 mW EIRP body-worn. Analog FM spectral masks, adjacent-channel power and spurious must be measured.

**What v1 code or analysis it reuses.** Almost nothing on the pack; the host UI and output path. v1's ADPCM work is abandoned.

**Riskiest assumption** and the cheapest experiment. That a stable, low-phase-noise, audio-modulated 1.79 GHz source can be built for ~£15 by people without an RF lab (the pro vendors spend real money here). Experiment (< £150): buy one used Sennheiser EW 100 G2 pack on the 1800 MHz band (~£60 second-hand) and demodulate it on a Pluto/RTL-SDR to prove the SDR half; separately prototype a VCO+PLL on an ADF4351 module with a varactor FM stage and measure phase noise on a TinySA.

**Why it might be wrong.** It abandons P5/P6 (automatic join, booth telemetry) unless a digital side-channel is added, which brings back a digital radio and most of a digital pack. Analog pack RF is a craft, not a firmware problem, and the project's agents are better at firmware. Audio quality is capped by FM and companding (~90 dB dynamic range with artefacts on transients), fine for speech, debatable for belt singing. It is also, philosophically, the technology everyone is leaving.
