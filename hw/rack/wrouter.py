"""Windowed wrapper around the pack's grid maze router (hw/pack/router.py) for a board too big for one grid.

The router rasterises copper into byte maps at 0.1 mm; a 412 x 323 mm board would need ~13 M cells per layer and
per width class, and A* over it in pure Python is slow. Here every copper item lives in one list (Copper), and each
connection is routed in a small grid built just for it: the bounding box of the new terminal and the nearest copper
already connected to its net, plus a margin (retried wider when it fails). In that grid the net being routed is id 1
and every other net is id 2, so there is no 250-net limit.

Router layers: 0 = F.Cu, 1 = In2.Cu, 2 = B.Cu (In1.Cu is the solid GND plane and is never routed), as router.py.
A net's targets are only the items already joined to it (the "connected" flag), so a branch never lands on a pad of
its own net that is not yet part of the tree.
"""
import math

KL = ("F.Cu", "In2.Cu", "B.Cu")
ALL = (0, 1, 2)


class Item:
    __slots__ = ("kind", "layers", "geom", "net", "bbox", "extra", "conn", "w")

    def __init__(self, kind, layers, geom, net, bbox, extra=0.0, conn=False, w=0.0):
        self.kind, self.layers, self.geom, self.net, self.bbox = kind, tuple(layers), geom, net, bbox
        self.extra, self.conn, self.w = extra, conn, w


def _seg_bbox(a, b, w):
    h = w / 2
    return (min(a[0], b[0]) - h, min(a[1], b[1]) - h, max(a[0], b[0]) + h, max(a[1], b[1]) + h)


class Copper:
    """every copper item on the board, in board mm"""

    def __init__(self, router, outline_rect, edge_clr=0.3, clearance=0.15, slack=0.05, widths=None, via=(0.6, 0.3), g=0.1):
        self.R = router
        self.items = []
        self.rect = outline_rect
        self.edge_clr, self.clr, self.slack, self.g = edge_clr, clearance, slack, g
        self.widths = widths or {"sig": 0.2, "pwr": 0.3, "wide": 0.5}
        self.via = via
        self.tags = []            # (layers, rect, tag)
        self.keepouts = []        # (layers, rect or circle, exempt nets)

    # ---- adding copper ----
    def pad(self, layers, poly, net, extra=0.0, smd=True, hole=None, conn=False):
        xs = [p[0] for p in poly]; ys = [p[1] for p in poly]
        it = Item("pad", layers, (poly, smd, hole), net, (min(xs), min(ys), max(xs), max(ys)), extra, conn)
        self.items.append(it)
        return it

    def seg(self, l, a, b, w, net, extra=0.0, conn=True):
        it = Item("seg", (l,), (a, b), net, _seg_bbox(a, b, w), extra, conn, w)
        self.items.append(it)
        return it

    def via_at(self, c, net, d=None, conn=True, hole_r=None):
        d = d or self.via[0]
        it = Item("via", ALL, (c, d / 2, hole_r if hole_r is not None else self.via[1] / 2), net,
                  (c[0] - d / 2, c[1] - d / 2, c[0] + d / 2, c[1] + d / 2), 0.0, conn)
        self.items.append(it)
        return it

    def hole(self, c, r):
        self.items.append(Item("hole", ALL, (c, r), None, (c[0] - r, c[1] - r, c[0] + r, c[1] + r)))

    def zone(self, l, poly, net):
        xs = [p[0] for p in poly]; ys = [p[1] for p in poly]
        it = Item("zone", (l,), poly, net, (min(xs), min(ys), max(xs), max(ys)), 0.0, True)
        self.items.append(it)
        return it

    def keepout(self, layers, rect, exempt=()):
        self.keepouts.append((tuple(layers), rect, set(exempt)))

    def tag(self, layers, rect, tag):
        self.tags.append((tuple(layers), rect, tag))

    # ---- one routing grid ----
    def grid(self, win, net):
        R = self.R
        x0, y0, x1, y1 = win
        bx0, by0, bx1, by1 = self.rect
        x0, y0, x1, y1 = max(x0, bx0), max(y0, by0), min(x1, bx1), min(y1, by1)
        g = R.Grid(x0, y0, x1, y1, g=self.g, clearance=self.clr, slack=self.slack, widths=dict(self.widths), via=self.via)
        rmax = max(g._radius(c) for c in g.cls) + 1.0
        # board edge band
        for c in g.cls:
            r = self.edge_clr + g.cls[c] / 2 + g.slack
            for band in ((x0, y0, bx0 + r, y1), (bx1 - r, y0, x1, y1), (x0, y0, x1, by0 + r), (x0, by1 - r, x1, y1)):
                if band[2] < x0 or band[0] > x1 or band[3] < y0 or band[1] > y1:
                    continue
                for i, x, y in g._bbox_cells(*band):
                    if x < bx0 + r or y < by0 + r or x > bx1 - r or y > by1 - r:
                        for l in range(3):
                            g.own[c][l][i] = R.HARD
        for layers, rect, tg in self.tags:
            if rect[2] < x0 or rect[0] > x1 or rect[3] < y0 or rect[1] > y1:
                continue
            g.tag_rect(list(layers), rect, tg)
        for layers, shape, exempt in self.keepouts:
            if net in exempt:
                continue
            if len(shape) == 3:                       # circle (cx, cy, r)
                cx, cy, r = shape
                if cx + r < x0 - rmax or cx - r > x1 + rmax or cy + r < y0 - rmax or cy - r > y1 + rmax:
                    continue
                for cls in g.cls:
                    rr = r + g.cls[cls] / 2 + g.slack
                    for i, x, y in g._bbox_cells(cx - rr, cy - rr, cx + rr, cy + rr):
                        if math.hypot(x - cx, y - cy) <= rr:
                            for l in layers:
                                g.own[cls][l][i] = R.HARD
                    if cls == "via":
                        for i, x, y in g._bbox_cells(cx - rr, cy - rr, cx + rr, cy + rr):
                            if math.hypot(x - cx, y - cy) <= rr:
                                g.novia[i] = 1
            else:
                a, b, c_, d = shape
                if c_ < x0 - rmax or a > x1 + rmax or d < y0 - rmax or b > y1 + rmax:
                    continue
                for cls in g.cls:
                    h = g.cls[cls] / 2 + g.slack
                    for i, x, y in g._bbox_cells(a - h, b - h, c_ + h, d + h):
                        for l in layers:
                            g.own[cls][l][i] = R.HARD
                        if cls == "via" and len(layers) == 3:
                            g.novia[i] = 1
        targets = set()
        for it in self.items:
            bb = it.bbox
            if bb[2] < x0 - rmax - it.extra or bb[0] > x1 + rmax + it.extra or bb[3] < y0 - rmax - it.extra or bb[1] > y1 + rmax + it.extra:
                continue
            nid = 1 if it.net == net else 2
            if it.kind == "pad":
                poly, smd, hole = it.geom
                g.mark_poly(list(it.layers), poly, nid, extra=it.extra if nid == 2 else 0.0)
                if hole:
                    g.mark_via_hole(hole[0], hole_r=hole[1])
                if smd:
                    xs = [q[0] for q in poly]; ys = [q[1] for q in poly]
                    for i, x, y in g._bbox_cells(min(xs), min(ys), max(xs), max(ys)):
                        if R.in_poly(x, y, poly):
                            g.novia[i] = 1
                if nid == 1 and smd:
                    # neck zone: round a pad too small for the wide class, the track may drop to the "pwr" width
                    xs = [q[0] for q in poly]; ys = [q[1] for q in poly]
                    if min(max(xs) - min(xs), max(ys) - min(ys)) < self.widths.get("wide", 0.5) + 0.1 or \
                            min(max(xs) - min(xs), max(ys) - min(ys)) < self.widths.get("big", 0.5) + 0.1:
                        for i, x, y in g._bbox_cells(min(xs) - 1.2, min(ys) - 1.2, max(xs) + 1.2, max(ys) + 1.2):
                            g.neck[i] = 1
                if nid == 1 and it.conn:
                    xs = [q[0] for q in poly]; ys = [q[1] for q in poly]
                    for i, x, y in g._bbox_cells(min(xs), min(ys), max(xs), max(ys)):
                        if R.in_poly(x, y, poly):
                            for l in it.layers:
                                targets.add((l, i))
            elif it.kind == "seg":
                a, b = it.geom
                w = it.w + (2 * it.extra if nid == 2 else 0.0)
                g.mark_seg(list(it.layers), a, b, w, nid)
                if nid == 1 and it.conn:
                    L = math.hypot(b[0] - a[0], b[1] - a[1])
                    n = max(1, int(L / (self.g / 2)))
                    for s in range(n + 1):
                        i = g.cell(a[0] + (b[0] - a[0]) * s / n, a[1] + (b[1] - a[1]) * s / n)
                        if i is not None:
                            targets.add((it.layers[0], i))
            elif it.kind == "via":
                c, r, hr = it.geom
                g.mark_circle(range(3), c, r, nid)
                g.mark_via_hole(c, hole_r=hr)
                if nid == 1 and it.conn:
                    i = g.cell(*c)
                    if i is not None:
                        for l in range(3):
                            targets.add((l, i))
            elif it.kind == "hole":
                c, r = it.geom
                g.mark_hole(c, r)
            elif it.kind == "zone":
                poly = it.geom
                xs = [q[0] for q in poly]; ys = [q[1] for q in poly]
                if nid == 2:
                    g.mark_poly(list(it.layers), poly, 2)
                elif it.conn:
                    for i, x, y in g._bbox_cells(max(min(xs), x0), max(min(ys), y0), min(max(xs), x1), min(max(ys), y1)):
                        if R.in_poly(x, y, poly) and R.poly_dist_edge(x, y, poly) > 0.6:
                            targets.add((it.layers[0], i))
        return g, targets

    def pad_cells(self, g, it):
        poly = it.geom[0]
        out = set()
        xs = [q[0] for q in poly]; ys = [q[1] for q in poly]
        for i, x, y in g._bbox_cells(min(xs), min(ys), max(xs), max(ys)):
            if self.R.in_poly(x, y, poly):
                for l in it.layers:
                    out.add((l, i))
        return out

    # ---- route one net ----
    def route_net(self, net, cls, layers, forbid=None, via_cost=10.0, layer_cost=(1.0, 1.6, 1.3), margins=(3.0, 10.0, 30.0),
                  on_seg=None, on_via=None, max_expand=900000):
        """join every pad of the net to its connected copper; the first pad group seeds the tree when nothing of the
        net is connected yet. Returns the list of pad items it could not reach."""
        forbid = forbid or {}
        pads = [it for it in self.items if it.kind == "pad" and it.net == net]
        if not pads:
            return []
        if not any(it.conn for it in self.items if it.net == net):
            pads[0].conn = True
        failed = []
        todo = [p for p in pads if not p.conn]
        while todo:
            conn = [it for it in self.items if it.net == net and it.conn]

            def dist(p):
                cx, cy = (p.bbox[0] + p.bbox[2]) / 2, (p.bbox[1] + p.bbox[3]) / 2
                return min(_bbox_dist(cx, cy, c.bbox) for c in conn), c_near(cx, cy, conn)
            todo.sort(key=lambda p: dist(p)[0])
            p = todo.pop(0)
            _, near = dist(p)
            ok = False
            for m in margins:
                bb = p.bbox
                win = (min(bb[0], near[0]) - m, min(bb[1], near[1]) - m, max(bb[2], near[2]) + m, max(bb[3], near[3]) + m)
                g, targets = self.grid(win, net)
                src = self.pad_cells(g, p)
                targets -= src
                if not targets or not src:
                    continue
                path = g.astar(src, targets, 1, cls, layers, forbid, via_cost=via_cost, layer_cost=layer_cost,
                               max_expand=max_expand)
                if path is None:
                    continue
                segs, vias = g.to_segments(path, cls, 1, forbid)
                for l, a, b, w in segs:
                    self.seg(l, a, b, w, net)
                    if on_seg:
                        on_seg(net, l, a, b, w)
                for v in vias:
                    self.via_at(v, net)
                    if on_via:
                        on_via(net, v)
                p.conn = True
                # pads of this net the new copper ran into are joined too (same group / touching)
                ok = True
                break
            if not ok:
                failed.append(p)
        return failed


def _bbox_dist(x, y, bb):
    dx = max(bb[0] - x, 0, x - bb[2])
    dy = max(bb[1] - y, 0, y - bb[3])
    return math.hypot(dx, dy)


def c_near(x, y, conn):
    best = min(conn, key=lambda c: _bbox_dist(x, y, c.bbox))
    bb = best.bbox
    # for a big zone, the nearest point of its bbox, not the whole bbox
    qx, qy = min(max(x, bb[0]), bb[2]), min(max(y, bb[1]), bb[3])
    if (bb[2] - bb[0]) * (bb[3] - bb[1]) > 25.0:
        return (qx - 1, qy - 1, qx + 1, qy + 1)
    return bb
