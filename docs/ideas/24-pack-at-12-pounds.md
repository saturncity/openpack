# 24. The £12 pack: MCU's own ADC, mic cable as antenna, module-only, no codec chip

**One sentence.** Strip the pack to a radio+MCU module, a two-transistor/one-op-amp mic preamp into the MCU's internal ADC, a USB-C charger chip and a jack, so that the pack costs ~£12 in parts and the project's cost ceiling moves from the radio to the case and the cell.

**How the air works.** Any scheme whose pack radio is a module (01-05, 22).

**How the pack works.** nRF52840 SAADC (12-bit, 200 ksps, differential, internal gain) oversampled 8× at 32 kHz gives ~13-14 effective bits and ~75 dB SNR after a low-noise preamp (OPA1692/MCP6V class, £0.50-1) with bias for electret/condenser mics (Sennheiser pinout: 3.5 mm TRS, 7.5 V bias through 4.7 kΩ on ring, audio on tip; a boost or the 18650's 3.7-4.2 V with a charge-pump gives the bias). No I2S codec, no MCLK, no second clock domain (which also simplifies idea 17). The lavalier cable's screen serves as a counterpoise/antenna element, as pro packs do (the module's PCB antenna remains the radiator; the cable improves its ground). Charging: TP4056 + DW01 protection (£0.50) off USB-C; battery gauge via the MCU's ADC. One PCB, two-layer, JLCPCB assembled at ~£3 each in 10s.

**Capacity, latency, reliability.** Unchanged from the air scheme; SAADC sampling is driven by the TDMA timer, so audio and radio share one timebase for free. 8-bit ADPCM from a 14-bit source is already the P8 quality target (8-bit ADPCM ≈ 12-13 bits of dynamic range), so the codec chip bought nothing audible. Risk: SAADC noise coupling from the radio's TX bursts (the whole system is on one die with one ground) must be measured, and 48 kHz is possible but 200 ksps caps oversampling at 4×.

**Cost.** Module £4 (nRF52840) or £3 (ESP32-C5) + preamp/bias £1.50 + charger/protection £1 + regulator £0.50 + jack £3 (locking Sennheiser-compatible; the single most expensive part) + switch/LED/passives £1 + PCB+assembly £3 ≈ £13-14 ex cell and case; with a printed case (£2) ≈ £16. Against a £30 budget this leaves £14 of margin for a better jack, a real codec if the SAADC fails the noise test, or a second radio (idea 22).

**UK legality.** The module's CE/RED pre-certification covers the radio; only the antenna arrangement (cable counterpoise) could change the EIRP and must be measured.

**What v1 code or analysis it reuses.** v1's preamp/bias design and jack choice; v1's codec is replaced by SAADC driver code.

**Riskiest assumption** and the cheapest experiment. SAADC noise floor with the radio transmitting. Experiment (< £40): nRF52840 DK, a preamp on a breadboard, record silence and a 1 kHz tone during 1 kHz TX bursts; FFT the result.

**Why it might be wrong.** A 12-bit SAADC is a microcontroller peripheral, not an audio ADC: its noise, non-linearity and sensitivity to supply ripple (the TX burst draws 15-25 mA steps) may put a buzz at the frame rate into every mic, which is the one artefact everyone recognises. The experiment is cheap and decisive.
