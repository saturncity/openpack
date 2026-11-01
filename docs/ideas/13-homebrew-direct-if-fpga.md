# 13. Home-made 60 MHz-wide receiver: a £10 ADC board, an open FPGA and a mixer

**One sentence.** Build the wideband receiver ourselves from an AD9226 12-bit 65 MSPS ADC module (£8-12, common in Chinese FPGA kits), a mixer + ADF4351 LO module to bring 2.4 GHz (or 1.8 GHz) down to a 30 MHz IF, and an open-toolchain FPGA (Lattice ECP5 on a £30 board, or a Zynq board) running a polyphase channeliser and 32 GFSK demodulators, so the receiver has no per-channel cost and no proprietary SDR.

**How the air works.** Any 2.4 GHz or 1785-1805 MHz TDMA/FDMA scheme from ideas 01, 02, 09, 11. The receiver's bandwidth (60 MHz at 65 MSPS with an under-sampled or quadrature IF) lets carriers sit anywhere.

**How the receiver works.** Antenna → LNA (£3) → band filter → mixer (ADE-xx class £5) → LO from ADF4351 module (£15) → IF filter → AD9226 (12-bit, 65 MSPS, £10) → FPGA (Colorlight i5/i9 ECP5 boards £25-40, fully open toolchain yosys/nextpnr; or a used Zynq board) → Gigabit Ethernet or USB 3 (FT601) to the host → audio. The FPGA does the channeliser (32-128 point polyphase FFT) and per-channel GFSK discriminators + bit sync + frame detect; the host does ADPCM and output. Nothing in the chain is a licensed radio IP or a closed SDR library.

**Capacity maths.** 60 MHz of 2.4 GHz band or the whole 20 MHz PMSE band at once: 32-100 carriers depending on the air scheme; adding capacity is a firmware change, not hardware.

**Latency budget.** ADC + channeliser + demod in FPGA ≈ 50 µs; FPGA-to-host 200-500 µs over Ethernet; so receiver-side latency is the lowest of all SDR variants. Overall with TDMA: codec 300 → frame 2000 → air 300 → FPGA 50 → Ethernet 300 → host 300 → out 250 ≈ 3.5 ms single copy.

**Reliability story.** Receiver-side: deterministic FPGA timing, one sample clock, 12-bit dynamic range (~70 dB) with AGC in the LNA; antenna diversity by a second ADC/mixer channel (+£30). Air-side as the chosen scheme.

**Cost.** Hub: LNA/filter/mixer/LO £40 + ADC £10 + FPGA board £35 + PSU/case £30 + host £110 = £225 fixed (50 % over £150: tripwire assessment, but £0 per channel so 32 channels for £225 vs a £470 budget line). Pack unchanged. 32-channel ≈ £1,000.

**UK legality.** Receive-only; pack's legality as the air scheme. The LO must not radiate (shielded).

**What v1 code or analysis it reuses.** Pack side as the air scheme; v1's GFSK link analysis for demodulator design.

**Riskiest assumption** and the cheapest experiment. That a 32-channel GFSK demodulator with bit sync and framing fits an ECP5-25 and can be written and verified by this team (FPGA DSP is a specialist skill; the agents can write and simulate Verilog, but hardware-in-the-loop debugging of RF+FPGA is slow with a non-engineer owner). Experiment (< £120): AD9226 module + Colorlight i5 + a 2.4 GHz nRF52 DK transmitting into a mixer/LO module; demodulate one carrier in the FPGA first, then 8.

**Why it might be wrong.** It is a research project disguised as a receiver. Everything in it is doable and all of it takes months; a Pluto or AntSDR does the same for £180 today. The only reason to choose it is zero proprietary dependence and the lowest receiver latency.
