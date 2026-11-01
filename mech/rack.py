"""1U rack chassis (RK-1, #34): a Hammond RM1U1913SBK with the main board, eight receivers, the CM4 IO board and
the rear/front panel cut-outs, plus an interference check.

    python3 mech/rack.py            -> prints the fit checks, writes mech/out/rack_fit.json, rack_{top,rear,side}.png
                                       (and mech/build/rack_*.step|stl when CadQuery is installed)

Case (Hammond drawing RM1U1913SBK, www.hammondmfg.com, read 2026-11-01): extruded 6063 aluminium frame, 482.61 wide
over the rack ears, 421.65 over the frame, 43.70 high, 330.20 deep; inside 415.30 x 323.85 x 40.09 (sections KK/LL);
3.18 mm (0.125 in) front and rear panels; 0.064 in (1.63 mm) top/bottom covers; frame wall 1.80 mm at the thinnest.
UK: Rapid Online 31-1555, GBP 140.76 ex VAT (hw/rack/prices.py).

Everything the board fixes comes from hw/rack/out/fab/mech.json (hw/rack/layout.py): board size and position,
standoff height, receiver footprint and holes, the panel connectors with their axis heights, the CM4IO frame.
Frame: x across the inside from the left wall, y from the rear panel's inner face towards the front, z up from the
inside of the bottom cover. Panel drawings are seen from OUTSIDE (rear panel: x mirrored).

Box model (no CadQuery needed): every solid is an axis-aligned box (cylinders by their bounding box), each checked
against the case inside and against every other solid, except the pairs that are meant to touch (a receiver on its
socket, a panel connector in its own cut-out). tests/mech/test_rack_fit.py repeats the overlap check with CadQuery
solids in CI.
"""
import json, math, pathlib, subprocess, sys

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
MECH = ROOT / "hw" / "rack" / "out" / "fab" / "mech.json"
OUT = HERE / "out"
BUILD = HERE / "build"

CASE = {"part": "Hammond RM1U1913SBK", "ears_w": 482.61, "frame_w": 421.65, "h": 43.70, "d": 330.20,
        "in_w": 415.30, "in_d": 323.85, "in_h": 40.09, "panel_t": 3.18, "cover_t": 1.63, "wall_t": 1.80,
        "uk": "Rapid Online 31-1555, GBP 140.76 ex VAT, 2026-11-01"}

# Panel parts that are not on the board (positions chosen in the gaps between the XLRs; data-sheet sizes)
# Neutrik NE8FDP etherCON (D-size): cut-out Ø24 + 2 x M3 at (+-9.5, +-12) diagonal, flange 26 x 31 in front of the
# panel, body behind it ~ Ø24 x 31 deep (est., D-series housing). Adafruit 4056 panel USB-C: M3 ears 20 mm apart,
# socket opening ~ 9.2 x 3.4 (est. from the Adafruit photos; cut 10 x 4.2), body ~ 12 x 6 x 16 deep (est.).
ETHERCON = {"x_board": 50.0, "z": 23.0, "cut_d": 24.0, "screws": [(-9.5, 12.0), (9.5, -12.0)], "screw_d": 3.2,
            "flange": (26.0, 31.0), "body": (24.0, 24.0, 31.0)}
USBC = {"x_board": 102.0, "z": 20.0, "slot": (10.0, 4.2), "screws": [(-10.0, 0.0), (10.0, 0.0)], "screw_d": 3.2,
        "body": (12.0, 7.0, 16.0)}
LED_HOLE_D = 2.5
HEIGHTS = {  # mm above the main board top, for the box model (data-sheet body heights, rounded up)
    "socket": 8.5, "idc": 9.1, "vh": 9.4, "cp": 5.6, "srp5030": 3.0, "smb": 2.5, "soic": 1.8, "default": 2.0,
}


def load():
    return json.loads(MECH.read_text())


def frame(m):
    """board (x, y) -> case frame; z of the board top"""
    x0 = m["board_x0"]
    top = m["standoff"] + m["thickness"]
    return (lambda x, y: (x + x0, y)), top


def solids(m):
    """[(name, box (x0, y0, z0, x1, y1, z1), group)] in the case frame"""
    to, top = frame(m)
    bw, bd = m["board"]
    S = [("main_board", (*to(0, 0), m["standoff"], *to(bw, bd), top), "board")]
    sw, sl = m["sub_board"]
    pitch = m["slot_pitch"]
    hs = m["sub_header_stack"]
    for k in range(8):
        x0, y0 = to(pitch * k, m["sub_y0"])
        # receiver: board from hs above the main board, parts to sub_above_main; the header/socket below it
        S.append((f"receiver{k}", (x0, y0, top + hs, x0 + sw, y0 + sl, top + m["sub_above_main"]), "rx"))
        # socket + header body under J1 (row at y = sub_y0 + 84.46..87.0, 13 columns, 2.54 pitch)
        sx0, sy0 = to(pitch * k + 48 - 8.76 - 2.54 * 12 - 1.27, m["sub_y0"] + 90 - 5.54 - 1.27)
        S.append((f"socket{k}", (sx0, sy0, top, sx0 + 2.54 * 13, sy0 + 5.08, top + hs), "socket"))
        for j, (hx, hy) in enumerate(m["sub_holes"][str(k)]):
            cx, cy = to(hx, hy)
            S.append((f"spacer{k}{j}", (cx - 3.2, cy - 3.2, top, cx + 3.2, cy + 3.2, top + hs), "spacer"))
    for p in m["panel"]:
        cx, _ = to(p["x"], 0)
        w, h = p["body"]
        S.append((p["name"], (cx - w / 2, 0.0, p["z"] - h / 2 if p["kind"] != "PJ-063AH" else top, cx + w / 2, p["depth"],
                              p["z"] + h / 2), "panelconn"))
    e = ETHERCON
    cx, _ = to(e["x_board"], 0)
    S.append(("ethercon", (cx - e["body"][0] / 2, 0.0, e["z"] - e["body"][1] / 2, cx + e["body"][0] / 2, e["body"][2],
                           e["z"] + e["body"][1] / 2), "panelconn"))
    u = USBC
    cx, _ = to(u["x_board"], 0)
    S.append(("usbc", (cx - u["body"][0] / 2, 0.0, u["z"] - u["body"][1] / 2, cx + u["body"][0] / 2, u["body"][2],
                       u["z"] + u["body"][1] / 2), "panelconn"))
    c = m["cm4io"]
    x0, y0 = to(c["rect"][0], c["rect"][1])
    x1, y1 = to(c["rect"][2], c["rect"][3])
    # CM4IO: board on 10 mm spacers, 1.6 mm, its tallest part (stacked USB-A / RJ45) 16 mm (est.) above it; the
    # THT pins below it reach 2.5 mm down (est.)
    S.append(("cm4io", (x0, y0, top + c["spacer"] - 2.5, x1, y1, top + c["spacer"] + 1.6 + c["height_above"]), "cm4io"))
    return S


def overlap(a, b, tol=0.0):
    return all(a[i] + tol < b[i + 3] and b[i] + tol < a[i + 3] for i in range(3))


ALLOWED = {("rx", "socket"), ("rx", "spacer"), ("socket", "board"), ("spacer", "board"), ("panelconn", "board")}


def rear_cutouts(m):
    """[(name, kind, x_out, z, size)] on the rear panel seen from outside (x mirrored: the left wall is on the right)"""
    to, top = frame(m)
    W = CASE["in_w"]
    out = []
    mir = lambda x: W - x
    for p in m["panel"]:
        x, _ = to(p["x"], 0)
        if p["kind"] == "NC3MAH":
            out.append((p["name"], "circle", mir(x), p["z"], p["cut_d"]))
            d, sd = p["screws"]
            for sx, sz in ((d, d), (-d, -d)):
                out.append((p["name"] + "_screw", "circle", mir(x + sx), p["z"] + sz, sd))
        elif p["kind"] == "5415025-1":
            out.append((p["name"], "dflat", mir(x), p["z"], (p["cut_d"], p["flat"])))
        else:
            out.append((p["name"], "circle", mir(x), p["z"], p["cut_d"]))
    e = ETHERCON
    x, _ = to(e["x_board"], 0)
    out.append(("ethercon", "circle", mir(x), e["z"], e["cut_d"]))
    for sx, sz in e["screws"]:
        out.append(("ethercon_screw", "circle", mir(x + sx), e["z"] + sz, e["screw_d"]))
    u = USBC
    x, _ = to(u["x_board"], 0)
    out.append(("usbc", "rect", mir(x), u["z"], u["slot"]))
    for sx, sz in u["screws"]:
        out.append(("usbc_screw", "circle", mir(x + sx), u["z"] + sz, u["screw_d"]))
    return out


def front_cutouts(m):
    to, top = frame(m)
    return [(f"led{i}", "circle", to(x, 0)[0], m["led_axis_z"], LED_HOLE_D) for i, (x, _) in enumerate(m["leds"])]


def cut_extent(c):
    _, kind, x, z, s = c
    if kind == "circle":
        return x - s / 2, x + s / 2, z - s / 2, z + s / 2
    if kind == "dflat":
        return x - s[0] / 2, x + s[0] / 2, z - s[0] / 2, z + s[1]
    return x - s[0] / 2, x + s[0] / 2, z - s[1] / 2, z + s[1] / 2


def checks(m=None):
    m = m or load()
    res, fail = {}, []

    def ok(name, cond, detail):
        res[name] = {"ok": bool(cond), "detail": detail}
        if not cond:
            fail.append(f"{name}: {detail}")
    S = solids(m)
    W, D, Hh = CASE["in_w"], CASE["in_d"], CASE["in_h"]
    to, top = frame(m)
    # 1. board and everything inside the case
    for name, b, g in S:
        ok(f"inside_{name}", b[0] >= 0 and b[1] >= 0 and b[2] >= 0 and b[3] <= W and b[4] <= D and b[5] <= Hh,
           f"{[round(v, 2) for v in b]}")
    # 2. no overlaps except the intended contacts
    bad = []
    for i, (na, a, ga) in enumerate(S):
        for nb, b, gb in S[i + 1:]:
            if (ga, gb) in ALLOWED or (gb, ga) in ALLOWED:
                continue
            if overlap(a, b):
                bad.append((na, nb))
    ok("no_interference", not bad, f"{bad[:8]}")
    # 3. margins
    rx_top = max(b[5] for n, b, g in S if g == "rx")
    cm_top = next(b[5] for n, b, g in S if n == "cm4io")
    side = min(min(b[0], W - b[3]) for n, b, g in S if g in ("board", "rx"))
    gaps = []
    rx = sorted((b for n, b, g in S if g == "rx"), key=lambda b: b[0])
    for a, b in zip(rx, rx[1:]):
        gaps.append(b[0] - a[3])
    margins = {"lid_over_receivers": round(Hh - rx_top, 2), "lid_over_cm4io": round(Hh - cm_top, 2),
               "side_wall": round(side, 2), "between_receivers": round(min(gaps), 2),
               "board_front_gap": round(D - m["board"][1], 2), "rear_panel_to_receivers": round(m["sub_y0"], 2)}
    res["margins"] = margins
    ok("lid_clearance", margins["lid_over_receivers"] >= 2.0, f"{margins['lid_over_receivers']} mm (>= 2)")
    ok("cm4io_clearance", margins["lid_over_cm4io"] >= 2.0, f"{margins['lid_over_cm4io']} mm (>= 2)")
    ok("side_clearance", margins["side_wall"] >= 1.0, f"{margins['side_wall']} mm (>= 1)")
    # 4. panel cut-outs: inside the panel's usable height (covers 1.63 mm, groove 2 mm est.) and >= 1.5 mm apart
    for which, cuts in (("rear", rear_cutouts(m)), ("front", front_cutouts(m))):
        ext = [(c[0], cut_extent(c)) for c in cuts]
        for n, e in ext:
            ok(f"{which}_{n}_in_panel", e[0] >= 3.0 and e[1] <= W - 3.0 and e[2] >= 2.0 and e[3] <= Hh - 2.0,
               f"{[round(v, 2) for v in e]}")
        close = []
        for i, (na, a) in enumerate(ext):
            for nb, b in ext[i + 1:]:
                if na.split("_")[0] == nb.split("_")[0]:
                    continue
                if a[0] - 1.5 < b[1] and b[0] - 1.5 < a[1] and a[2] - 1.5 < b[3] and b[2] - 1.5 < a[3]:
                    close.append((na, nb))
        ok(f"{which}_cutouts_apart", not close, f"{close[:6]}")
    # 5. connector axes vs. the board: every panel connector's body sits on (or above) the board top
    for p in m["panel"]:
        ok(f"axis_{p['name']}", p["z"] - p["body"][1] / 2 >= top - 0.01 or p["kind"] == "PJ-063AH",
           f"axis {p['z']:.2f}, body bottom {p['z'] - p['body'][1] / 2:.2f}, board top {top:.2f}")
    # 6. u.FL jumper reach: main-board port -> receiver J3/J4, path up and over the receiver's rear edge
    reach = []
    for ant in "AB":
        for (px, py), (rx_, ry) in zip(m["ports"][ant], m["receiver_ufl"][ant]):
            path = (m["sub_y0"] - py) + m["sub_header_stack"] + m["thickness"] + (ry - m["sub_y0"]) + abs(rx_ - px) + 6.0
            reach.append(path)
    res["ufl_path_max_mm"] = round(max(reach), 1)
    ok("ufl_jumper_reach", max(reach) <= 100.0 * 0.8, f"longest path {max(reach):.1f} mm vs 100 mm jumper (80 % usable)")
    return res, fail


# ---------------------------------------------------------------------------------------------------------------
# drawings (SVG -> PNG with ImageMagick): top view, rear and front panels, side section
# ---------------------------------------------------------------------------------------------------------------
def _svg(w, h, body, scale):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w * scale:.0f}" height="{h * scale:.0f}" '
            f'viewBox="-5 -5 {w + 10} {h + 10}"><rect x="-5" y="-5" width="{w + 10}" height="{h + 10}" fill="white"/>'
            f'{body}</svg>')


def _rect(x0, y0, x1, y1, fill, stroke="black", sw=0.3, op=1.0):
    return (f'<rect x="{min(x0, x1):.2f}" y="{min(y0, y1):.2f}" width="{abs(x1 - x0):.2f}" height="{abs(y1 - y0):.2f}" '
            f'fill="{fill}" fill-opacity="{op}" stroke="{stroke}" stroke-width="{sw}"/>')


def _circle(x, y, d, fill="none"):
    return f'<circle cx="{x:.2f}" cy="{y:.2f}" r="{d / 2:.2f}" fill="{fill}" stroke="black" stroke-width="0.3"/>'


def _text(x, y, t, s=3.0):
    return f'<text x="{x:.2f}" y="{y:.2f}" font-size="{s}" font-family="sans-serif">{t}</text>'


def render(m=None):
    m = m or load()
    OUT.mkdir(exist_ok=True)
    W, D, Hh = CASE["in_w"], CASE["in_d"], CASE["in_h"]
    S = solids(m)
    col = {"board": "#2e7d32", "rx": "#1565c0", "socket": "#424242", "spacer": "#9e9e9e", "panelconn": "#ef6c00",
           "cm4io": "#6a1b9a"}
    # top view: y (depth) down the page from the rear panel
    body = _rect(-CASE["panel_t"], -CASE["panel_t"], W + 0, D + CASE["panel_t"], "#eeeeee")
    body += _rect(0, 0, W, D, "white")
    for n, b, g in sorted(S, key=lambda s: s[1][2]):
        body += _rect(b[0], b[1], b[3], b[4], col[g], op=0.45 if g in ("rx", "cm4io") else 0.8)
    body += _text(2, -1, "REAR PANEL (inside view from above)", 4) + _text(2, D + 3.5, "FRONT PANEL", 4)
    body += _text(150, D - 60, f"{CASE['part']}: inside {W} x {D} x {Hh} mm", 5)
    files = {}
    files["rack_top"] = _svg(W, D + 8, body, 4)
    # rear panel, outside view
    body = _rect(0, 0, W, Hh, "#dddddd")
    for c in rear_cutouts(m):
        _, kind, x, z, s = c
        zz = Hh - z
        if kind == "circle":
            body += _circle(x, zz, s, "white")
        elif kind == "dflat":
            body += _circle(x, zz, s[0], "white") + _rect(x - s[0] / 2, zz - s[0] / 2, x + s[0] / 2, zz - s[1], "#dddddd", sw=0)
        else:
            body += _rect(x - s[0] / 2, zz - s[1] / 2, x + s[0] / 2, zz + s[1] / 2, "white")
    body += _text(2, Hh + 4, "REAR PANEL, seen from outside (cut-outs from hw/rack/out/fab/mech.json)", 3.5)
    files["rack_rear"] = _svg(W, Hh + 6, body, 5)
    body = _rect(0, 0, W, Hh, "#dddddd")
    for c in front_cutouts(m):
        _, kind, x, z, s = c
        body += _circle(x, Hh - z, s, "white")
    body += _text(2, Hh + 4, "FRONT PANEL, seen from outside: lock / peak LED per channel", 3.5)
    files["rack_front"] = _svg(W, Hh + 6, body, 5)
    # side section at slot 3 (x across the case: depth to the right, height up)
    body = _rect(0, 0, D, Hh, "white")
    for n, b, g in S:
        if b[0] <= 180 <= b[3] or g in ("board", "cm4io"):
            body += _rect(b[1], Hh - b[5], b[4], Hh - b[2], col[g], op=0.5)
    body += _text(2, Hh + 4, "SIDE SECTION through slot 3 (rear panel on the left, lid at the top)", 3.5)
    files["rack_side"] = _svg(D, Hh + 6, body, 5)
    for name, svg in files.items():
        p = OUT / f"{name}.svg"
        p.write_text(svg)
        subprocess.run(["magick", "-density", "150", str(p), "-background", "white", "-flatten", "-colors", "32",
                        f"PNG8:{OUT / (name + '.png')}"], check=True, capture_output=True)
        p.unlink()


def cadquery_solids(m=None):
    """CadQuery solids of the same boxes (CI), the case shell and the drilled panels"""
    import cadquery as cq
    m = m or load()
    box = lambda b: cq.Workplane("XY").box(b[3] - b[0], b[4] - b[1], b[5] - b[2], centered=False).translate((b[0], b[1], b[2]))
    parts = {n: box(b) for n, b, g in solids(m)}
    W, D, Hh, t = CASE["in_w"], CASE["in_d"], CASE["in_h"], CASE["panel_t"]
    rear = cq.Workplane("XZ").rect(W, Hh, centered=False).extrude(t).translate((0, 0, 0))
    for c in rear_cutouts(m):
        _, kind, x, z, s = c
        d = s if kind == "circle" else (s[0] if kind == "dflat" else max(s))
        hole = cq.Workplane("XZ").center(W - x, z).circle(d / 2).extrude(t + 2).translate((0, 1, 0))
        rear = rear.cut(hole)
    parts["rear_panel"] = rear
    return parts


def main():
    m = load()
    res, fail = checks(m)
    OUT.mkdir(exist_ok=True)
    (OUT / "rack_fit.json").write_text(json.dumps(res, indent=1) + "\n")
    for k, v in res.items():
        if k in ("margins", "ufl_path_max_mm"):
            print(f"{k}: {v}")
        elif not v["ok"]:
            print(f"FAIL {k}: {v['detail']}")
    print(f"{sum(1 for v in res.values() if isinstance(v, dict) and v.get('ok'))} checks ok, {len(fail)} failed")
    render(m)
    try:
        import cadquery as cq  # noqa: F401
        BUILD.mkdir(exist_ok=True)
        for n, s in cadquery_solids(m).items():
            if n in ("rear_panel",):
                cq.exporters.export(s, str(BUILD / f"rack_{n}.step"))
    except ImportError:
        pass
    return 1 if fail else 0


if __name__ == "__main__":
    sys.exit(main())
