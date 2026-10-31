Phase: 2 of 6 (firmware in the simulator)
Done since last update: Phase 1 finished. Sound compression picked (ADPCM-6): it scores 4.2–4.6 out of 5 on an automatic listening scale, above the 4.0 bar on every speech and singing clip. Microphone amplifier circuit meets its noise and loudness limits. Rack's control software started early (#28), with the channel plan for 8 packs spread across the three Wi-Fi channels.
Next: check the radio simulator covers what we need (#18), empty firmware app (#19), then the codec in C (#21) and the real radio timing (#22).
Waiting on human: nothing
Risks: "No audible dropouts in a packed house" (R1) is still borderline in the model. Time diversity (resending each sound packet a moment later, about 2 ms extra delay) clearly helps: with it, sound stays good up to about 25 % Wi-Fi load even in the worst case, versus 10 % without. The full simulation in Phase 2 decides; if it fails there, I will ask you here with the closest achievable number.
