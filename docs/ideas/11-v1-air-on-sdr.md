# 11. Keep v1's air interface, replace its 32 receivers with one SDR

**One sentence.** v1 died because one nRF5340 receiver radio per pack made the rack huge and expensive; keep its continuous GFSK streams and ADPCM frames unchanged and receive all of them with one wideband SDR plus a software channeliser, so the receiver count no longer scales with the pack count.

**How the air works.** As v1: 2.4 GHz, 1 Mbps or 2 Mbps GFSK, one carrier pair per pack (or one carrier with v1's second copy dropped in favour of FEC), 1 ms ADPCM frames, continuous transmission. The SDR sees 56-60 MHz at once (Pluto hacked bandwidth, AntSDR E200 up to 61 MHz [verify], LimeSDR Mini 30.72 MHz), so 25-30 1 Mbps carriers fit in one capture, 32 in two captures or one 2.4 GHz-wide SDR. The downlink v1 lacked is added with one nRF52840 beacon radio (£4), used to reassign carriers around Wi-Fi.

**How the receiver works.** One SDR (£160-220) + one mini PC or a used small-form-factor PC with a mid-range GPU (£150-250). ice9-bluetooth-sniffer demonstrates demodulating all 40 BLE channels (and many classic channels) at once from HackRF/USRP captures on commodity hardware; our 32 narrower, known-carrier demods are easier. Adding capacity = adding SDRs, not per-pack hardware.

**Capacity maths.** 32 carriers × 1.5-2 MHz = 48-64 MHz of the 83.5 MHz band: this is the problem v1 had and could not solve: with Wi-Fi channel 6 occupying 22 MHz of the middle, only ~60 MHz is clean, so 32 continuous 1 Mbps GFSK carriers do not fit with any margin. At 2 Mbps GFSK carrying 300 kbps, carriers can be ~700 kHz wide (the deviation shrinks with the data rate if a custom PHY is used), 32 × 700 kHz = 22 MHz; but nRF radios cannot run a 300 kbps GFSK mode at 2.4 GHz (minimum 1 Mbps on nRF52; 125/500 kbps coded PHY uses 1 MHz channels anyway). So capacity is 25-30 packs on a 60 MHz-clean band, fewer with more Wi-Fi.

**Latency budget.** Codec 300 → frame 1000 → air (continuous) ~400 → SDR + host transfer 500-1500 → demod 300 → out 250 ≈ 2.8-3.8 ms.

**Reliability story.** v1's own: static carriers are a liability under hopping interferers; the SDR at least sees the whole band and the new downlink can move carriers between numbers. Diversity: a second SDR RX port. Loss handling by FEC inside the frame rather than a second copy.

**Cost.** Pack: v1's £28-33 BOM minus the BT40NE module premium if a bare nRF52840 module is used: ~£26 ex cell. Hub: SDR £180 + PC £200 = £380 fixed (tripwire), £0 per channel. 32-channel ≈ £1,210.

**UK legality.** As v1: EN 300 328 non-adaptive continuous transmission at 100 % duty cycle forces ≤ 10 mW EIRP per pack (medium utilisation), which is v1's UK limitation and the reason its R1 margin was thin.

**What v1 code or analysis it reuses.** Everything on the pack: firmware, codec, pack hardware, bsim scenarios; the audit's capacity maths.

**Riskiest assumption** and the cheapest experiment. That 25-32 simultaneous GFSK demodulations run in real time on a £200 host within 1.5 ms of buffering. Experiment (< £200, tripwire-adjacent): a Pluto (£190) + two v1 packs (already designed; build on dev kits) + GNU Radio; measure loss and host latency.

**Why it might be wrong.** It keeps the two structural flaws the audit named (static carriers, 100 % duty cycle at 10 mW) and only fixes the receiver count; 32 carriers do not fit beside a Wi-Fi network; the SDR host is a PC with a GPU, not a £60 Pi. It is the comfortable idea, and comfort is not what the board is for.
