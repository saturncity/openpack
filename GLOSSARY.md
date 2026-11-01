# Glossary

These terms are used verbatim in code, issues and ADRs; do not substitute synonyms.

- **frame**: One 1000 µs period (48 samples at 48 kHz, ±20 ppm) in which a pack sends copy A, retunes, sends copy B, then leaves a 300 µs RX slot idle (AIR-4).
- **copy A/B**: The two transmissions of the same frame in one frame period, copy A on channel A at t0 and copy B on channel B at t0+T_A+T_GAP; the receiver takes the first CRC-valid one. Avoid "packet 1/2", "primary/secondary".
- **carrier pair**: The two RF carriers (fA in 2402–2440 MHz, fB = fA + at least 40 MHz) assigned to one pack; one pair per pack, FDMA (SYS-6, AIR-5).
- **channel plan**: `host/channel_plan.yaml`, the single source of pack-id to carrier pair (API-3).
- **residual loss**: Fraction of frames where neither copy (nor the time-diversity copy, if on) arrives CRC-valid; gate is at most 0.1 % over 1 h under the Q3 interferers (laptop + 2 phones on Wi-Fi 1/6/11 at 2 m from the receiver, pack at 10 m). Avoid "packet loss" for this.
- **dropout event**: An audible gap: a run of ≥ 3 consecutive lost frames, which PLC cannot hide (ADR-0003); gate is at most 1 per hour and at most 2 consecutive lost frames (Q3, SYS-3). Avoid "glitch".
- **lock**: Receiver state in which it tracks the pack's frame timing (RX windows on A then B, ±50 µs) and its audio clock; reached at most 2 s after pack power-on (RX-2, RX-3, RX-7).
- **acquisition**: The search before lock, where the receiver holds RX open on channel A until it sees a CRC-valid packet with the configured address (RX-2).
- **time diversity**: Per-pack setting (`OP_TIME_DIVERSITY`, default off, ADR-0017; was build-time in ADR-0001) in which packet n also carries frame n-2. It adds 2000 µs latency (2.28 ms to 4.60 ms with DAC FLT=1) to survive Wi-Fi bursts in venues that break the install rule (Q1).
- **gap carrier**: A carrier ≥ 11 MHz from every Wi-Fi 1/6/11 centre (2423 2426 2448 2451 2473 2476 2479, and 2482 in UK/EU), so only the Wi-Fi skirt reaches it; every UK pack has one (AIR-5, ADR-0016). Avoid "clean channel".
- **install rule**: Where the two rack antennas go and what must stay away from them: one per wing, ¼ of the depth back, 4 m up, aimed at the far upstage corner and 10° down; no Wi-Fi in the wings or on stage, backstage Wi-Fi ≥ 6 m away (`docs/human/antenna-install.md`, ADR-0021, which replaced ADR-0016's front-of-stage rule). R1 at UK power rests on it.
- **PLC**: Packet loss concealment at the receiver: repeat the last frame with a 1 ms linear fade, mute after 10 ms of loss (RX-6).
- **jitter slot**: The fixed 200 µs output deadline after copy B ends in which the receiver decodes and releases a frame, so latency is constant (SPEC section 2).
- **twin**: The digital twin: the same Zephyr firmware built for BabbleSim `nrf5340bsim` with simulated Wi-Fi interferers and the real host software, run on a laptop and in CI; hardware only calibrates it (PLAN).
- **frame lead**: How long before the net core's payload latch (20 µs before TXEN, #98) the pack's audio frame clock ticks: 100 µs, the deadline for read + encode + IPC. Set once by the start-up sync (ADR-0020), then held by the lead loop on HFCLKAUDIO (ADR-0022). Avoid "latency margin".
