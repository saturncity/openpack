# OpenPack iteration 2 — market & technology-transfer research

Date: 2026-11-01. UK focus, GBP. Compiled by lead agent from own research (section 4) and four parallel sub-agent reports (sections 1, 2, 3). Every number carries a URL; items marked "unverified" / "*" / "n/p" (not published) / "n/v" (not verified) could not be confirmed from a primary source. Nothing under /home/lenzj/openpack was modified.

## 0. Headline findings

1. **Nobody sells a 32-channel 2.4 GHz mic system.** Consumer kits top out at 3-5 co-located sets (6-10 mics); pro 2.4 GHz tops out at 20 (Audio-Technica System 20 PRO). The 32-in-one-carrier systems (Sennheiser Spectera 64 ch / ~1 ms, Shure Axient Digital 2 ms) are UHF/1G4 WMAS, GBP thousands per channel. Cheapest consumer price is ~£19-45 per TX channel (Boya, DJI Mic Mini, Rode Micro), but those are 2-TX-to-1-RX islands with no venue-wide coordination.
2. **UK regulation just moved in OpenPack's favour: 1785-1805 MHz became licence-exempt on 29 April 2026** (IR 2030/35/3: 50 mW e.i.r.p. body-worn, 20 mW other; S.I. 2026/396). It is 20 MHz of clean spectrum with no Wi-Fi/Bluetooth/phones, but no cheap transceiver silicon tunes it; it needs an SDR or a mixer front-end. 2.4 GHz continuous GFSK stays capped at ~10 dBm by the 10 dBm/MHz PSD rule, but below 10 dBm there is no duty-cycle/LBT requirement at all.
3. **The "one SDR receives 32 mics" idea is technically demonstrated (ice9-bluetooth-sniffer channelizes 20-60 MHz into 2 MHz GFSK channels in real time) but not at <5 ms and not cheaply**: a 60 MHz-capable SDR is £500-900 (LimeSDR Mini 2 / bladeRF), PlutoSDR only streams ~4-5 MS/s continuously, and no SDR audio project below 5 ms latency exists. 32 x 2 MHz channels = 64 MHz, more than any hobby SDR.
4. **The cheap, proven path is TDMA on commodity 2 Mbps GFSK radios**: nRF52840 modules £6-12, nRF54L15 (4 Mbps proprietary mode, NCS 3.0) £5-10, nRF24L01+ £0.94. One 2 Mbps radio measures ~1.7 Mbps ESB throughput, so 32 x 64 kbps does not fit in one radio; a hub of 4-8 radios (£40-100) does. This is the architecture Sennheiser Spectera uses (one wideband TDMA carrier), scaled down.
5. **DECT (SpeechLine) is 19 ms / 20 ch; LE Audio is 30 ms; 5 GHz ESP32-C5 UDP floor is ~0.5 ms in a quiet lab but Wi-Fi CSMA under audience load is unsolved; 863-865 MHz is 2 MHz wide (useless for 32 digital channels).** DECT-2020 NR+ on nRF9151 (£77 DK, +21 dBm, 1880-1900 MHz licence-exempt, half-slot ~210 us) is the one genuinely novel transfer candidate but requires writing a MAC and has zero published audio precedent.

## 1. Cheapest existing 2.4 GHz digital wireless mic systems (UK, GBP inc VAT, fetched 2026-11-01)

| System (kit) | UK price | £/TX ch | Quoted latency | MAX sets in one room (critical) | Hopping | Chipset |
|---|---|---|---|---|---|---|
| Rode Wireless GO (Gen 3), 2TX+1RX | £169 (sale, was £189) https://www.guitarguitar.co.uk/product/241125432425027--rode-wireless-go-gen-3 | £84.50 | Rode: "near-zero", no ms in datasheet https://edge.rode.com/pdf/products/1485/Wireless%20GO%20III_Datasheet_08_FA.pdf ; reseller 3.5-4 ms (unverified) | **4 kits (4 RX / 8 TX)** https://help.rode.com/hc/en-us/articles/12443146600207 (same for GO II, Wireless PRO, ME); original GO: "up to eight systems" https://rode.com/en/products/wirelessgo | Series IV proprietary, "based on Wi-Fi technology", AES-128 | Not published; Amp Hour #636 could not ID it ("not nRF52833") https://theamphour.com/636-discovering-cursed-connectors |
| Rode Wireless Micro, 2TX+1RX | ~£75-90 (PriceRunner, undated) | ~£40-45 | not published | **not published** | Series IV | unknown |
| DJI Mic Mini, 2TX+1RX | £65 (Amazon via PriceSpy) https://pricespy.co.uk/s/dji-mini-mic/ | £32.50 | not published (orig. DJI Mic ~15 ms lab https://www.lensrentals.com/rent/dji-mic-wireless-microphone-kit) | not published for Mini; DJI Mic/Mic 2: **5 sets (10 TX)**, DJI forum staff https://forum.dji.com/thread-277969-1-1.html | GFSK 2 Mbps, 2400-2483.5 MHz, EIRP <20 dBm, BT 5.3 https://www.dji.com/uk/mic-mini/specs | BLE-PHY-class SoC implied (inference) |
| DJI Mic Mini 2 | £88.95-89 https://pricespy.co.uk/product.php?p=16543238 | £44.50 | n/p | n/p | as above | unknown |
| DJI Mic 2, 2TX+1RX+case | from £139 https://pricespy.co.uk/s/dji-mic-2-combo/ | £69.50 | n/p | 5 sets (forum) | 2.4 GHz + BT | unknown |
| DJI Mic 3 | £175-203 | £87-101 | n/p | n/p; 4 TX per RX, 8 RX per TX https://www.dji.com/uk/mic-3/faq | auto-hopping 2.4 + 5 GHz | unknown |
| Hollyland Lark M2 Combo | UK n/v; EUR 105 | ~£45 | "<20 ms" (listing, unverified) | **3 sets**, mics >=0.5 m apart (support, via forum) https://forum.hollyland.com/thread-253-1-1.html ; Lark 150: 7 sets https://www.hollyland.com/faq/how-to-set-them-up-when-multiple-sets-of-lark-150-are-used-at-the-same-place | GFSK, AFH | unknown |
| Lark M2S Combo | EUR 114 | ~£49 | n/p | n/p | 2.4 GHz AFH | unknown |
| Lark Max 2 (2TX) | ~£120 (EUR 279 / $279) | ~£120 | 20 ms max https://www.adorama.com/HLLARKMAX2U.html | n/p; 4 mics per RX (manual) | GFSK 2 Mbps AFH (manual) | unknown |
| Xvive U3 (1TX+1RX XLR) | £177 https://www.andertons.co.uk/xvive-wireless-microphone-system-24ghz | £177 | <5 ms | **6** (6 switchable channels; signal weakens at 6 sets) https://www.soundhouse.co.jp/en/contents/staff-blog/index?post=1072 | 6 fixed channels, no hopping | unknown |
| Sennheiser XSW-D Portable Lav Set | £255 https://www.scan.co.uk/products/sennheiser-xsw-d-portable-lavalier-set-24hz-75m-range-5-hours-battery-life | £255 | <4 ms, aptX Live | **5** https://www.markertek.com/product/xsw-dlavalierset/sennheiser-xsw-d-wireless-digital-lavalier-set-with-clip-on-lavalier-mic-3-5mm-transmitter-and-xlr-male-rx-li-ion | automatic | Qualcomm/CSR aptX SoC (inference) |
| Shure MoveMic Two (2TX) | £245 https://pricespy.co.uk/product.php?p=13344454 ; RX kit £311 | £123 | n/p | **n/p** | proprietary 2.4 GHz | unknown |
| Saramonic Blink 500 B2+ (2TX) | £136 RRP; older B2 £84 Scan | £68 (B2 £42) | ProX 8 ms https://www.saramonic.com/product/blink500prox ; B2 12 ms | **Blink 500 ProX: 18 TX per band** https://www.bhphotovideo.com/c/product/1748026-REG/saramonic_blink500proxb4_blink_500_prox_b4.html | auto hopping | unknown |
| Boya BY-V20 (2TX+1RX) | from £38 https://pricespy.co.uk/s/boya-boya/ | **£19** | n/p | BY-WM4 Pro: **8 systems**, >=5 m apart https://www.bhphotovideo.com/c/product/1572166-REG/boya_by_wm4_pro_k2_dual_channel_digital_wireless_microphone.html | - | unknown |
| Comica | UK price not found | - | - | n/p | - | - |
| Mackie EleMent Wave LAV | £157 https://www.scan.co.uk/products/mackie-element-wave-lavalier-microphone-system | £157 | n/p | **6** ("up to 6 Wave systems in the same area") | encrypted 2.4 GHz | unknown |
| Alto Stealth Wireless | - | - | - | **Not 2.4 GHz** - UHF 540-570 MHz, 16 presets https://www.altoprofessional.com/products/stealth-wireless | - | - |

Cheapest per channel: Boya ~£19/ch, DJI Mic Mini ~£32/ch, Blink 500 B2 ~£42/ch, Rode Wireless Micro ~£40-45/ch. **No sub-£100/ch system publishes more than 5 co-located sets (<=10 mics in one room)**; only Saramonic ProX (18) and Boya WM4 Pro (8) claim more.

Highest simultaneous counts claimed at 2.4 GHz (pro gear):

| System | Claim | Source |
|---|---|---|
| Audio-Technica System 20 PRO | **20 channels** (HD mode; 10 standard), 5 linked chassis | https://www.audio-technica.com/en-us/system-20-pro |
| Shure GLX-D+ dual band | 11 typical / 16 ideal with Frequency Manager; 2.4 GHz-only 9/11 (retailer, unverified) | https://www.shure.com/en-GB/products/wireless-systems/glx-d_plus |
| Line 6 XD-V75 | 14 | https://www.fullcompass.com/common/files/16987-XDV75SpecificationSheet.pdf |
| Audio-Technica System 10 / 10 PRO | 8; PRO 10 via 5 chassis | https://www.audio-technica.com/en-us/microphones/wireless-systems/line-series/system-10 |
| Saramonic Blink 500 ProX | 18 | B&H above |

**32-channel-capable 2.4 GHz mic system: none found.** Ceiling found is 20 (AT System 20 PRO). AT ES Wireless reaches 96 channels but is DECT 1.9 GHz. Sennheiser Spectera does 32 in one 6/8 MHz carrier but in UHF/1G4 (see 2e).

UK legality: all listed 2.4 GHz systems are CE/UKCA under EN 300 328 (IR 2030/7/1). Example: Rode Wireless GO II UKCA DoC cites EN 300 328 V2.2.2, 2.402-2.480 GHz, **10 mW**, 29 June 2021 https://edge.rode.com/pdf/products/812/Wireless%20GO%20II%20-%20UKCA%20Declaration%20of%20Conformity.pdf — i.e. the market leader runs at the 10 dBm PSD-limited level, same as OpenPack would.

Chipsets: no teardown or FCC filing publicly identifies the radio SoC of any product above. Confirmed Nordic designs in wireless mics: AnkerWork M650 (nRF5340) https://www.nordicsemi.com/Nordic-news/2023/08/AnkerWork-M650-wireless-microphone-employs-nRF5340-SoC ; Virscient LiveOnAir nRF5340 module claims sub-5 ms https://www.nordicsemi.com/Nordic-news/2023/10/Virscients-LiveOnAir-audio-solution-employs-nRF5340-SoC . DJI Mic Mini and Lark Max 2 both specify GFSK 2 Mbps (BLE-PHY class).

## 2. Technology-transfer candidates (sub-agent research, accessed 2026-11-01)

### (a) DECT / DECT-2020 NR+

| Item | Finding | Source |
|---|---|---|
| Classic DECT air interface | 10 ms frame, 24 slots (12 down/12 up), 1.152 Mbit/s GFSK, 10 carriers x 1.728 MHz in 1880-1900 MHz = 120 duplex 32 kbit/s channels; 250 mW peak / 10 mW average (EU) | https://en.wikipedia.org/wiki/DECT |
| Sennheiser SpeechLine DW (SL DW) | DECT TDMA/GFSK with back-channel; **19 ms latency** (Sennheiser FAQ); **up to 20 channels per room** (EU 1880-1900 MHz) | https://www.sennheiser.com/globalassets/digizuite/40479-en-2022_11_speechline_digital_wireless_system_specification_v3.2_en.pdf ; https://www.sennheiser.com/de-at/support/knowledge-base/speechline-digital-wireless-faq |
| SL DW UK price | SL Rack Receiver DW-3-EU **£509 inc VAT** (Thomann UK); SL MCR 4 DW-3 4-ch Dante rack **£2,857 inc VAT** (Stage Supply) = ~£714/ch receive side | https://www.thomann.co.uk/sennheiser_sl_rack_receiver_dw_3_eu.htm ; https://stagesupply.co.uk/product/sennheiser-speechline-sl-mcr-4-dw-3-multi-channel-receiver-dante-4ch-poe/ |
| Sennheiser AVX (DECT 1.9 GHz) | 19 ms latency; SK AVX-3 bodypack £339, SKM AVX-835-3 £419 (Scan); EKP AVX-3 receiver £424 inc VAT. "12 simultaneous systems" is a US-reseller claim — unverified | https://www.scan.co.uk/products/sennheiser-sk-avx-3-bodypack-transmitter-for-avx-digital-wireless-microphone-system ; https://stagesupply.co.uk/product/sennheiser-ekp-avx-3-uk-ultra-compact-avx-camera-receiver-1-9ghz/ |
| Nordic nRF9151 DECT NR+ | PHY-only firmware (ETSI TS 103 636-2/-3): **application must implement the MAC**; 1.728 MHz BW; up to 3.4 Mbps peak (DevZone: 2.4 Mbps practical firmware cap); +21 dBm on bands 1/2/9/22, +19 dBm band 4; subslot = half-slot, max 15 subslots/transmission; "designed for 1 ms latency" (design goal, not measured); no devices-per-cell figure published | https://docs.nordicsemi.com/r/bundle/ps_nrf9151/page/dect.html ; https://nrfconnectdocs.nordicsemi.com/ncs/latest/nrfxlib/nrf_modem/doc/dectphy.html ; https://devzone.nordicsemi.com/f/nordic-q-a/117969/dect-nr-power-class-and-bandwidth-data-rate/534401 |
| nRF9151-DK price | **£76.54 ex VAT (£91.85 inc)**, 263 in stock, DigiKey UK | https://www.digikey.co.uk/en/products/detail/nordic-semiconductor-asa/NRF9151-DK/24420446 |
| NR+ slot structure | 10 ms frame, 24 slots of 416.67 us; half-slot (~210 us) operation; Nordic modem needs ~1 slot gap between scheduled ops. audioXpress (2026) says NR+ targets mic->IEM <=4-5 ms but gives no measured latency or channel count | https://arxiv.org/pdf/2104.08549 ; https://audioxpress.com/article/dect-nr-a-wireless-solution-for-real-time-audio ; https://devzone.nordicsemi.com/f/nordic-q-a/128769/dect-nr-scheduling-latency-issues/570735 |
| Renesas/Dialog DA14495 (DECT) | "Active" but Renesas forum: **"no recommendation for DECT new designs"**; dev kit 0 stock / 168-day lead at Avnet | https://www.renesas.com/en/products/da14495 ; https://community.renesas.com/general/f/general---forum/52168/chipset-recommendation-for-new-dect-design |
| Wirepas 5G Mesh (NR+) | metering focus, broadcast only, separately licensed — not an audio candidate | https://wirepas.com/news/wirepas-unveils-general-availability-of-wirepas-5g-mesh |

Minimum DECT latency: one slot per 10 ms frame per direction -> >=10 ms framing + codec (SL DW/AVX land at 19 ms). NR+ half-slot (~210 us) scheduling could in principle reach low-ms, but only with a self-written MAC on nRF9151 — no published audio result. Note NR+ band 1 = 1880-1900 MHz (UK licence-exempt DECT band); band 9/22 frequencies unverified; 1785-1805 MHz is NOT an NR+ band.

### (b) BLE LE Audio / Auracast (nRF5340 Audio DK)
- Spec: max **31 CIS per CIG**; Nordic SDC: "no absolute maximum of BISes, CISes and ACLs", limited by memory/airtime; **tested only with 2 CIS / 2-3 BIS**; ISO interval 5 ms min. https://nrfconnectdocs.nordicsemi.com/ncs/latest/nrfxlib/softdevice_controller/doc/isochronous_channels.html . Nordic LE Audio application supports 2 streams.
- Latency: Nordic engineer estimate **"a little over 30 ms"** end-to-end; 10-15 ms "a stretch" with 7.5 ms frames. https://devzone.nordicsemi.com/f/nordic-q-a/85053/live-audio-streaming-latency-nrf5340
- No source found for many-to-one mic aggregation over ISO.
- nRF5340 Audio DK: **£128.94 ex VAT (£154.73 inc)**, DigiKey UK. https://www.digikey.co.uk/en/products/detail/nordic-semiconductor-asa/NRF5340-AUDIO-DK/16399476
- Verdict: LE Audio is a dead end for <5 ms (LC3 frame 7.5/10 ms + ISO scheduling), useful only as a reference for ISO-style scheduling.

### (c) UK PMSE bands - chipsets and products
(Regulatory detail is in section 4.)
- Chipsets: Si4463/SX1262/CC1101/nRF905 all tune 863-865 MHz, but 2 MHz at 10 mW gives roughly 8-10 x 200 kHz analogue-width channels -> nowhere near 32 digital mics.
- **1.8 GHz: no cheap general-purpose transceiver found.** Only DECT silicon exists near it (nRF9151 does 1880-1900 band 1, not 1785-1805). A wideband SDR (Pluto/Lime/bladeRF) or an RF mixer front-end on a 2.4 GHz chip would be needed to exploit 1785-1805 MHz. (Note by lead: a 2.4 GHz nRF/SX1280 transmitter + a cheap mixer down-converting by ~600 MHz is a plausible experimental route but was not found demonstrated anywhere - unverified.)
- Commercial 1.8 GHz / 2.4 GHz products: Sennheiser EW-D Y1-3 = 1785.2-1799.8 MHz https://www.sennheiser.com/globalassets/digizuite/40899-en-ew-d_y1-3_frequency_range_04_2021.pdf (UK price for Y1-3 not found; CH38 EW-D 835-S £539 inc VAT https://www.audiovolt.co.uk/products/sennheiser-ew-d-835-s-digital-wireless-handheld-microphone-system-ch38). Shure GLX-D+ 2.4/5.8 GHz: **11 typical / 16 ideal systems** with Frequency Manager, £599-659 https://www.guitarguitar.co.uk/product/230127399529027--shure-glxd24ukb58-z4-dual-band-handheld-system ; latency 4.5-8 ms (retailer figure https://www.adorama.com/shgd14z3.html — unverified vs Shure).

### (e) 5 GHz Wi-Fi and wideband-TDMA references
- ESP32-C5: dual-band Wi-Fi 6 (20 MHz 802.11ax, OFDMA + TWT), STA and SoftAP https://www.espressif.com/en/products/socs/esp32-c5 . DevKitC-1-N8R8 **£11.26**, Mouser UK https://www.mouser.co.uk/c/semiconductors/?q=esp32 ; Waveshare ESP32-C5 Mini £5.21-5.58. SoftAP cap **15 stations** (ESP_WIFI_MAX_CONN_NUM https://sourcevu.sysprogs.com/espressif/esp-idf/macros/ESP_WIFI_MAX_CONN_NUM) -> 32 mics need a real AP.
- Latency floors: raw UDP sendto->recvfrom on C5/C6 **540 +/- 200 us** in a quiet lab https://esp32.com/viewtopic.php?p=145855 ; modem-sleep adds up to ~300 ms unless disabled https://esp32.com/viewtopic.php?p=140883 ; DIY ESP32 mic projects report 80-500 ms (https://github.com/codehat01/esp32-voicelink ; https://www.hackster.io/chris-greening/esp32-walkie-talkie-f8d0dd). ESP-NOW ~600 kbit/s, 4-5 ms (peaks 10-12 ms) with ACK https://esp32.com/viewtopic.php?p=105674 . Caveat: these are quiet-room numbers; CSMA/CA under a packed auditorium's Wi-Fi is the unsolved issue - 5 GHz is far emptier than 2.4 GHz in a theatre but phones do use 5 GHz.
- WiSA HT: 5 GHz U-NII private network, **8 ch uncompressed 24-bit, 5.2 ms @48 kHz / 2.6 ms @96 kHz**, +/-2 us sync https://www.wisatechnologies.com/technology-products (proof that a private 5 GHz TDMA PHY can do <5 ms; WiSA modules are not sold to hobbyists).
- Sennheiser Spectera (WMAS): one 6/8 MHz carrier, **64 ch (32 in/32 out)**, **~1 ms mic latency, 0.7 ms IEM**, UHF or 1G4 https://www.sennheiser.com/en-dk/product-families/spectera ; https://sennheiser.com/globalassets/digizuite/49087-en-spectera-sek-product-specification-v1.4-en.pdf . Shure Axient Digital: **2 ms** (ADX1 2-2.9 ms) https://www.shure.com/en-gb/newsroom/shure-axient-digital-adx-wireless-transmitters-globally-available . These are the architecture to copy: ONE wideband carrier, TDMA, one base station.

### (f) Open-source projects (thin field)

| Project | Radio | Result |
|---|---|---|
| arduino-audio-tools nRF24 | nRF24L01+ 2 Mbps, no ACK | mono 16-bit 32 kHz, **~6.5 ms** (author) https://pschatzmann.github.io/arduino-audio-tools/structaudio__tools_1_1_n_r_f24_config.html |
| RF24Audio (TMRh20) | nRF24L01+ | 16-44 kHz sample rate depending on 250k-2 Mbps; AVR only; no latency figure https://github.com/nRF24/RF24Audio |
| Convergent Design Erika | nRF52833 ESB | commercial, 4 mics per hub, no latency given (Nordic news 2021) |
| Wi-Fi_IEM (thisven) | RPi RT-Linux/JACK over Wi-Fi | IEM over WLAN, latency unquantified https://github.com/thisven/Wi-Fi_IEM |
| Nordic DevZone | nRF52 | "no Nordic device reliably >1 Mbps raw at 100 m" https://devzone.nordicsemi.com/f/nordic-q-a/78822/uncompressed-audio-streaming |

No SX1280/Si4463/CC2500 audio project, no "openIEM", and no nRF5340 multi-stream mic-aggregation project surfaced.

**Not completed by sub-agent:** Sennheiser TeamConnect; nRF Audio presentation-delay values; NR+ band-9/22 frequency confirmation.

### (d) ONE wideband SDR receiver for 32 narrowband transmitters (sub-agent research, 2026-11-01; "*" = converted/unverified)

Hardware and UK prices (qty 1):

| Device | RX BW / rate, bits, bus | Price | 2.4 GHz? |
|---|---|---|---|
| RTL-SDR Blog V4 | 2.56 MHz stable, 8-bit, USB2; 500 kHz-1.766 GHz https://www.rtl-sdr.com/wp-content/uploads/2024/12/RTLSDR_V4_Datasheet_V_1_0.pdf | £81.60 kit https://thepihut.com/products/rtl-sdr-blog-v4-usb-dongle-with-dipole-antenna-kit | No - needs downconverter; 1 channel only |
| SDRplay RSP1B | 10 MHz, up to 2 GHz https://www.sdrplay.com/rsp1b/ | £105.80 ex VAT | No (2 GHz max) - BUT covers 1785-1805 MHz |
| Airspy Mini / R2 | 6 / 10 MHz, 12-bit, to 1.7/1.8 GHz | Mini £109.95 https://moonrakeronline.com/airspy-mini-sdr | No; Mini covers 1785-1805 MHz? (1.7 GHz max - no*) |
| HackRF One | 2-20 MS/s, 8-bit, half-duplex, USB2 https://hackrf.readthedocs.io/en/latest/hackrf_one.html | £328.60 inc, **discontinued** https://thepihut.com/products/great-scott-gadgets-hackrf-one-software-defined-radio | Yes (20 MHz = 10 x 2 MHz ch) |
| HackRF Pro | 20 MS/s 8-bit (40 MS/s @4-bit), USB-C https://greatscottgadgets.com/hackrf/pro/ | $400 https://www.sparkfun.com/hackrf-pro.html ; EUR 439 WiMo; GBP not found* | Yes |
| ADALM-PlutoSDR (AD9363) | 56 MHz bursts only; **~4-5 MS/s continuous over USB2** https://wiki.gnuradio.org/index.php/PlutoSDR_Source ; https://rtl-sdr.com/some-further-tests-with-the-adalm-pluto-sdr/ | $229.86 Digi-Key US; UK ~£200-230 inc* | Yes but continuous BW = 2 channels |
| Pluto+ clone (AD9363, GbE) | GbE-limited | ~$80-180 grey-market https://www.ebay.de/itm/395590561808 ; no UK stockist* | Yes |
| AntSDR E200 (AD9363, Zynq, GbE) | tens of MS/s | $299 campaign https://crowdsupply.com/microphase-technology/antsdr-e200 | Yes |
| LimeSDR Mini 2.0 | 30.72 MS/s, 40 MHz, 12-bit, USB3, ECP5 FPGA | $630 + $18 ship https://www.crowdsupply.com/lime-micro/limesdr-mini-2 ; ~£560 landed* | Yes (15-20 x 2 MHz ch) |
| LimeSDR USB | 61.44 MHz, 12-bit, USB3 | back on sale Mar 2025, price not found* | Yes (30 ch) |
| bladeRF 2.0 micro xA4 / xA9 | 61.44 MS/s, 12-bit, USB3; xA9 301 kLE FPGA | $540 / $860 https://www.nuand.com/shop/ ; EUR 649/899 Lab401; no UK stockist | Yes (30 ch) |
| USRP B205mini-i | 56 MHz, 12-bit, USB3 | £1,542.56 ex VAT https://www.digikey.co.uk/en/products/detail/ni/784417-01/18710219 | Yes |
| Ubertooth One | CC2400, 1 channel at a time; **retired** https://greatscottgadgets.com/ubertoothone/ | $119.95 | Single ch |

RTL-SDR 2.4 GHz downconverters: Ian Wraith mixer stack <£30 https://www.rtl-sdr.com/a-low-cost-2-4-ghz-downconverter-from-off-the-shelf-dev-boards/ ; modded DirecTV SUP-2400 https://www.rtl-sdr.com/a-demonstration-of-the-rtl-sdr-receiving-wifi-and-2-4-ghz-ism-with-a-modded-sup-2400-downconverter/ - all still cap at 2.4 MHz BW = 1 channel.

Prior art for multi-channel GFSK/BLE from one SDR:
- **ice9-bluetooth-sniffer** (Mike Ryan): polyphase channelizer "1 x 20 MHz -> 20 x 2 MHz", one thread per channel, 4-60 MHz on HackRF/USRP, all 79+40 channels on bladeRF 2.0; GPU FFT via VkFFT; "the channelizer will be the bottleneck"; no published CPU numbers. https://github.com/mikeryan/ice9-bluetooth-sniffer ; https://hardwear.io/talks/building-a-modern-bluetooth-sniffer/ . Strongest evidence that 20-40 x 2 MHz GFSK channels are real-time on a desktop.
- "One GPU to Snoop Them All" (Polimi/Edinburgh 2020): full BLE band GPU-channelized real-time https://re.public.polimi.it/handle/11311/1264923 (full text 403'd*).
- Lexfo bluesniff: HackRF 20 MHz, 7 BLE channels simultaneous before signal-quality problems https://blog.lexfo.fr/sniffing-ble-sdr.html
- BTLE (Jiao Xianjun) HackRF single channel https://github.com/JiaoXianjun/BTLE ; NRF24-BTLE-Decoder (RTL-SDR, nRF24/BLE adv) https://github.com/samyk/NRF24-BTLE-Decoder ; gr-nordic (Bastille) ESB decoder, single channel https://www.github.com/BastilleResearch/gr-nordic ; LimeSDR nRF24 decode "finicky" https://discourse.myriadrf.org/t/solved-difficulties-during-decoding-of-nrf24l01-protocol-with-limesdr/1798
- Sniffle is TI CC26x2 hardware, not SDR https://www.nccgroup.com/research/sniffle-a-sniffer-for-bluetooth-5/ . No published FPGA channelizer for bladeRF/LimeSDR found*; 64-ch PFB cost reference 1346 DSP48 on ZCU102 https://www.openresearch.institute/?p=3663

Sanity numbers (sub-agent arithmetic, unverified*):
- 32 x 2 Mbps GFSK at 2 MHz spacing = **64 MHz** -> exceeds every hobby SDR (bladeRF/LimeSDR USB 61.44 MHz = 30 ch). At 1 Mbps / 1 MHz spacing (32-40 MHz) it fits a LimeSDR Mini 2.0 or bladeRF; otherwise two SDRs.
- PFB channelizer at 64 MS/s, 8 taps: ~4-8 GFLOPS + 32 GFSK demods <1 GFLOPS - feasible on a mini-PC; on Pi 5 the risk is USB3 ingest (64 MS/s x 4 B = 256 MB/s); a Pi 4 froze at 10 MS/s with UHD https://lists.ettus.com/empathy/thread/7QB53I2QJWEAXPHQCZDJ4XX4TELRPITX ; no Pi 5 data.
- Latency: **no citable project doing <5 ms SDR audio**. LimeSDR FPGA packet 1020 samples, "performanceLatency=0" https://discourse.myriadrf.org/t/limesdr-streaming-buffers/2291 ; TX buffer->air 10-600 us https://discourse.myriadrf.org/t/tx-rx-round-trip-latency-and-coherence/2938 . GNU Radio default buffering adds several ms; <5 ms needs tiny buffers + RT thread + custom (non-GNU-Radio) pipeline.

Single-receiver TDMA alternative (one nRF radio time-slicing many TX):
- nRF52840 ESB fast ramp-up: TXEN/RXEN 130 -> **40 us** https://nrfconnectdocs.nordicsemi.com/ncs/latest/nrf/doxygen/html/structesb__config_afd2a90e82437adea039923ac717ee956.html ; ESB max **8 pipes** (CONFIG_ESB_PIPE_COUNT 1-8) https://developer.nordicsemi.com/nRF_Connect_SDK/doc/v1.6-branch/kconfig/CONFIG_ESB_PIPE_COUNT.html
- Measured ESB throughput at 2 Mbps / 252-B payload: **~1.7 Mbit/s** (theoretical 1.87) https://devzone.nordicsemi.com/f/nordic-q-a/120889/how-to-achieve-nrf52840-esb-maximum-data-rate/569953 . So **32 x 64 kbps = 2.05 Mbps does not fit one 2 Mbps radio**; with 5 ms frames (32 slots x 156 us incl. 40 us ramp) ~24 B/slot ~38 kbps/TX gross, zero retry margin. 4 Mbps (nRF54L15) roughly doubles this. Nordic: 2 Mbps audio "won't leave a lot of overhead for retransmissions" https://devzone.nordicsemi.com/f/nordic-q-a/48744/nrf24-audio-quality
- nRF24L01+ MultiCeiver: 6 pipes, one packet at a time; no multi-mic nRF24 audio hub project found; nRF24Z1 is 1:1. Practical hub = 4-8 nRF52840/nRF54L15 radios at ~£5-12 each (8 pipes / 4-8 mics each) rather than one SDR.

## 3. Cheap radio modules — UK prices (qty 1, ex VAT unless "inc"; DigiKey UK pages fetched 2026-11-01; "snip" = search snippet, +/-20 %)

| Part | UK price (qty 1) | Source | Max raw OTA | RX sens @ top rate | TX max | >=2 Mbps (1 ms frames) |
|---|---|---|---|---|---|---|
| nRF5340 DK | £36.58 | https://www.digikey.co.uk/en/products/detail/nordic-semiconductor-asa/NRF5340-DK/13544603 | 2 Mbps GFSK | -92 dBm @2M (https://docs.nordicsemi.com/r/bundle/ps_nrf5340/page/radio.html-unique_1119835464) | +3 dBm | Yes |
| nRF5340 Audio DK | £128.94 | https://www.digikey.co.uk/en/products/detail/nordic-semiconductor-asa/NRF5340-AUDIO-DK/16399476 | 2 Mbps | | +3 dBm | Yes |
| Fanstel BT40E / BT40F (nRF5340) | £12.08 / £12.52 | https://www.digikey.co.uk/en/products/result?keywords=BT40E | 2 Mbps | -92 dBm | +3 dBm | Yes |
| u-blox NORA-B106 (nRF5340) | £8.14 (8,519 stk) | https://www.digikey.co.uk/en/products/result?keywords=NORA-B106-00B | 2 Mbps | -92 dBm | +3 dBm | Yes |
| Raytac MDBT53-1M (nRF5340) | ~EUR 6.05 + ship (marketplace) | https://www.digikey.co.uk/en/products/detail/raytac/MDBT53-1M/16603005 | 2 Mbps | -92 dBm | +3 dBm | Yes |
| EBYTE E73-2G4M08S1C (nRF52840) | $7.59 (~£5.9) snip | https://lcsc.com/product-detail/C356849.html | 2 Mbps | -89 dBm @2M | +8 dBm | Yes |
| Holyiot 18010 (nRF52840) | $7-10 snip | https://www.aliexpress.us/item/2251832681687614.html | 2 Mbps | -89 dBm | +8 dBm | Yes |
| Seeed XIAO nRF52840 | £9.50 inc | https://thepihut.com/products/seeed-xiao-ble-nrf52840 | 2 Mbps | -89 dBm | +8 dBm | Yes |
| EBYTE E73-2G4M04S1B (nRF52832) | $4.59 snip | https://www.lcsc.com/product-image/C411306.html | 2 Mbps | -89 dBm | +4 dBm | Yes |
| nRF54L15 DK | £29.14 | https://www.digikey.co.uk/en/products/result?keywords=NRF54L15-DK | **4 Mbps** GFSK (proprietary) | -96 dBm @BLE 1M; 4 Mbps sens unverified | +8 dBm | Yes |
| Seeed XIAO nRF54L15 | £9.60 inc | https://thepihut.com/products/seeed-studio-xiao-nrf54l15 | 4 Mbps | | +8 dBm | Yes |
| Fanstel BM15E (nRF54L15) | £5.39 | https://www.digikey.co.uk/en/products/result?keywords=BM15E | 4 Mbps | | +8 dBm | Yes |
| nRF21540 FEM chip | £1.19 (qty 5-20) snip | https://uk.rs-online.com/web/p/rf-amplifiers-ics/2098055 | n/a | +13 dB LNA | +20 dBm PA | - |
| nRF21540 DB bundle | £65.19 | https://www.digikey.co.uk/en/products/result?keywords=nRF21540-DB | 2 Mbps | | +20 dBm | Yes |
| Fanstel BT840N (nRF52840+nRF21540) | £12.14 | https://www.digikey.co.uk/en/products/result?keywords=BT840N | 2 Mbps | -89 + LNA | +20 dBm | Yes |
| Fanstel BT840X (nRF52840+SKY66112) | £16.82 | https://www.digikey.co.uk/en/products/result?keywords=BT840X | 2 Mbps | -89 dBm | +20 dBm | Yes |
| ESP32-C5-DevKitC-1-N8R8 | £11.21 | https://www.digikey.co.uk/en/products/result?keywords=ESP32-C5-DEVKITC-1 | Wi-Fi 6 HE20; BLE 2M | BLE 2M -94.5 dBm; HE20 MCS0 -93 dBm (https://documentation.espressif.com/esp32-c5-wroom-1_wroom-1u_datasheet_en.pdf) | 19-20 dBm 2.4G; 16.5-18 dBm 5G | Yes |
| ESP32-C6-DevKitC-1-N8 | £6.72 | https://www.digikey.co.uk/en/products/result?keywords=ESP32-C6-DEVKITC-1 | Wi-Fi 6 (2.4 only); BLE 2M | | ~20 dBm | Yes |
| TI LP-CC2652R7 LaunchPad | £45.19 | https://www.digikey.co.uk/en/products/result?keywords=LP-CC2652R7 | 2 Mbps (BLE 2M) | -91 dBm @2M | +5 (R) / +20 dBm (P) | Yes |
| EBYTE E72-2G4M20S1E (CC2652P) | $5.43 snip | https://www.robotshop.com/products/ebyte-e72-2g4m20s1e-ebyte-cc2652p-24g-low-energy-ble-50-multi-protocol-wireless-communication-module-with-pcb-antenna | 2 Mbps | -91 dBm | +20 dBm | Yes |
| TI CC2500 module | £9.99 eBay snip | https://www.ti.com/product/CC2500 | 500 kbaud | | +1 dBm | No |
| TI CC1101 module | £4.89-5.99 eBay snip | | 600 kbps sub-GHz | | +10/12 dBm | No |
| Si4463 (E10 / RFM26W) | no UK price found | https://WWW.SILABS.COM/documents/public/data-sheets/Si4464-63-61-60.pdf | 1 Mbps | -126 dBm (low rate) | +20 dBm | No |
| EBYTE E28-2G4M12S (SX1280) | $6.40 snip | https://www.lcsc.com/product-image/C411310.html | GFSK 2 Mb/s; FLRC 1.3 Msym/s | GFSK 2M -83 dBm; FLRC 650 kb/s -100.5 dBm (https://mm.digikey.com/Volume0/opasdata/d220001/medias/docus/483/SX1280-81_Rev3.2_Mar2020.pdf) | +12.5 dBm | Marginal |
| EBYTE E28-2G4M27S (SX1280+PA) | $9.66 LCSC; £14.45 eBay UK snip | https://www.lcsc.com/product-image/C411312.html | same | same | +27 dBm (illegal above 20 dBm EIRP in UK) | Marginal |
| EBYTE E22-900M22S (SX1262) | $6.60 snip | https://www.lcsc.com/product-image/C411293.html | 300 kbps FSK | | +22 dBm | No |
| nRF24L01+ (10-pack) | £9.39 inc (£0.94 ea) | https://www.amazon.co.uk/AZDelivery-NRF24L01-2-4GHz-Wireless-Module/dp/B081JXY7KJ | 2 Mbps, 32 B payload, 6 pipes ESB | -82 dBm @2M | 0 dBm | Yes |
| nRF24L01+PA+LNA / E01-ML01DP5 | £8.99-9.99 inc per 2 / $3.21 | https://www.amazon.co.uk/nrf24l01/s?k=nrf24l01 | 2 Mbps | ~-82 + LNA | +20 dBm nominal | Yes |
| Si24R1 clone (E01C-ML01D) | ~£1 | https://www.robotshop.com/products/ebyte-e01c-ml01d-ebyte-smart-farm-low-cost-solution-si24r1-300m-small-size-dip-24g-wireless-rf-module-compatible-nrf24l01-module | 2 Mbps | -83 dBm @2M (secondary) | +7 dBm | Yes |

Notes
- **nRF54L15 4 Mbps**: hardware feature, proprietary only (not BLE). Nordic staff on DevZone: NCS **v3.0.0** `radio_test` exposes `nrf_4Mbit_BT04`/`nrf_4Mbit_BT06`; ESB supports `ESB_BITRATE_4MBPS` with 252-byte payloads; a user measured 2.35 Mbps ESB throughput. 4 Mbps sensitivity not found - unverified. https://devzone.nordicsemi.com/f/nordic-q-a/121320/how-to-verify-the-4mbps-transmission-mode-of-the-nrf54l15-series
- Part-number corrections: "Raytac MDBT54" does not exist (nRF54L15 line is AN54LQ/AN54LV); Fanstel nRF54L15 modules are BM15/BC15; EBYTE E104-BT54S is an ST chip; Fanstel nRF21540 parts are BT840N/BT840NE (nRF52840) and BT40N (nRF5340); BT840X/BT40X use SKY66112.
- TI CC8520/CC8530 PurePath Wireless: product pages say ACTIVE but datasheet is 2012, brokers list obsolete, no distributor price. https://www.ti.com/product/CC8520
- KleerNet KLR3012 status unverified (Microchip 403). LCSC audio SoCs (JieLi AC6925B4 $0.65, Actions/Airoha) are classic-BT A2DP parts, not low-latency raw-frame radios.
- Verdict: every Nordic nRF52/53/54 module, nRF24L01+/Si24R1, ESP32 and CC2652 qualify at >=2 Mbps. SX1280 only at GFSK 2 Mb/s with -83 dBm (9 dB worse than nRF52840); its headline sensitivity is at LoRa/FLRC rates far too slow for 1 ms frames. Best sensitivity-at-rate: nRF5340 (-92 dBm @2M). nRF54L15 4 Mbps gives most airtime headroom (halves slot length for a 32-slot TDMA).
- Mouser UK / Farnell UK blocked fetches; DigiKey UK served GBP pages.

## 4. UK rules recap (verified against primary texts, 2026-11-01)

### 2.4 GHz (2400-2483.5 MHz) — licence-exempt, EN 300 328 V2.2.2 (2019-07)
Source: ETSI EN 300 328 V2.2.2 text, https://www.etsi.org/deliver/etsi_en/300300_300399/300328/02.02.02_60/en_300328v020202p.pdf ; Ofcom IR 2030 v1.16 (April 2026; row IR2030/7/1, text seen in the 20 July 2026 draft) https://www.ofcom.org.uk/siteassets/resources/documents/consultations/category-3-4-weeks/consultation-expanding-access-to-the-6-ghz-band-for-commercial-mobile-and-wi-fi-services/main-document/draft-ir-2030-licence-exempt-short-range-devices-u6.pdf

| Parameter | Limit | Clause |
|---|---|---|
| Max e.i.r.p., FHSS or non-FHSS | 20 dBm (100 mW) | 4.3.1.2.3 / 4.3.2.2.3; IR2030/7/1 "100 mW e.i.r.p." |
| PSD, non-FHSS (wideband e.g. GFSK, Wi-Fi, LoRa-2.4) | 10 dBm / MHz e.i.r.p. | 4.3.2.3.3; IR2030/7/1 "10 mW/MHz e.i.r.p. when other types of modulation are used" |
| PSD, FHSS | 100 mW / 100 kHz | IR2030/7/1 |
| Medium Utilisation (non-adaptive, both FHSS & non-FHSS) | MU = (Pout/100 mW) x DC <= 10 % | 4.3.1.6 / 4.3.2.5.3 |
| MU / duty-cycle / adaptivity (LBT) requirements | DO NOT APPLY if declared e.i.r.p. < 10 dBm | 4.3.2.4.1, 4.3.2.5.1 |
| Occupied channel bandwidth, non-adaptive non-FHSS > 10 dBm | <= 20 MHz | 4.3.2.7.3 |
| Non-adaptive FHSS: hop count | N >= max(5, 15 MHz / hop separation), accumulated Tx time <= 15 ms per hop per 15 ms x N | 4.3.1.4.3.1 |
| Adaptive FHSS | must cover >= 70 % of band; 400 ms per hop | 4.3.1.4.3.2 |
| Receiver category | 0-10 dBm e.i.r.p. -> category 2 (relaxed blocking); 0 dBm -> category 3; adaptive >10 dBm -> category 1 | 4.2.3.2 |

Practical reading for a 1-2 MHz GFSK mic transmitter: a *continuous* non-hopping GFSK carrier of ~1 MHz bandwidth is capped by the 10 dBm/MHz PSD to about +10 dBm e.i.r.p. — and at <10 dBm the MU/duty-cycle/LBT rules vanish, so continuous 100 % duty-cycle transmission is legal. To get to 20 dBm you must either (a) spread to >=10 MHz occupied bandwidth (PSD rule) AND be adaptive (LBT/DAA) or keep MU <= 10 %, or (b) use FHSS with >= 15 hops at 1 MHz separation (non-adaptive FHSS, MU <= 10 %, i.e. 100 mW only at <= 10 % duty cycle; 20 mW allows 50 % duty). A 2.4 GHz theatre pack at 20 mW with 50 % TDMA duty and 15+ hop FHSS is compliant; so is a 10 mW continuous non-hopping link. Also a separate IR2030/26/5 row ("Wireless Audio Applications", 2400-2483.5 MHz, 10 mW e.i.r.p., EN 300 422) exists for audio-specific SRDs.

### 1785-1805 MHz (1.8 GHz PMSE) — NOW LICENCE-EXEMPT in the UK (since 29 April 2026)
- Ofcom statement "Updating Wireless Telegraphy Licence Exemptions", 27 Oct 2025, Table 4 and para 4.16/4.22: exempt Audio PMSE in 821.5-826 MHz (100 mW e.i.r.p. body-worn / 20 mW other), 826-832 MHz (100 mW e.i.r.p.), 1785-1805 MHz (50 mW e.i.r.p. for body-worn devices or devices implementing Spectrum Scanning Procedure (SSP); 20 mW e.i.r.p. for other devices); applies across the UK incl. Northern Ireland (para 4.22). https://www.ofcom.org.uk/siteassets/resources/documents/consultations/category-1-10-weeks/consultation-updating-wireless-telegraphy-licence-exemptions/main-document/statement-updating-wireless-telegraphy-exemptions.pdf
- Implemented as IR2030/35/1, /35/2, /35/3 (text extracted above) in IR 2030 v1.16 April 2026, brought into force by The Wireless Telegraphy (Exemption) (Amendment) (No. 2) Regulations 2026, S.I. 2026/396, made 8 April 2026, in force 29 April 2026 (regulation 4 points the 2021 Exemption Regulations at "IR 2030 ... published by OFCOM in April 2026"). https://lawplayer.com/uk/act/uksi-2026-396 (third-party mirror of legislation.gov.uk; official text not fetched — mark as "verify on legislation.gov.uk").
- Before April 2026 the band was covered by the UK Wireless Microphone (shared) licence and not usable in NI (Ofcom statement para 4.20). Wikipedia states "deregulated since May 2026" — slightly off vs the SI date. https://en.wikipedia.org/wiki/Wireless_microphone_licensing
- 20 MHz wide, no Wi-Fi/Bluetooth/phones in it (it is the LTE 1800 duplex gap; adjacent to LTE uplink 1710-1785 and downlink 1805-1880). Harmonised standard is EN 300 422 (wireless audio) — a digital 2 Mbps GFSK link would be assessed under EN 300 422 rather than EN 300 328.

### 863-865 MHz — licence-exempt
- IR2030/24/3, /33/1, /26/3: Radio microphones / Audio PMSE / Wireless Audio, 863-865 MHz, 10 mW e.r.p., EN 300 422 / EN 301 357; IR2030/1/13 non-specific SRD 863-865 MHz 25 mW e.r.p. with duty-cycle/LBT (EN 300 220). IR 2030 PDF as above.
- Ofcom licence-exempt page: 863-865 MHz "Transmitter power: 10mW", typically up to 4 frequencies used together (analogue 200 kHz channels). https://www.ofcom.org.uk/spectrum/radio-equipment/licence-exempt
- Only 2 MHz wide: not viable for 32 digital channels (a 2 Mbps GFSK channel is ~1-2 MHz wide) -> at most 1-2 digital links or ~8 narrowband ones.

### 2400-2483.5 MHz wireless mic specific
- IR2030/26/5 Wireless Audio Applications 2400-2483.5 MHz 10 mW e.i.r.p. (EN 300 422/EN 301 357); the generic WBDTS row (IR2030/7/1, EN 300 328) allows 100 mW e.i.r.p. subject to the PSD/MU rules above — most 2.4 GHz mic systems are certified under EN 300 328 as WBDTS.
- Ofcom's licence-exempt page says manufacturers claim up to 70 2.4 GHz frequencies in use together; transmitter power listed as 10 mW. https://www.ofcom.org.uk/spectrum/radio-equipment/licence-exempt

### DECT 1880-1900 MHz
- Licence-exempt across CEPT incl. UK; 250 mW (24 dBm) nominal peak, EN 301 406. CEPT ERC/DEC(98)22 https://docdb.cept.org/download/4449 . UK IR 2004 not fetched (unverified at primary-source level; DECT handsets are sold licence-free in the UK under the WT Exemption Regulations).

### 5 GHz
- IR2030/8/1a: 5150-5250 MHz WAS/RLAN (indoor; 200 mW e.i.r.p. in EN 301 893); IR2030/8/2 5470-5730 MHz 1 W / 50 mW/MHz with DFS; 5725-5850 MHz 25 mW SRD (IR2030/1/23) or IR 2007 FWA. IR 2030 PDF as above (row text only partially extracted; power values for 5150-5250 not quoted here — verify).
- IR2030/9/2: "Short Range Devices — Music and speech" 5725-5875 MHz 25 mW e.i.r.p., EN 300 440 (a wireless-audio SRD row at 5.8 GHz).

### Licence costs (if you choose a licensed band instead)
- UK Wireless Microphone Licence (shared; Channel 38 606.5-613.5 MHz): £75/yr online (£85 standard), £135/2 yr online (£155). https://www.ofcom.org.uk/manage-your-licence/radiocommunication-licences/pmse/pmse-licence-info (page dated 2015, copyright 2026 — fee current as displayed).
- Co-ordinated (site-specific interleaved UHF): per-frequency, minimum 48-hour rate; fee table on Ofcom's PMSE fees page (not fetched).

## 5. Gaps / could not verify
- Rode Wireless GO III ms latency, Rode Wireless Micro and DJI Mic Mini/Mic 3 co-location limits (not published by vendors).
- No chipset confirmed for any consumer 2.4 GHz mic (no public teardown); AnkerWork M650 and Virscient LiveOnAir are the only confirmed nRF5340 mic designs.
- nRF54L15 4 Mbps receiver sensitivity; nRF9151 NR+ band 9/22 frequencies; Sennheiser TeamConnect channel counts.
- HackRF Pro, PlutoSDR, LimeSDR USB, bladeRF UK GBP prices (no UK stockist found; USD/EUR given).
- Official legislation.gov.uk text of S.I. 2026/396 (third-party mirror used); the UK IR 2004 DECT text; Ofcom PMSE co-ordinated fee table.
- Mouser UK and Farnell UK blocked automated fetches; DigiKey UK, The Pi Hut, Scan, Andertons, Thomann UK served prices.
