# Mounting the two rack antennas in the wings

Why: the 8 belt packs are quiet radios (that is the UK legal limit). Audience phones are loud. Each receive antenna therefore sits in a wing, high up, and looks across the stage and away from the audience. This page is the rule the system was designed and simulated with (docs/adr/0021). The margin is small (about 1.5 dB at the worst spot on stage), so set it up exactly as written. If you don't follow it, an actor can drop out when the house fills up. Numbers come from `python3 audit.py`, "Audit 7".

Time: about 1 hour, with the venue's lighting crew (they own the booms, stands and ladders).
Send back: the photos from step 13 and the result of step 14, attached to GitHub issue #92.

## What you need

| Item | What it looks like | Qty |
|---|---|---|
| L-com **HG2409P-NF** antenna | white flat square, 114 × 114 mm, 23 mm thick, with a short black cable ending in a round screw socket (N female) | 2 |
| L-com **CA3N050** cable | thick black coax, 15.2 m long, with the same large screw plug (N male) on both ends | 2 |
| L-com **LCCA30301-FT1.5** jumper | short thick cable (45 cm): a large screw socket (N female) on one end, a small push-and-twist plug (BNC) on the other | 2 |
| Mounting | an L-com HGX-PMT04 tilt-and-swivel bracket, **or** a theatre half-coupler with a 1/4-20 bolt (ask the lighting crew) | 2 |
| Something 4 m tall in each wing | the venue's **lighting boom** (an upright steel pipe in the wing), or a wind-up lighting stand that reaches 4 m | 2 |
| Safety bond | a steel safety cable for each antenna (the lighting crew has these) | 2 |
| Tape measure | at least 8 m long (or the venue's laser measure) | 1 |
| Phone | with a level or compass app that shows tilt in degrees (iPhone: Measure → Level; Android: any "bubble level" app) | 1 |
| Cable ties | about 20 | |

## The rule in one picture

Top view (audience at the bottom):

```
                         UPSTAGE (back wall)
        +----------------------------------------------+
        |  far upstage corner                          |
  WING  |  o <--------.               .-------->  o    |  WING
  stage |              \  beam  beam /                 |  stage
  left  |               \           /                  |  right
        |                \         /                   |
   [A]==|== 1 m          \_______/            1 m ==|==[B]   <- each antenna 1/4 of the way back,
        |  offstage                          offstage |         4 m up, aimed at the FAR UPSTAGE CORNER
        |                                              |
        +--------------- front edge of stage ----------+
                 AUDIENCE: behind and beside the beams

   No Wi-Fi router, hotspot or laptop anywhere in either wing or on stage.
   A backstage Wi-Fi router must be at least 6 m from both antennas.
```

Side view of one antenna:

```
      [#]  <- antenna face, 4 m above the stage floor, tilted down 10 deg
       |\
       | \   beam
 boom  |  \___________
 or    |              \______         actors walk under it:
 stand |                     \___     the 4 m height keeps every pack
 ------+-------------------------\--  at least 2.8 m from the antenna
       stage floor
```

## Steps

1. **Ask the venue's IT person one question:** "Is the house Wi-Fi on channels 1, 6 and 11 only, not 13? And is there a Wi-Fi router in the wings or backstage near the wings?" *Expected:* "yes, 1/6/11", and you have a list of any routers near the stage. If channel 13 is in use, ask them to move it to 1, 6 or 11 for show nights.
2. **Find the spot in stage-left wing.** Measure the stage depth: from the front edge of the stage to the back wall (or the last curtain). Divide it by 4. Go that far back from the front edge, and 1 m offstage of the edge of the acting area (the line where the side curtains or the proscenium edge are). *Expected:* a spot about 1.5–2.5 m back from the front of the stage, just behind the first side curtain. Write the distances down.
3. **Pick the mount.** Use the lighting boom nearest that spot (within 1 m is fine), or stand a wind-up lighting stand there. It has to hold the antenna **4 m above the stage floor** (anything from 3.7 m to 4.5 m is fine). *Expected:* the crew says the boom or stand reaches 4 m. If nothing reaches 3.7 m, see "If it didn't work".
4. **Fix the bracket to antenna A.** Bolt the bracket (or the half-coupler bolt) to the four holes on the back of antenna A, the side with no printing. *Expected:* the antenna does not wobble on the bracket.
5. **Mount antenna A** on the boom or stand with its centre 4 m above the stage floor, and clip a safety cable from the bracket around the pipe. *Expected:* measured from the stage floor to the middle of the white face, 3.7–4.5 m; the safety cable is tight around the pipe.
6. **Aim antenna A.** Turn the white face toward the **far upstage corner of the acting area**, the corner on the other side of the stage, nearest the back wall. It must never face the audience. *Expected:* standing in that far corner and looking back, you see the white face square-on.
7. **Tilt antenna A down 10°.** Hold your phone flat against the white face with the level app open, and tilt the bracket until the app reads 10° (face looking slightly down at the floor). Tighten the bracket. *Expected:* the app reads 5–15°, and the face looks just a little down, across the stage.
8. **Repeat steps 2–7 for antenna B** in the stage-right wing, aimed at the far upstage corner on the stage-left side. *Expected:* the two antennas face each other diagonally across the stage, both angled a little toward the back wall and a little down.
9. **Connect the long cables.** Screw the large plug of a CA3N050 onto the round socket on each antenna's short lead, finger-tight, no tools. *Expected:* the plug turns about 4 full turns and stops.
10. **Run each cable to the rack** down the boom or stand and along the wing wall, cable-tied every metre, never across the actors' path. *Expected:* nothing hangs or lies where an actor walks, and the free end reaches the rack. Each cable is 15.2 m long; if it doesn't reach, stop and post the distance on issue #92.
11. **Fit the short jumpers at the rack.** Screw each jumper's large socket onto a long cable's plug, finger-tight. *Expected:* it turns about 4 turns and stops.
12. **Plug into the rack.** Push the stage-left jumper's small BNC plug onto the rear socket labelled **ANT A**, the stage-right one onto **ANT B**, and turn each a quarter-turn clockwise until it clicks. *Expected:* neither comes off when you tug it gently.
13. **Take three photos:** (1) each antenna from the far upstage corner it points at; (2) one antenna from the side, showing the tilt and the boom; (3) the tape measure or laser reading of its height. *Expected:* three photos on your phone, attached to issue #92.
14. **Check the no-Wi-Fi zones.** Walk both wings and the stage, then everything backstage within 6 m of either antenna. Look for Wi-Fi routers (boxes with antennas or blinking lights), hotspots and laptops. *Expected:* none in the wings or on stage, and none within 6 m of an antenna. If the stage manager's desk is in a wing, its laptop runs on a cable with Wi-Fi off. During the show, crew in the wings keep their phones in **airplane mode** (Wi-Fi off is not enough: a phone's mobile signal near an antenna also crowds the receiver). Post "zones clear", or a list of what you found, on issue #92.
15. **Switch on the rack and all 8 packs.** *Expected:* all 8 lock lights on the front of the rack go solid within 2 seconds.

## If it didn't work

- **A pack drops out (its lock light flickers) once the audience is in, but not in rehearsal.** Most likely a router, hotspot or laptop is in a wing or within 6 m of an antenna, or an antenna has been turned toward the audience. Repeat steps 6 and 14 with the house full. If you can't clear it, the agents switch that pack to time diversity from the booth (ADR-0017: about 2 ms more delay, still under the 5 ms limit). Post on issue #92 which pack, where it was on stage, and the time.
- **Every channel is weak on one antenna** (packs lock only when they're close to it). Most likely a connector is loose or a cable is damaged. Re-tighten the three screw joints on that side (steps 9 and 11) and re-seat the BNC plug (step 12). **One thing to try:** swap the two BNC plugs at the rack (ANT A ↔ ANT B). If the problem moves to the other socket, the cable or antenna is at fault; if it stays, the rack is. Post which on issue #92.
- **Nothing in the wing reaches 3.7 m** (low studio grid, no booms). Use the highest mount you have, measure its height, and post it on issue #92. Never lower than 3.5 m: lower than that, with actors waiting in both wings, an actor walking past the antenna can drown out the packs next to it on the radio dial. The agents will rework the numbers; the most likely fix is time diversity for the packs worn by actors who wait in that wing.
