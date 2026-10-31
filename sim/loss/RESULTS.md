# sim/loss results (issue #14, evidence for ADR-0001)

Reproduce: `python3 sim/loss/traces.py` (about 2 s, fixed seed). Model: `audit.burst_loss` Gilbert-Elliott defaults
(mean burst 2 frames, p_bad 0.9, p_good 0.001), two independent channels, 3.6 M frames = 1 h.
Frame lost = both copies lost; time diversity (TD) also needs packet n+2 to fail (both copies).
Events/h = runs of >= 3 lost frames (ADR-0003 dropout).

| busy % | TD off: residual % | max run | events/h | TD on: residual % | max run | events/h |
|---|---|---|---|---|---|---|
| 5% | 0.214 | 6 | 257 | 0.012 | 4 | 11 |
| 10% | 0.828 | 8 | 972 | 0.051 | 6 | 38 |
| 15% | 1.844 | 7 | 2100 | 0.127 | 5 | 87 |
| 20% | 3.265 | 9 | 3776 | 0.257 | 7 | 151 |
| 25% | 5.094 | 8 | 6094 | 0.460 | 6 | 259 |
| 30% | 7.325 | 9 | 8661 | 0.762 | 7 | 337 |
| 35% | 9.977 | 10 | 11763 | 1.199 | 8 | 478 |
| 40% | 12.998 | 9 | 15423 | 1.836 | 7 | 618 |

ADR-0003 limits: residual <= 0.1 %, max run <= 2, <= 1 event/h.

Reading: TD cuts residual loss 15-18x and events/h 20-25x, but neither mode meets ADR-0003 at any busy
fraction from 5 % up. TD-on at 5 % busy still has 11 events/h and max run 4. So "off" fails SYS-3 everywhere,
and ADR-0001's rule (R1 outranks R3) means ship TD **on**; even then the committed busy fraction (#16) must be
below 5 %, or more protection is needed (more copies, FEC, a longer TD offset). The model is independent-channel
GE with audit.py's guessed parameters; #16 should replace them.

## PLC (RX-6) and quality curve

`sim/loss/plc.py`: repeat last good frame for 10 ms, the 11th lost frame fades it 1 -> 0 over 1 ms, then mute.
(Reading of "1 ms linear fade; mute after 10 ms": the fade is the last repeat before the mute.)

`python3 sim/loss/curve.py` runs codec + trace + PLC on two `say` speech clips and scores with
`sim/quality.visqol` (issue #13). ViSQOL curve: pending until `sim/quality.py` is on main; the script
already writes the degraded WAVs to `sim/loss/out/` (gitignored). ADPCM-6 is the only codec that fits with TD.
