# 15. No base station at all: a fistful of £5 USB radio dongles and the laptop

**One sentence.** The "receiver" is 4-8 nRF52840 USB dongles (Nordic PCA10059 £10, Chinese nRF52840 dongles £3-6, or our own pack PCB without the audio parts) plugged into a powered USB hub on the laptop that already mixes the show, so the base station's fixed cost is a hub and a cable and there is no host computer to buy.

**How the air works.** Idea 01/02 TDMA (or 03 FHSS) unchanged. Each dongle is one hub radio on one carrier with its own beacon; the dongles agree on a common superframe by one of them acting as master and the others listening to its beacon over the air (they are 2 cm apart) or by a shared GPIO/sync wire inside the hub enclosure.

**How the receiver works.** USB full speed (nRF52840 has FS only: 12 Mbps, bulk transfers, 1 ms frames) is enough: one carrier's 5-7 mics × 68 bytes per 2 ms = 240 kB/s, comfortably one or two 64-byte packets per USB frame. The laptop (Linux, macOS, Windows) runs the host program: merge, conceal, present as a virtual audio device (Linux: ALSA loopback/PipeWire; macOS: a Core Audio plug-in; Windows: ASIO driver via a small bridge) and serve the booth UI on localhost. For venues that want a box, the same dongles plug into a £60 Pi 5 or a used thin client (£40), which then presents UAC2 to the mixing laptop. The nRF54L15 dongle variant would double the carrier capacity when it exists cheaply.

**Capacity maths.** As idea 01: 5-10 mics per dongle; 32 mics with repair = 7-13 dongles; a 10-port powered hub is £20. USB bandwidth is irrelevant (total ≈ 1.2 MB/s). Beyond 32: more dongles, more hubs; the band is the limit, not the host.

**Latency budget.** Codec 300 → frame 2000 → air 300 → dongle USB FS (≤ 1 ms frame + bulk scheduling) 500-1000 → laptop audio stack (PipeWire/Core Audio at 64-sample quantum: 1.3 ms at 48 kHz) 1300 → out 250 ≈ 4.7-5.2 ms single copy. The laptop's own audio buffer is the risk; a Pi-based box with its own DAC/UAC2 output instead removes the laptop stack from the measured path (P3 is measured to USB out).

**Reliability story.** Air-side as the scheme. Host-side: consumer USB hubs and laptops suspend ports, re-enumerate and run antivirus; the Pi variant is the reliable one for shows; the laptop-only variant is the £0 one for rehearsals. Dongle firmware watchdog resets re-enumerate in ~0.5 s (affects only that dongle's 5-7 mics: acceptable? P1 says a restart never affects other mics; it affects the mics on that carrier, so the superframe must reassign them, which it can within 1 s).

**Cost.** Pack as idea 01 (~£24; and if the dongle is our own pack PCB, the same board serves both roles, halving NRE). Hub: 8 dongles £40 + powered hub £20 + enclosure £10 = £70 fixed (half the budget), £0 host; with a Pi 5 box +£80. 32-channel ≈ £840-920.

**UK legality.** As the air scheme. Dongles with a module antenna radiate the beacon at ≤ 10 dBm; fine.

**What v1 code or analysis it reuses.** v1's host code (USB audio, UI) adapted; the nRF52840 Zephyr radio work; v1 pack hardware if the dongle is the pack PCB.

**Riskiest assumption** and the cheapest experiment. That 8 USB full-speed dongles behind a hub deliver frames to userspace with < 1 ms jitter on all three laptop OSs. Experiment (< £60): 4 Chinese nRF52840 dongles + hub; GPIO on one dongle at RX, host timestamps at read(); histogram.

**Why it might be wrong.** USB full speed and consumer hubs are the least deterministic transport on the board; a laptop running the show's QLab, the mixer software and the booth UI is a shared-resource lottery. It saves a £60-110 host at the cost of P1 exposure; the honest version keeps a small dedicated box, which is idea 01 with dongles instead of soldered modules.
