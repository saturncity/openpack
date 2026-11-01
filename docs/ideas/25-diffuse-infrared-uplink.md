# 25. Diffuse infrared uplink: no radio spectrum at all

**One sentence.** Theatres already send audio by infrared (assistive-listening systems from Sennheiser and Williams AV flood the house with 2.3/2.8 MHz-subcarrier IR); reverse it: each pack carries IR emitters, the rig carries photodiode receivers, and 32 mics share unlimited, unregulated optical bandwidth.

**How the air works.** 850-950 nm IR LEDs on the pack (shoulder/chest, wide-angle, 100-500 mW peak pulsed), on-off keying or 4-PPM at 1-4 Mbps per pack in TDMA (one wavelength, time slots) or simple FDM of subcarriers. Diffuse propagation (reflections off walls and floor, as IrDA-era 4 Mbps diffuse-IR LANs and the Sennheiser house systems rely on) so line of sight is not strictly required. Downlink by the same means from ceiling emitters, or by a cheap 2.4 GHz radio.

**How the receiver works.** 4-8 receiver heads (large-area PIN photodiodes with a daylight filter, transimpedance amplifier, comparator) on the lighting bars and proscenium, cabled to the host; selection combining across heads. Parts are pennies; the heads cost cable and rigging time.

**Capacity maths.** Optical bandwidth is effectively unlimited; the limit is the LED's modulation bandwidth (~10 MHz for cheap IR LEDs) and the receiver's SNR: 32 mics × 300 kbps = 10 Mbps aggregate in TDMA on one wavelength is at the edge; two wavelengths (850/940 nm with filters) relax it.

**Latency budget.** Optical ≈ 0; TDMA framing as idea 01; ≈ 3.5 ms.

**Reliability story.** Stage lighting: tungsten fixtures radiate enormous near-IR (a 1 kW profile is a 1 kW IR heater), saturating photodiodes unless the subcarrier/pulse scheme and AC coupling reject it; LED rigs are kinder. Bodies, costumes, hats and hands block IR far more than RF; an actor lying down facing upstage with a cloak over the pack is silent. Fog and haze scatter IR (helpfully, for diffuse links). Audience phones and Wi-Fi are irrelevant; TV remotes and IR assistive systems are co-channel.

**Cost.** Pack: IR LEDs + driver £2 + MCU £2.50 + codec/preamp £5 + power/jack/case £10 ≈ £20 ex cell. Receiver heads 6 × £10 + host £110 + cable £40 ≈ £210 fixed, £0 per channel.

**UK legality.** None for IR at these powers beyond eye-safety (IEC 62471; diffuse LEDs at 100 mW are fine).

**What v1 code or analysis it reuses.** Codec, UI, host.

**Riskiest assumption** and the cheapest experiment. Shadowing by the actor's own body and costume. Experiment (< £40): an IR LED on a vest driven at 1 Mbps PRBS, a photodiode receiver on a stand; move around a room under stage lighting and count errors.

**Why it might be wrong.** A wireless mic's one job is to work when the actor turns their back; IR is blocked by the actor's back. It is on the board because the rule says strange ideas are not pre-rejected, and because its parts cost nothing.
