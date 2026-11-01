"""OpenPack bodypack enclosure (PK-5, PK-11). Run: python mech/pack.py -> mech/build/*.stl,*.step
PCB outline/height follow hw/pack/layout.py (#34); the parts above it are the per-part boxes in
hw/pack/out/fab/envelope.json (courtyard x datasheet height), so the interference test sees the real board. Edit parameters only.
Coords (mm): x length, y width, z up. Base floor at z=0; lid on top. Origin at plan-view centre."""
import cadquery as cq
from pathlib import Path

# ---- parameters -----------------------------------------------------------
L, W, WALL = 96.0, 62.0, 1.6              # outer plan size (PK-11: <= 100 x 65), wall
H_IN = 19.6                               # interior height; body = WALL + H_IN + WALL
Z_TOP = WALL + H_IN                       # top of walls / underside of lid
CELL_D, CELL_L = 18.5, 65.5               # 18650
HOLD_CLR, HOLD_END, HOLD_W = 0.25, 5.0, 21.0   # holder bore clearance, end block length, width
CELL_GAP_Z = 0.5                          # cell sits 0.5 above floor
# board beside the holder; notch clears the (-30, 26.9) lid post; z0 raised so the BT40NE antenna (overhanging
# x < -28) rides above the clip bosses (top z 6.0). Matches hw/pack/layout.py OUTLINE.
PCB = dict(x0=-28.0, x1=45.4, y0=-6.5, y1=28.5, z0=WALL + 3.4, t=1.6, comp_h=8.0, notch=(-26.5, 24.0))
ANTENNA = (-38.9, -28.0, 7.7, 22.7, 2.0)               # BT40NE antenna section past the board edge: x0,x1,y0,y1,h
# board retention: 2x M2 x 6 thread-forming screws through the PCB (hw/pack/layout.py MOUNT) into printed bosses;
# 2 plain rests. Boss wall (5.6 - 1.8) / 2 = 1.9 >= WALL; pilot 3.0 deep leaves 2.0 under it.
PCB_SCREWS, SCREW_BOSS_D, SCREW_PILOT_D, SCREW_PILOT_DEPTH = [(-25.0, -3.5), (36.0, 26.0)], 5.6, 1.8, 3.0
PCB_RESTS = [(-25.0, 25.5), (30.0, -3.5)]
CELL_X0 = -L / 2 + WALL + 0.2 + HOLD_END  # cell start; blocks flank it
JACK_D, JACK_Y, JACK_Z = 6.0, 0.0, PCB["z0"] + PCB["t"] + 5.2   # SJ1-3543 M6 bushing, axis 5.2 above the board
USB_W, USB_H, USB_Y, USB_Z = 9.0, 3.2, 18.0, PCB["z0"] + PCB["t"] + 1.6
RECESS = 0.8                              # USB-C mouth recess depth (pad inside keeps wall 1.6)
WHIP_XY, WHIP_D, WHIP_L = (42.5, 27.5), 0.9, 31.0   # PK-5: 31 mm quarter-wave wire
POSTS = [(-43.9, 26.9), (-30.0, 26.9), (43.9, -26.9)]  # M2 lid posts (4th corner is the whip)
LEDS = [(8.0, 20.0), (16.0, 20.0)]; LED_D = 2.5      # power/battery, peak/clip
# light pipes: chimneys from the lid down to 0.4 mm above the LEDs (bore LED_D, wall WALL); optional 2.5 mm acrylic rod
LED_TOP = PCB["z0"] + PCB["t"] + 0.8                 # LTST-C191 height 0.8
# SW1 (C&K JS102011SAQN, right angle) at (-3.5, 19.0): its actuator sticks out 2.0 mm towards -y (KiCad footprint
# F.Fab) and slides 1.5 mm along x. SW_ACT is the actuator in the "A" position. A printed fork (switch_ext) grips it
# and rises through the lid slot; prongs span 0.3-3.6 mm above the board because the actuator height is not pinned.
SW_ACT = dict(x0=-5.5, x1=-4.0, y0=15.2, y1=17.2, travel=1.5)
SW_BODY = (-8.0, 1.0, 17.2, 20.8, 3.5)                 # x0, x1, y0, y1, h
SWITCH = (-4.0, 16.05, 4.6, 2.3)                     # recessed slide-switch slot x,y,len,width
# printed PETG belt clip (separate part), 2x M2 screws into heat-set inserts in the back wall.
# Printed on its side (y up) so layers run along the spring arm; arm tapers 3 -> 2.4 mm, tip chamfer = lead-in lip.
CLIP_T, CLIP_W, CLIP_OPEN, CLIP_PLATE, CLIP_ARM, CLIP_TIP_T = 3.0, 20.0, 4.0, 28.0, 28.0, 2.4
CLIP_SCREWS = [(-32.0, -2.0), (-32.0, 12.0)]
INSERT_D, BOSS_D, BOSS_TOP = 3.2, 7.0, 6.0   # M2 heat-set insert hole, boss, boss top z (insert sits on the floor)
SNAP_T, SNAP_W, SNAP_LEN, BARB = 1.6, 8.0, 4.0, 0.6   # battery-door snap arms (2, on the window long sides)
DOOR_CLR = 0.1
OUT = Path(__file__).parent / "build"

# ---- helpers --------------------------------------------------------------
def box(x0, x1, y0, y1, z0, z1):
    return cq.Workplane("XY").box(x1 - x0, y1 - y0, z1 - z0, centered=False).translate((x0, y0, z0))

def cyl_x(d, x0, x1, y, z):
    return cq.Workplane("YZ").workplane(offset=x0).center(y, z).circle(d / 2).extrude(x1 - x0)

def teardrop_x(d, x0, x1, y, z):
    """horizontal hole along x with a 50 deg (from horizontal) roof: prints without support"""
    r = d / 2
    tip = cq.Workplane("YZ").workplane(offset=x0).polyline([(y - 0.766 * r, z + 0.643 * r), (y, z + 1.556 * r), (y + 0.766 * r, z + 0.643 * r)]).close().extrude(x1 - x0)
    return cyl_x(d, x0, x1, y, z).union(tip)

def house_x(w, h, x0, x1, y, z):
    """w x h rectangle centred on (y, z) with a 50 deg roof to a point"""
    a, b, rise = w / 2, h / 2, w / 2 * 1.19
    pts = [(y - a, z - b), (y + a, z - b), (y + a, z + b), (y, z + b + rise), (y - a, z + b)]
    return cq.Workplane("YZ").workplane(offset=x0).polyline(pts).close().extrude(x1 - x0)

def vcyl(d, x, y, z0, z1):
    return cq.Workplane("XY").workplane(offset=z0).center(x, y).circle(d / 2).extrude(z1 - z0)

# ---- parts ----------------------------------------------------------------
YC = -W / 2 + WALL + 0.2 + HOLD_W / 2           # cell axis y
ZC = WALL + CELL_GAP_Z + CELL_D / 2             # cell axis z
XR = L / 2                                      # +x outer wall face

def cell():
    return cq.Workplane("YZ").workplane(offset=CELL_X0).center(YC, ZC).circle(CELL_D / 2).extrude(CELL_L)

def holder():
    def blk(x0):
        b = box(x0, x0 + HOLD_END, YC - HOLD_W / 2, YC + HOLD_W / 2, WALL, ZC + 4.0)
        return b.cut(cyl_x(CELL_D + 2 * HOLD_CLR, x0 - 1, x0 + HOLD_END + 1, YC, ZC))
    return blk(CELL_X0 - HOLD_END).union(blk(CELL_X0 + CELL_L))

def pcb():
    p = PCB
    nx, ny = p["notch"]
    return box(p["x0"], p["x1"], p["y0"], p["y1"], p["z0"], p["z0"] + p["t"]).cut(
        box(p["x0"] - 1, nx, ny, p["y1"] + 1, p["z0"] - 1, p["z0"] + p["t"] + 1))

def antenna():  # module antenna section, overhanging the board edge
    x0, x1, y0, y1, h = ANTENNA
    z = PCB["z0"] + PCB["t"]
    return box(x0, x1, y0, y1, z, z + h)

ENVELOPE = Path(__file__).resolve().parents[1] / "hw" / "pack" / "out" / "fab" / "envelope.json"

def comps():
    """parts on the board: per-part boxes from the layout (J1 body clipped at the wall, J2 is usbc(), SW1 split into
    body + actuator); falls back to a coarse block if the layout outputs are missing"""
    import json
    p = PCB
    top = p["z0"] + p["t"]
    if not ENVELOPE.exists():
        return box(p["x0"] + 2, p["x1"] - 7, p["y0"] + 2, p["y1"] - 2, top, top + p["comp_h"])
    out = None
    for e in json.loads(ENVELOPE.read_text()):
        if e["h"] <= 0 or e["ref"] in ("J2", "SW1"):
            continue
        x1 = min(e["x1"], L / 2 - WALL) if e["ref"] == "J1" else e["x1"]
        b = box(e["x0"], x1, e["y0"], e["y1"], top, top + e["h"])
        out = b if out is None else out.union(b)
    x0, x1, y0, y1, h = SW_BODY
    a = SW_ACT
    out = out.union(box(x0, x1, y0, y1, top, top + h)).union(box(a["x0"], a["x1"], a["y0"], a["y1"], top + 0.5, top + 3.0))
    return out

def switch_ext():  # printed fork: prongs either side of the actuator, plate, stalk up through the lid slot
    a, top = SW_ACT, PCB["z0"] + PCB["t"]
    g, t = 0.15, WALL
    xl, xr = a["x0"] - g - t, a["x1"] + g + t
    xc = (a["x0"] + a["x1"]) / 2
    y0, y1 = a["y0"], a["y1"] - 0.3
    f = box(xl, a["x0"] - g, y0, y1, top + 0.3, top + 3.6).union(box(a["x1"] + g, xr, y0, y1, top + 0.3, top + 3.6))
    f = f.union(box(xl, xr, y0, y1, top + 3.6, top + 3.6 + t))
    return f.union(box(xc - 1.0, xc + 1.0, y0, y1, top + 3.6 + t, Z_TOP + WALL - 0.4))

def jack():  # M6 bushing from the body front (wall inner face) through the wall; body is in comps()
    return cyl_x(JACK_D, XR - WALL, XR + 0.9, JACK_Y, JACK_Z)

def usbc():
    return box(PCB["x1"] - 3, XR - RECESS, USB_Y - USB_W / 2, USB_Y + USB_W / 2, USB_Z - USB_H / 2, USB_Z + USB_H / 2)

def whip():
    return vcyl(WHIP_D, *WHIP_XY, Z_TOP, Z_TOP + WALL + WHIP_L)

def base():
    b = box(-L / 2, L / 2, -W / 2, W / 2, 0, Z_TOP).cut(box(-L / 2 + WALL, L / 2 - WALL, -W / 2 + WALL, W / 2 - WALL, WALL, Z_TOP + 1))
    for x, y in POSTS:
        b = b.union(vcyl(5.0, x, y, WALL - 0.1, Z_TOP)).cut(vcyl(1.8, x, y, Z_TOP - 8, Z_TOP + 1))
    p = PCB  # PCB rests (d4) and screw bosses (M2 thread-forming pilot)
    for x, y in PCB_RESTS:
        b = b.union(vcyl(4.0, x, y, WALL - 0.1, p["z0"]))
    for x, y in PCB_SCREWS:
        b = b.union(vcyl(SCREW_BOSS_D, x, y, WALL - 0.1, p["z0"])).cut(vcyl(SCREW_PILOT_D, x, y, p["z0"] - SCREW_PILOT_DEPTH, p["z0"] + 1))
    # +x wall: inner pad behind USB-C mouth, mouth recess outside, jack + usb openings
    b = b.union(box(XR - WALL - 0.8, XR - WALL + 0.1, USB_Y - 8, USB_Y + 8, WALL - 0.1, Z_TOP - 1.5))
    b = b.cut(house_x(14, 6, XR - RECESS, XR + 1, USB_Y, USB_Z))
    b = b.cut(house_x(USB_W + 0.6, USB_H + 0.6, XR - WALL - 1, XR + 1, USB_Y, USB_Z))
    b = b.cut(teardrop_x(JACK_D + 0.6, XR - WALL - 1, XR + 1, JACK_Y, JACK_Z))
    for x, y in CLIP_SCREWS:  # heat-set insert boss + M2 screw hole through the back wall
        b = b.union(vcyl(BOSS_D, x, y, WALL - 0.1, BOSS_TOP)).cut(vcyl(INSERT_D, x, y, WALL, BOSS_TOP + 1)).cut(vcyl(2.4, x, y, -1, WALL + 0.1))
    return b

def _window():
    return box(CELL_X0 - 0.25, CELL_X0 + CELL_L + 0.25, YC - 9.5, YC + 9.5, Z_TOP - 1, Z_TOP + WALL + 1)

def lid():
    l = box(-L / 2, L / 2, -W / 2, W / 2, Z_TOP, Z_TOP + WALL).cut(_window())
    for x, y in POSTS:
        l = l.cut(vcyl(2.4, x, y, Z_TOP - 1, Z_TOP + WALL + 1))
    l = l.cut(vcyl(1.6, *WHIP_XY, Z_TOP - 1, Z_TOP + WALL + 1))
    for x, y in LEDS:   # light-pipe chimney hanging from the lid, then the bore through both
        l = l.union(vcyl(LED_D + 2 * WALL, x, y, LED_TOP + 0.4, Z_TOP + 0.1))
        l = l.cut(vcyl(LED_D, x, y, LED_TOP, Z_TOP + WALL + 1))
    sx, sy, sl, sw = SWITCH
    return l.cut(box(sx - sl / 2, sx + sl / 2, sy - sw / 2, sy + sw / 2, Z_TOP - 1, Z_TOP + WALL + 1))

def door():  # tool-free battery door: plug in the lid window; two snap arms click under the lid, pry out with a fingernail
    c = DOOR_CLR
    x0, x1 = CELL_X0 - 0.25 + c, CELL_X0 + CELL_L + 0.25 - c
    d = box(x0, x1, YC - 9.5 + c, YC + 9.5 - c, Z_TOP, Z_TOP + WALL)
    xm = (x0 + x1) / 2   # arms on the long sides (clear of the round cell), centred along x
    for yo, sgn in ((YC - 9.5 + c, -1), (YC + 9.5 - c, 1)):
        arm = box(xm - SNAP_W / 2, xm + SNAP_W / 2, min(yo, yo - sgn * SNAP_T), max(yo, yo - sgn * SNAP_T), Z_TOP - SNAP_LEN, Z_TOP + 0.1)
        zb = Z_TOP - 0.3   # retention face 50 deg, lead-in 45 deg; arm flexes inward 0.6 mm
        prof = [(yo, zb), (yo + sgn * BARB, zb - BARB * 1.19), (yo, zb - BARB * 1.19 - BARB)]
        barb = cq.Workplane("YZ").workplane(offset=xm - SNAP_W / 2).polyline(prof).close().extrude(SNAP_W)
        d = d.union(arm).union(barb)
    return d

def clip():  # plate on the back wall, riser, tapered return arm; mouth opening CLIP_OPEN
    cx = CLIP_SCREWS[0][0]; yc = sum(y for _, y in CLIP_SCREWS) / 2
    xa, xb = cx - CLIP_PLATE / 2, cx + CLIP_PLATE / 2
    zt = -CLIP_T - CLIP_OPEN                  # arm top (belt side)
    zr = zt - CLIP_T                          # arm bottom at the root
    xt = xb - CLIP_ARM                        # arm tip
    prof = [(xa, 0), (xb, 0), (xb, zr), (xt, zt - CLIP_TIP_T), (xt, zt - 0.4), (xt + 1.5, zt), (xb - CLIP_T, zt), (xb - CLIP_T, -CLIP_T), (xa, -CLIP_T)]
    a = cq.Workplane("XZ").workplane(offset=-(yc + CLIP_W / 2)).polyline(prof).close().extrude(CLIP_W)
    for x, y in CLIP_SCREWS:   # teardrop (tip towards +y = up when printed on its side)
        r = 1.2
        a = a.cut(vcyl(2 * r, x, y, -CLIP_T - 1, 1)).cut(cq.Workplane("XY").workplane(offset=-CLIP_T - 1).polyline(
            [(x - 0.8 * r, y + 0.45 * r), (x - 0.766 * r, y + 0.643 * r), (x, y + 1.556 * r), (x + 0.766 * r, y + 0.643 * r), (x + 0.8 * r, y + 0.45 * r)]).close().extrude(CLIP_T + 2))
    return a

ENCLOSURE = dict(base=base, lid=lid, door=door)   # printed body (PK-11 envelope)
PRINTED = dict(ENCLOSURE, clip=clip, switch_ext=switch_ext)   # + clip and switch fork (outside PK-11 / inside the body)
INTERNALS = dict(cell=cell, holder=holder, pcb=pcb, comps=comps, jack=jack, usbc=usbc, whip=whip)   # comps holds the antenna (U1 box)

def parts():
    return {k: f() for k, f in {**PRINTED, **INTERNALS}.items()}

def export():
    OUT.mkdir(exist_ok=True)
    ps = parts()
    for k, v in ps.items():
        cq.exporters.export(v, str(OUT / f"pack_{k}.stl"), tolerance=0.02, angularTolerance=0.1)
    asm = cq.Assembly()
    for k, v in ps.items():
        asm.add(v, name=k)
    asm.save(str(OUT / "pack.step"))
    return ps

if __name__ == "__main__":
    export()
