# Mounting the two rack antennas in a theatre

Why: the 8 belt packs are quiet radios (UK legal limit). The audience's phones are loud, so the two receive antennas must hear the stage and turn their backs on the audience. This page is the rule the system was designed and simulated with (docs/adr/0016). If the rule is not kept, actors can drop out when the house fills. Numbers come from `python3 audit.py`, "Audit 5".

Time: about 1 hour with the venue's lighting crew (they own the lighting bars and the ladder or lift).
Send back: the photos in step 13 and the result in step 14, attached to GitHub issue #92.

## What you need

| Item | What it looks like | Qty |
|---|---|---|
| L-com **HG2409P-NF** antenna | white flat square, 114 × 114 mm, 23 mm thick, short black cable ending in a round screw socket (N female) | 2 |
| L-com **CA3N050** cable | thick black coax, 15.2 m, the same large screw plug (N male) on both ends | 2 |
| L-com **LCCA30301-FT1.5** jumper | short (45 cm) thick cable, large screw socket (N female) on one end, small push-and-twist plug (BNC) on the other | 2 |
| Mounting | an L-com HGX-PMT04 tilt-and-swivel bracket, **or** a theatre half-coupler with a 1/4-20 bolt (ask the lighting crew) | 2 |
| Safety bond | a steel safety cable for each antenna (the lighting crew has these) | 2 |
| Tape measure | at least 8 m (or the venue's laser measure) | 1 |
| Cable ties | about 20 | |

## The rule in one picture

Side view (audience on the left, stage on the right):

```
                      antenna, >= 6 m above the stage floor,
                      tilted down ~45 deg, looking UPSTAGE
                         [#]\
 AUDIENCE                |   \   beam
 (phones)                |    \_______________
                         |     \              \___      ACTORS
  O O O O O              |      \                 \__   (packs)
  | | | | |  >= 4.5 m    |       \                   \   o   o
 ------------ from the --|----------------------------\--|---|------ stage floor
  stalls      antenna    | proscenium                    actors stay >= 4 m from the antenna:
                         |                               the 6 m height does this for you
```

Top view:

```
                     UPSTAGE (back wall)
   +-------------------------------------------------+
   |   no Wi-Fi router, hotspot or laptop within      |
   |   12 m IN FRONT of either antenna (wings too)    |
   |                                                  |
   |        ^ beam               beam ^               |
   |       /|\                       /|\              |
   |  [A] antenna A          antenna B [B]            |
   +--|-------------------------------------------|---+  <- proscenium / front lighting bar
      |  1 m in from each side                    |
      |                                           |
           AUDIENCE: every phone and the venue Wi-Fi
           >= 4.5 m from each antenna (behind or beside)
```

## Steps

1. **Ask the venue's IT person one question:** "Is the house Wi-Fi on channels 1, 6 and 11 only, not 13?" *Expected:* "yes". If they say 13 is used, ask them to move it to 1, 6 or 11 for show nights.
2. **Pick the bar.** With the lighting crew, choose the first lighting bar upstage of the proscenium (often called the "1st electric"). You need a bar that sits **at least 6 m above the stage floor** when it is at show height ("trim"). *Expected:* the crew tells you its trim height, and it is 6 m or more. No bar that high? See "If it didn't work".
3. **Measure the height.** Have the crew bring the bar to its show height, then measure from the stage floor to the bar. *Expected:* 6.0 m or more. Write the number down.
4. **Fix the bracket to antenna A.** Bolt the bracket (or half-coupler bolt) to the four holes on the back of antenna A, the side without the printing. *Expected:* the antenna does not wobble on the bracket.
5. **Hang antenna A** on the bar about 1 m in from the stage-left end of the proscenium opening, and clip a safety cable from the bracket around the bar. *Expected:* the antenna hangs from the bar, and the safety cable is tight around the bar.
6. **Aim antenna A.** Turn the flat white face so it looks **upstage**, at the actors, never at the audience. Tilt it **down about 45°**, so it looks at the middle of the stage floor. *Expected:* standing centre stage and looking up, you see the white face square-on.
7. **Repeat steps 4–6 for antenna B**, 1 m in from the stage-right end. *Expected:* both antennas look upstage and down, like two headlights pointed at the stage.
8. **Connect the long cable** to antenna A's short lead. Screw the large plug of a CA3N050 onto the round socket on the antenna's lead. Finger-tight only, no tools. *Expected:* the plug turns about 4 full turns and stops.
9. **Run the cable to the rack** along the bar and down with the lighting cables, cable-tied every metre. If the bar moves (flies), leave a loop as long as its travel. *Expected:* no cable hangs in the actors' path, and the free end reaches the rack. It is 15.2 m long: if it does not reach, stop and post the distance on issue #92.
10. **Fit the short jumper at the rack.** Screw the jumper's large socket onto the long cable's plug, finger-tight. *Expected:* it turns about 4 turns and stops.
11. **Plug into the rack.** Push the jumper's small BNC plug onto the rack's rear socket labelled **ANT A**, and turn it a quarter-turn clockwise until it clicks. *Expected:* it does not come off when you tug it gently.
12. **Repeat steps 8–11 for antenna B**, into the rear socket **ANT B**.
13. **Take three photos:** (1) each antenna from centre stage, looking up; (2) one antenna from the side, showing the tilt; (3) the tape measure or laser reading of the height. *Expected:* three photos on your phone, attached to issue #92.
14. **Check the 4.5 m and 12 m zones.** Walk the area within 4.5 m of each antenna: the edge of the stalls, any box seat, the side gallery or fly floor, and the prompt corner. Then walk the wings and back wall within 12 m in front. Look for Wi-Fi routers (boxes with antennas or blinking lights), hotspots and crew laptops. *Expected:* none found. Crew working in those zones (fly floor, follow-spot, prompt desk) keep their phones on **Wi-Fi off** during the show. Post "zones clear" or a list of what you found on issue #92.
15. **Switch on the rack and all 8 packs.** *Expected:* all 8 lock lights on the rack front go solid within 2 seconds.

## If it didn't work

- **A pack drops out (its lock light flickers) once the audience is in, but not in rehearsal.** Most likely a phone, hotspot or laptop is inside the 4.5 m zone, or something is transmitting within 12 m in front of an antenna. Repeat step 14 with the house full. If you cannot clear it, the agents switch that pack to time diversity from the booth (ADR-0017: about 2 ms more delay, still under the 5 ms limit). Post on issue #92 which pack, where it was on stage, and the time.
- **Every channel is weak on one antenna** (packs lock only when standing close). Most likely a connector is loose or the cable is damaged. Re-tighten the three screw joints on that side (steps 8 and 10) and re-seat the BNC (step 11). **One thing to try:** swap the two BNC plugs at the rack (ANT A ↔ ANT B). If the problem moves to the other socket, the cable or antenna is at fault; if it stays, the rack is. Post which on issue #92.
- **No bar is 6 m high** (studio or low grid). Use the highest bar or boom at the front of the stage, measure it, and post the height on issue #92. Do not aim the antennas at the audience to make up for it. The agents will rework the numbers. Most likely fix: keep actors further back from the antennas, and switch the packs nearest the front to time diversity.
