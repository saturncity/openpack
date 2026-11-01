"""Pack board vs enclosure fit, without CadQuery (it is not on every machine; tests/mech/test_pack_fit.py does the
same check with CadQuery solids when it is installed).

    python3 hw/pack/fit.py      -> prints the checks, writes hw/pack/out/fit.json and out/render/fit_{top,side}.png

Inputs: mech/pack.py parameters (read with a stub `cadquery` module when the real one is missing),
hw/pack/layout.py OUTLINE, hw/pack/out/fab/envelope.json (per-part courtyard x height boxes).
Boxes are axis-aligned; posts, bosses and standoffs are cylinders. Frame: mech/pack.py (mm, z up).
"""
import json, math, pathlib, sys, types

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUT = HERE / "out"


def load_mech():
    try:
        import cadquery  # noqa: F401
    except ImportError:
        sys.modules["cadquery"] = types.ModuleType("cadquery")
    sys.path.insert(0, str(ROOT / "mech"))
    import pack
    return pack


def box_overlap(a, b, tol=0.0):
    return all(a[i] + tol < b[i + 3] and b[i] + tol < a[i + 3] for i in range(3))


def circle_box(cx, cy, r, b):
    qx = min(max(cx, b[0]), b[3]); qy = min(max(cy, b[1]), b[4])
    return math.hypot(qx - cx, qy - cy) < r


def checks():
    m = load_mech()
    sys.path.insert(0, str(HERE))
    import layout, footprints
    P = m.PCB
    top = P["z0"] + P["t"]
    env = json.loads((OUT / "fab" / "envelope.json").read_text())
    inner = (-m.L / 2 + m.WALL, -m.W / 2 + m.WALL, m.WALL, m.L / 2 - m.WALL, m.W / 2 - m.WALL, m.Z_TOP)
    res, fail = {}, []

    def ok(name, cond, detail=""):
        res[name] = {"ok": bool(cond), "detail": detail}
        if not cond:
            fail.append(f"{name}: {detail}")

    # 1. outline agrees with mech
    xs = [p[0] for p in layout.OUTLINE]; ys = [p[1] for p in layout.OUTLINE]
    ok("outline_matches_mech", (min(xs), max(xs), min(ys), max(ys)) == (P["x0"], P["x1"], P["y0"], P["y1"])
       and layout.NOTCH == P["notch"], f"layout {min(xs), max(xs), min(ys), max(ys)} mech {P['x0'], P['x1'], P['y0'], P['y1']}")
    board = (P["x0"], P["y0"], P["z0"], P["x1"], P["y1"], top)
    # solids the board and parts must miss
    hx0 = m.CELL_X0 - m.HOLD_END; hx1 = m.CELL_X0 + m.CELL_L + m.HOLD_END
    holder = (hx0, m.YC - m.HOLD_W / 2, m.WALL, hx1, m.YC + m.HOLD_W / 2, m.ZC + 4.0)
    cell = (m.CELL_X0, m.YC - m.CELL_D / 2, m.ZC - m.CELL_D / 2, m.CELL_X0 + m.CELL_L, m.YC + m.CELL_D / 2, m.ZC + m.CELL_D / 2)
    usb_pad = (m.XR - m.WALL - 0.8, m.USB_Y - 8, m.WALL, m.XR - m.WALL + 0.1, m.USB_Y + 8, m.Z_TOP - 1.5)
    cyls = [("post", x, y, 2.5, m.WALL, m.Z_TOP) for x, y in m.POSTS] + \
           [("clip boss", x, y, m.BOSS_D / 2, m.WALL, m.BOSS_TOP) for x, y in m.CLIP_SCREWS]
    nx, ny = P["notch"]

    def in_notch(b):
        return b[0] < nx and b[4] > ny

    def solid_hits(b, skip_wall_x=False):
        hits = []
        if box_overlap(b, holder):
            hits.append("holder")
        if box_overlap(b, cell):
            hits.append("cell")
        if box_overlap(b, usb_pad) and not skip_wall_x:
            hits.append("usb wall pad")
        for name, x, y, r, z0, z1 in cyls:
            if b[2] < z1 and b[5] > z0 and circle_box(x, y, r, b):
                hits.append(f"{name} ({x}, {y})")
        if not skip_wall_x and (b[0] < inner[0] or b[3] > inner[3]):
            hits.append("x wall")
        if b[1] < inner[1] or b[4] > inner[4]:
            hits.append("y wall")
        if b[5] > inner[5]:
            hits.append("lid")
        if b[2] < inner[2]:
            hits.append("floor")
        return hits

    # board slab: split around the notch (box minus notch corner)
    slabs = [(P["x0"], P["y0"], P["z0"], P["x1"], ny, top), (nx, ny, P["z0"], P["x1"], P["y1"], top)]
    ok("board_clear", not any(solid_hits(s) for s in slabs), str([solid_hits(s) for s in slabs]))
    ant = m.ANTENNA
    ab = (ant[0], ant[2], top, ant[1], ant[3], top + ant[4])
    ok("antenna_overhang_clear", not solid_hits(ab), str(solid_hits(ab)))
    ok("antenna_overhang_ge_9.8mm", ant[1] - ant[0] >= 9.8, f"{ant[1] - ant[0]:.1f} mm past the board edge (Fanstel p.20: 9.8)")
    bad = {}
    tallest = (None, 0)
    for e in env:
        b = (e["x0"], e["y0"], top, e["x1"], e["y1"], top + e["h"])
        through = e["ref"] in ("J1", "J2")      # these pass through the +x wall openings: checked below
        if through:
            b = (b[0], b[1], b[2], min(b[3], inner[3]), b[4], b[5])
        h = solid_hits(b, skip_wall_x=through)
        if e["ref"] == "U1":   # module body = pad section on the board; the antenna part is checked above
            b2 = (max(b[0], P["x0"]), b[1], b[2], b[3], b[4], b[5])
            h = solid_hits(b2)
        if h:
            bad[e["ref"]] = h
        if top + e["h"] > tallest[1]:
            tallest = (e["ref"], top + e["h"])
    ok("parts_clear", not bad, json.dumps(bad))
    ok("lid_clearance", inner[5] - tallest[1] >= 1.0, f"tallest {tallest[0]} top z {tallest[1]:.1f}, lid underside {inner[5]:.1f}")
    # connectors in their wall openings (jack axis from the SJ1-3543 drawing, USB-C centre 1.6 mm above the board top)
    j1 = next(e for e in env if e["ref"] == "J1")
    j2 = next(e for e in env if e["ref"] == "J2")
    axis = top + footprints.JACK["AXIS"]
    front = layout.PLACE["J1"][0]
    ok("jack_in_opening", abs((j1["y0"] + j1["y1"]) / 2 - m.JACK_Y) < 0.3 and abs(m.JACK_Z - axis) < 1e-6
       and abs(front - (m.L / 2 - m.WALL)) < 0.05 and footprints.JACK["BUSHING"] > m.WALL + 1.5,
       f"jack y {(j1['y0'] + j1['y1']) / 2:.2f} vs JACK_Y {m.JACK_Y}; axis z {axis:.2f} vs JACK_Z {m.JACK_Z:.2f}; "
       f"body front x {front} on the wall face; bushing {footprints.JACK['BUSHING']} through a {m.WALL} wall (nut needs ~1.5)")
    usb_y = (j2["y0"] + j2["y1"]) / 2
    USB4105_BODY_W = 8.94   # GCT USB4105 shell width (courtyard is wider: it includes the shield tabs inside)
    ok("usb_in_opening", abs(usb_y - m.USB_Y) < 0.3 and USB4105_BODY_W <= m.USB_W + 0.6
       and abs(m.USB_Z - (top + 1.6)) < 1e-6, f"usb y {usb_y:.2f} vs USB_Y {m.USB_Y}; mouth z {top + 1.6:.2f} vs USB_Z {m.USB_Z:.2f}")
    # lid features over the parts
    pos = {e["ref"]: ((e["x0"] + e["x1"]) / 2, (e["y0"] + e["y1"]) / 2) for e in env}
    led_ok = all(min(math.hypot(pos[r][0] - x, pos[r][1] - y) for x, y in m.LEDS) <= 1.2 for r in ("D1", "D2", "D3", "D4"))
    ok("leds_under_lid_holes", led_ok, str({r: pos[r] for r in ("D1", "D2", "D3", "D4")}))
    # switch fork: actuator (from the KiCad footprint at SW1's placement) inside the fork, stalk travel inside the slot
    sx, sy, sl, sw = m.SWITCH
    a = m.SW_ACT
    swx, swy, swr = layout.PLACE["SW1"]
    act_ok = swr == 0 and abs(a["x0"] - (swx - 2.0)) < 1e-6 and abs(a["x1"] - (swx - 0.5)) < 1e-6 and abs(a["y0"] - (swy - 3.8)) < 1e-6
    xc = (a["x0"] + a["x1"]) / 2
    travel = (xc - 1.0, xc + 1.0 + a["travel"])
    ok("switch_fork_on_actuator", act_ok, f"SW1 at {layout.PLACE['SW1']}, SW_ACT {a}")
    ok("switch_stalk_in_slot", sx - sl / 2 < travel[0] - 0.2 and sx + sl / 2 > travel[1] + 0.2 and
       abs(sy - (a["y0"] + a["y1"] - 0.3) / 2) < 0.05, f"stalk x {travel[0]:.2f}..{travel[1]:.2f} in slot {sx - sl / 2:.2f}..{sx + sl / 2:.2f}")
    fork = [(a["x0"] - 1.75, a["y0"], top + 0.3, a["x0"] - 0.15, a["y1"] - 0.3, top + 3.6),
            (a["x1"] + 0.15, a["y0"], top + 0.3, a["x1"] + 1.75, a["y1"] - 0.3, top + 3.6),
            (a["x0"] - 1.75, a["y0"], top + 3.6, a["x1"] + 1.75, a["y1"] - 0.3, m.Z_TOP)]
    hits = sorted({e["ref"] for e in env for f in fork if e["ref"] != "SW1" and e["h"] > 0
                   and box_overlap(f, (e["x0"], e["y0"], top, e["x1"], e["y1"], top + e["h"]))})
    ok("switch_fork_clear", not hits, str(hits))
    # light-pipe chimneys: from the lid down to LED_TOP + 0.4, outer d LED_D + 2 WALL
    r = m.LED_D / 2 + m.WALL
    hits = sorted({e["ref"] for e in env for x, y in m.LEDS if e["h"] > 0 and top + e["h"] > m.LED_TOP + 0.4
                   and circle_box(x, y, r, (e["x0"], e["y0"], 0, e["x1"], e["y1"], 0))})
    ok("light_pipes_clear", not hits and abs(m.LED_TOP - (top + 0.8)) < 1e-6, str(hits))
    res["light_pipe_bore_mm"] = round(m.Z_TOP + m.WALL - m.LED_TOP, 1)
    # board retention: screw bosses under the layout's M2 holes
    ok("screws_match_layout", sorted(m.PCB_SCREWS) == sorted(layout.MOUNT.values()), f"mech {m.PCB_SCREWS} layout {layout.MOUNT}")
    # THT legs (1.6 mm below the board) vs the PCB standoffs
    so = [(x, y, 2.0) for x, y in m.PCB_RESTS] + [(x, y, m.SCREW_BOSS_D / 2) for x, y in m.PCB_SCREWS]
    legs = [(r, x, y) for r, x, y in _tht_pads()]
    near = [(r_, x, y) for r_, x, y in legs for sx_, sy_, rr in so if math.hypot(x - sx_, y - sy_) < rr + 1.1]
    ok("tht_legs_clear_standoffs", not near and P["z0"] - 1.6 > m.WALL, str(near))
    ufl = (-25.1, 9.9, top + 2.0)
    wb = (m.WHIP_XY[0], m.WHIP_XY[1], m.Z_TOP)
    res["ufl_to_whip_straight_mm"] = round(math.dist(ufl, wb), 1)
    res["board_mm"] = [round(P["x1"] - P["x0"], 1), round(P["y1"] - P["y0"], 1)]
    res["fail"] = fail
    return res, m, env


def _tht_pads():
    try:
        import pcbnew as Pn
    except ImportError:
        return json.loads((OUT / "fit.json").read_text()).get("_tht", []) if (OUT / "fit.json").exists() else []
    b = Pn.LoadBoard(str(HERE / "pack.kicad_pcb"))
    out = []
    for fp in b.GetFootprints():
        for p in fp.Pads():
            if p.GetAttribute() == Pn.PAD_ATTRIB_PTH:
                q = p.GetPosition()
                out.append((fp.GetReference(), round(Pn.ToMM(q.x) - 100, 3), round(100 - Pn.ToMM(q.y), 3)))
    return out


def render(res, m, env):
    from PIL import Image, ImageDraw
    import layout
    S = 10
    W, H = int(m.L * S) + 40, int(m.W * S) + 40
    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)
    X = lambda x: 20 + (x + m.L / 2) * S
    Y = lambda y: 20 + (m.W / 2 - y) * S
    R = lambda x0, y0, x1, y1, **k: d.rectangle([X(x0), Y(y1), X(x1), Y(y0)], **k)
    R(-m.L / 2, -m.W / 2, m.L / 2, m.W / 2, outline="#555", width=2)
    R(-m.L / 2 + m.WALL, -m.W / 2 + m.WALL, m.L / 2 - m.WALL, m.W / 2 - m.WALL, outline="#999")
    R(m.CELL_X0 - m.HOLD_END, m.YC - m.HOLD_W / 2, m.CELL_X0 + m.CELL_L + m.HOLD_END, m.YC + m.HOLD_W / 2, fill="#ddd", outline="#222")
    R(m.CELL_X0, m.YC - m.CELL_D / 2, m.CELL_X0 + m.CELL_L, m.YC + m.CELL_D / 2, fill="#9bb7e0", outline="#3a7bd5")
    pts = [(X(x), Y(y)) for x, y in layout.OUTLINE]
    d.polygon(pts, fill="#cfe8d6", outline="#1f8a4c")
    a = m.ANTENNA
    R(a[0], a[2], a[1], a[3], fill="#f7d9a8", outline="#c77d00")
    d.text((X(a[0]) + 4, Y(a[3]) + 4), "BT40NE antenna\n(off board)", fill="#7a4b00")
    for e in env:
        col = "#d94f4f" if e["ref"] in ("J1", "J2") else "#2f6f4f"
        R(e["x0"], e["y0"], e["x1"], e["y1"], outline=col)
        if e["ref"][0] in "UJ" or e["ref"] in ("SW1", "BT1"):
            d.text((X(e["x0"]) + 2, Y(e["y1"]) + 2), e["ref"], fill=col)
    for x, y in m.POSTS:
        d.ellipse([X(x - 2.5), Y(y + 2.5), X(x + 2.5), Y(y - 2.5)], fill="#888")
    for x, y in m.CLIP_SCREWS:
        r = m.BOSS_D / 2
        d.ellipse([X(x - r), Y(y + r), X(x + r), Y(y - r)], outline="#555", width=2)
    P = m.PCB
    for x, y in m.PCB_RESTS:
        d.ellipse([X(x - 2), Y(y + 2), X(x + 2), Y(y - 2)], outline="#aaa")
    for x, y in m.PCB_SCREWS:
        r = m.SCREW_BOSS_D / 2
        d.ellipse([X(x - r), Y(y + r), X(x + r), Y(y - r)], outline="#7a00c7", width=2)
    sa = m.SW_ACT
    R(sa["x0"] - 1.75, sa["y0"], sa["x1"] + 1.75, sa["y1"] - 0.3, outline="#7a00c7", width=2)
    for x, y in m.LEDS:
        r = m.LED_D / 2
        d.ellipse([X(x - r), Y(y + r), X(x + r), Y(y - r)], outline="#e6a700", width=2)
    sx, sy, sl, sw = m.SWITCH
    R(sx - sl / 2, sy - sw / 2, sx + sl / 2, sy + sw / 2, outline="#e6a700", width=2)
    wx, wy = m.WHIP_XY
    d.ellipse([X(wx) - 5, Y(wy) - 5, X(wx) + 5, Y(wy) + 5], fill="#f2c200")
    d.line([X(-25.1), Y(9.9), X(wx), Y(wy)], fill="#f2c200", width=1)
    d.text((24, H - 18), "top view, lid off: board (green), parts (courtyards), holder+cell, posts, clip bosses, "
           "rests, M2 screw bosses + switch fork (purple), lid light pipes/switch slot (amber), whip + pigtail (yellow)", fill="black")
    (OUT / "render").mkdir(parents=True, exist_ok=True)
    img.save(OUT / "render" / "fit_top.png")
    # side section looking from -y: z vs x
    Hs = int(30 * S) + 40
    img = Image.new("RGB", (W, Hs), "white")
    d = ImageDraw.Draw(img)
    Z = lambda z: Hs - 30 - z * S
    d.rectangle([X(-m.L / 2), Z(m.Z_TOP + m.WALL), X(m.L / 2), Z(0)], outline="#555", width=2)
    d.line([X(-m.L / 2), Z(m.Z_TOP), X(m.L / 2), Z(m.Z_TOP)], fill="#999")
    d.line([X(-m.L / 2), Z(m.WALL), X(m.L / 2), Z(m.WALL)], fill="#999")
    top = P["z0"] + P["t"]
    d.rectangle([X(P["x0"]), Z(top), X(P["x1"]), Z(P["z0"])], fill="#1f8a4c")
    d.rectangle([X(a[0]), Z(top + a[4]), X(a[1]), Z(top)], fill="#f7d9a8", outline="#c77d00")
    for x, y in m.CLIP_SCREWS[:1]:
        d.rectangle([X(x - m.BOSS_D / 2), Z(m.BOSS_TOP), X(x + m.BOSS_D / 2), Z(m.WALL)], fill="#bbb")
    d.rectangle([X(m.CELL_X0 - m.HOLD_END), Z(m.ZC + 4), X(m.CELL_X0 + m.CELL_L + m.HOLD_END), Z(m.WALL)], outline="#222")
    for e in env:
        d.rectangle([X(e["x0"]), Z(top + e["h"]), X(min(e["x1"], m.L / 2 + 3)), Z(top)], outline="#2f6f4f")
    d.ellipse([X(m.L / 2 - m.WALL) - 3 * S, Z(m.JACK_Z) - 3 * S, X(m.L / 2 - m.WALL) + 3 * S, Z(m.JACK_Z) + 3 * S], outline="#d94f4f", width=2)
    d.text((24, 8), f"side section from -y: board z {P['z0']:.1f}-{top:.1f}, lid underside {m.Z_TOP:.1f}; holder (outline), "
           f"clip boss under the antenna (grey), jack opening (red)", fill="black")
    img.save(OUT / "render" / "fit_side.png")


def main():
    res, m, env = checks()
    res["_tht"] = _tht_pads()
    (OUT / "fit.json").write_text(json.dumps(res, indent=1) + "\n")
    for k, v in res.items():
        if isinstance(v, dict):
            print(f"{'ok  ' if v['ok'] else 'FAIL'} {k}: {v['detail']}")
    print({k: v for k, v in res.items() if not isinstance(v, dict) and not k.startswith("_")})
    render(res, m, env)
    return 1 if res["fail"] else 0


if __name__ == "__main__":
    sys.exit(main())
