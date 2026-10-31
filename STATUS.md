Phase: 1 of 6 (computer models: sound quality, radio losses, microphone amplifier)
Done since last update: sound compression options built (#12); microphone amplifier simulated and meets its noise and loudness limits (#15); Wi-Fi crowding numbers written down, mostly estimates because nobody has published measurements of a packed theater (#16); first dropout model (#14).
Next: the sound-quality contest picks the compression (#13, running), then the sound-quality-vs-Wi-Fi curve finishes #14. Then Phase 2 (firmware in the simulator).
Waiting on human: nothing
Risks: "No audible dropouts in a packed house" (R1) is borderline in the model. It passes only if the spare radio channel between Wi-Fi channels stays almost perfectly clean. The resend-each-sound-packet-later option (time diversity, about 2 ms extra delay) looks necessary. Phase 2 simulation decides; if it still fails there, I will ask you here with the closest achievable number.
