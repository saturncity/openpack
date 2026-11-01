# 26. Near-field magnetic induction through a stage-floor loop (the hearing-loop in reverse)

**One sentence.** Theatres already have induction loops (audio-frequency magnetic fields for hearing aids) under the seats; lay a loop under or around the stage and have packs transmit low-frequency (100 kHz-10 MHz) magnetic-field signals that only the loop picks up, so the link is immune to everything in the RF bands and legal under the inductive-SRD rules.

**How the air works.** Near-field coupling at, e.g., 6.78 MHz ISM or the 13.56 MHz ISM band (EN 300 330, inductive, field-strength limits in dBµA/m at 10 m), or spread across 1-10 MHz with low field strength; each pack drives a small ferrite coil; 32 packs FDM on separate carriers of ~300 kHz each (needs ~10 MHz total: only possible under the general inductive limits, which are low) or TDMA on one carrier. The loop's near-field range is a fraction of a wavelength: at 10 MHz λ = 30 m, so a 10 m stage is within the near field of a loop around it.

**How the receiver works.** The loop cable (one turn of 1.5 mm² wire round the stage, £20) into a tuned amplifier and an ADC (a 24-bit audio ADC at 192 kHz for sub-100 kHz carriers, or an SDR's HF input for MHz carriers; an RTL-SDR in direct-sampling mode covers 0-14 MHz for £30). Host demodulates. Zero per-channel cost.

**Capacity maths.** Legal field strengths and the available inductive bands make ~10 Mbps aggregate implausible: the 13.56 MHz band is 14 kHz wide at high power (42 dBµA/m) and the generic 9 kHz-30 MHz allowance is -20 to 10 dBµA/m, enough for metres, not tens of metres, at hundreds of kbps. Realistic: a few mics at speech-grade bitrate. Not 32.

**Latency budget.** Continuous, ~1-2 ms including SDR buffers.

**Reliability story.** Immune to Wi-Fi, Bluetooth, phones; vulnerable to dimmers, LED drivers and switch-mode supplies (the loudest things in a theatre at 100 kHz-10 MHz), to the actor's distance and orientation relative to the loop (coupling falls as 1/r³), and to anything in the band's hearing-loop neighbours (the house loop itself at audio frequencies is below our carriers).

**Cost.** Pack ~£18 (coil driver replaces the radio). Receiver £30 SDR + loop £20 + host £110.

**UK legality.** EN 300 330 inductive SRDs; field strength at 10 m must be measured with a loop antenna (not a TinySA job).

**What v1 code or analysis it reuses.** Codec, UI, host.

**Riskiest assumption** and the cheapest experiment. That any legal field strength carries 300 kbps 10 m to a floor loop. Experiment (< £50): a signal generator/MCU driving a ferrite coil at 6.78 MHz, a one-turn loop on the floor into an RTL-SDR; measure SNR vs distance and orientation.

**Why it might be wrong.** Physics: near-field coupling falls off as the cube of distance and the legal field limits are set for RFID-range links. It is a hearing-aid technology; it will carry hearing-aid bandwidths over hearing-aid distances.
