"""Grid maze router for hw/pack/layout.py (pure Python: the system python that carries pcbnew has no numpy).

Coordinates are board mm, x right / y up (mech/pack.py frame). Three routing layers (F, In2, B); In1 is the
solid GND plane and is never routed. Every copper item is rasterised into per-layer, per-width "owner" maps:
a cell is free for net N when no other net's copper lies within clearance + half-width (+ slack) of its centre.
A* runs over (layer, cell) with 8-way moves and through-vias, then the path is string-pulled into any-angle
segments, each re-checked against the same maps. DRC (kicad-cli) is the final judge.
"""
import heapq
import math
from array import array

FREE, HARD, MULTI = 0, 255, 254
SQ2 = math.sqrt(2.0)


def seg_dist(px, py, ax, ay, bx, by):
    dx, dy = bx - ax, by - ay
    L2 = dx * dx + dy * dy
    t = 0.0 if L2 == 0 else max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / L2))
    qx, qy = ax + t * dx - px, ay + t * dy - py
    return math.sqrt(qx * qx + qy * qy)


def in_poly(px, py, poly):
    inside = False
    n = len(poly)
    j = n - 1
    for i in range(n):
        xi, yi = poly[i]
        xj, yj = poly[j]
        if (yi > py) != (yj > py) and px < (xj - xi) * (py - yi) / (yj - yi) + xi:
            inside = not inside
        j = i
    return inside


def poly_dist(px, py, poly):
    if in_poly(px, py, poly):
        return 0.0
    d = 1e9
    n = len(poly)
    for i in range(n):
        ax, ay = poly[i]
        bx, by = poly[(i + 1) % n]
        d = min(d, seg_dist(px, py, ax, ay, bx, by))
    return d


class Grid:
    def __init__(self, xmin, ymin, xmax, ymax, g=0.1, clearance=0.15, slack=0.05, widths=None, via=(0.6, 0.3)):
        self.g, self.x0, self.y0 = g, xmin, ymin
        self.nx = int(round((xmax - xmin) / g)) + 1
        self.ny = int(round((ymax - ymin) / g)) + 1
        self.N = self.nx * self.ny
        self.L = 3                                  # 0 F.Cu, 1 In2.Cu, 2 B.Cu
        self.clr, self.slack = clearance, slack
        self.widths = widths or {"sig": 0.2, "pwr": 0.4}
        self.via_d, self.via_drill = via
        # classes: track widths + the via pad
        self.cls = dict(self.widths)
        self.cls["via"] = self.via_d
        self.own = {c: [bytearray(self.N) for _ in range(self.L)] for c in self.cls}
        self.tag = [bytearray(self.N) for _ in range(self.L)]   # region tags (per-net forbids)
        self.novia = bytearray(self.N)                          # inside SMD pads: no via here
        # "neck" zones (L1 only): around small pads of a wide net, the wide class may fall back to a NECK-wide track
        self.neck = bytearray(self.N)
        self.NECK, self.NECK_W = "pwr", self.widths["pwr"]

    # ---- geometry helpers ----
    def xy(self, i):
        return self.x0 + (i % self.nx) * self.g, self.y0 + (i // self.nx) * self.g

    def cell(self, x, y):
        ix = int(round((x - self.x0) / self.g))
        iy = int(round((y - self.y0) / self.g))
        if 0 <= ix < self.nx and 0 <= iy < self.ny:
            return iy * self.nx + ix
        return None

    def _bbox_cells(self, x0, y0, x1, y1):
        ix0 = max(0, int(math.floor((x0 - self.x0) / self.g)))
        ix1 = min(self.nx - 1, int(math.ceil((x1 - self.x0) / self.g)))
        iy0 = max(0, int(math.floor((y0 - self.y0) / self.g)))
        iy1 = min(self.ny - 1, int(math.ceil((y1 - self.y0) / self.g)))
        for iy in range(iy0, iy1 + 1):
            y = self.y0 + iy * self.g
            base = iy * self.nx
            for ix in range(ix0, ix1 + 1):
                yield base + ix, self.x0 + ix * self.g, y

    def _radius(self, c):
        return self.clr + self.cls[c] / 2 + self.slack

    def _set(self, arr, i, net):
        v = arr[i]
        if v == FREE:
            arr[i] = net
        elif v != net and v != HARD:
            arr[i] = MULTI

    def mark_shape(self, layers, dist_fn, bbox, net, extra=0.0):
        """dist_fn(x, y) -> distance from copper (0 inside). Marks every width class on the given layers."""
        rmax = max(self._radius(c) for c in self.cls) + extra
        x0, y0, x1, y1 = bbox
        radii = [(c, self._radius(c) + extra) for c in self.cls]
        for i, x, y in self._bbox_cells(x0 - rmax, y0 - rmax, x1 + rmax, y1 + rmax):
            d = dist_fn(x, y)
            if d > rmax:
                continue
            for c, r in radii:
                if d <= r:
                    for l in layers:
                        self._set(self.own[c][l], i, net)

    def mark_poly(self, layers, poly, net, extra=0.0):
        xs = [p[0] for p in poly]
        ys = [p[1] for p in poly]
        self.mark_shape(layers, lambda x, y: poly_dist(x, y, poly), (min(xs), min(ys), max(xs), max(ys)), net, extra)

    def mark_seg(self, layers, a, b, width, net):
        hw = width / 2
        self.mark_shape(layers, lambda x, y: max(0.0, seg_dist(x, y, a[0], a[1], b[0], b[1]) - hw),
                        (min(a[0], b[0]) - hw, min(a[1], b[1]) - hw, max(a[0], b[0]) + hw, max(a[1], b[1]) + hw), net)

    def mark_circle(self, layers, c, r, net, extra=0.0):
        self.mark_shape(layers, lambda x, y: max(0.0, math.hypot(x - c[0], y - c[1]) - r),
                        (c[0] - r, c[1] - r, c[0] + r, c[1] + r), net, extra)

    def mark_hole(self, c, r, hole_clr=0.25):
        """drilled hole (NPTH or via drill): blocks every layer, with hole clearance for vias"""
        for cls in self.cls:
            rr = r + (hole_clr + self.via_drill / 2 if cls == "via" else self.clr) + self.cls[cls] / 2 + self.slack
            for i, x, y in self._bbox_cells(c[0] - rr, c[1] - rr, c[0] + rr, c[1] + rr):
                if math.hypot(x - c[0], y - c[1]) <= rr:
                    for l in range(self.L):
                        self.own[cls][l][i] = HARD

    def mark_outline(self, poly, edge_clr):
        """cells outside the board or within edge clearance (+ half width) of the edge become HARD"""
        for i in range(self.N):
            x, y = self.xy(i)
            inside = in_poly(x, y, poly)
            d = poly_dist_edge(x, y, poly)
            for c in self.cls:
                r = edge_clr + self.cls[c] / 2 + self.slack
                if not inside or d <= r:
                    for l in range(self.L):
                        self.own[c][l][i] = HARD

    def tag_rect(self, layers, rect, tag):
        x0, y0, x1, y1 = rect
        for i, _, _ in self._bbox_cells(x0, y0, x1, y1):
            for l in layers:
                self.tag[l][i] = tag

    def free(self, cls, l, i, net):
        v = self.own[cls][l][i]
        return v == FREE or v == net

    def via_ok(self, i, net, forbid_tags):
        if self.novia[i]:
            return False
        for l in range(self.L):
            v = self.own["via"][l][i]
            if not (v == FREE or v == net):
                return False
            if self.tag[l][i] in forbid_tags.get(l, ()):
                return False
        return True

    # ---- search ----
    def astar(self, sources, targets, net, cls, layers, forbid_tags, via_cost=10.0, layer_cost=(1.0, 1.6, 1.25),
              max_expand=600000):
        """sources/targets: sets of (layer, cell). Returns list of (layer, cell) from a source to a target."""
        nx, N = self.nx, self.N
        own = self.own[cls]
        tags = self.tag
        tcells = {}
        for l, i in targets:
            tcells.setdefault(i, set()).add(l)
        txy = [self.xy(i) for i in tcells]
        # heuristic: octile distance (cells) to the nearest target cell centre; few targets -> cheap
        tix = [((i % nx), (i // nx)) for i in tcells]
        if len(tix) > 40:
            step = len(tix) // 40 + 1
            tix = tix[::step]

        def h(i):
            x, y = i % nx, i // nx
            best = 1e18
            for tx, ty in tix:
                dx, dy = abs(x - tx), abs(y - ty)
                v = (dx + dy) + (SQ2 - 2) * min(dx, dy)
                if v < best:
                    best = v
            return best * 1.001

        INF = 1e30
        gsc = array("d", [INF]) * (N * self.L)
        prev = array("l", [-1]) * (N * self.L)
        heap = []
        for l, i in sources:
            if l not in layers:
                continue
            k = l * N + i
            gsc[k] = 0.0
            heapq.heappush(heap, (h(i), 0.0, k))
        moves = [(1, 0, 1.0), (-1, 0, 1.0), (0, 1, 1.0), (0, -1, 1.0), (1, 1, SQ2), (1, -1, SQ2), (-1, 1, SQ2), (-1, -1, SQ2)]
        wide = cls not in ("sig", "pwr")
        neck, narr = self.neck, self.own[self.NECK][0]

        def ok0(j, v):   # layer-0 test with the neck fallback for wide classes
            if v == FREE or v == net:
                return True
            if wide and neck[j] == net:
                w = narr[j]
                return w == FREE or w == net
            return False
        expanded = 0
        ny = self.ny
        while heap:
            f, gk, k = heapq.heappop(heap)
            if gk > gsc[k]:
                continue
            l, i = divmod(k, N)
            if i in tcells and l in tcells[i]:
                path = []
                while k != -1:
                    path.append(divmod(k, N))
                    k = prev[k]
                return path[::-1]
            expanded += 1
            if expanded > max_expand:
                return None
            x, y = i % nx, i // nx
            lc = layer_cost[l]
            arr = own[l]
            tg = tags[l]
            fb = forbid_tags.get(l, ())
            for dx, dy, c in moves:
                xx, yy = x + dx, y + dy
                if xx < 0 or yy < 0 or xx >= nx or yy >= ny:
                    continue
                j = yy * nx + xx
                v = arr[j]
                if l == 0 and wide:
                    if not ok0(j, v):
                        continue
                elif not (v == FREE or v == net):
                    continue
                if fb and tg[j] in fb:
                    continue
                if dx and dy:   # diagonal: both orthogonal neighbours must be free too (no corner cutting)
                    j1, j2 = y * nx + xx, yy * nx + x
                    v1, v2 = arr[j1], arr[j2]
                    if l == 0 and wide:
                        if not (ok0(j1, v1) and ok0(j2, v2)):
                            continue
                    elif not ((v1 == FREE or v1 == net) and (v2 == FREE or v2 == net)):
                        continue
                ng = gk + c * lc
                kk = l * N + j
                if ng < gsc[kk]:
                    gsc[kk] = ng
                    prev[kk] = k
                    heapq.heappush(heap, (ng + h(j), ng, kk))
            # via to the other allowed layers
            if len(layers) > 1 and self.via_ok(i, net, forbid_tags):
                for l2 in layers:
                    if l2 == l:
                        continue
                    kk = l2 * N + i
                    ng = gk + via_cost
                    if ng < gsc[kk]:
                        gsc[kk] = ng
                        prev[kk] = k
                        heapq.heappush(heap, (ng + h(i), ng, kk))
        return None

    # ---- path post-processing ----
    def seg_free(self, l, a, b, cls, net, forbid):
        """sample the segment every g/2 and require free cells (nearest-cell test)"""
        return self.seg_kind(l, a, b, cls, net, forbid) is not None

    def seg_kind(self, l, a, b, cls, net, forbid):
        """None if blocked; else the width the segment can take: the class width, or NECK_W when every sample sits in
        this net's neck zone (wide classes on L1 only). Mixed segments are refused so long runs stay full width."""
        L = math.hypot(b[0] - a[0], b[1] - a[1])
        n = max(1, int(L / (self.g / 2)))
        arr = self.own[cls][l]
        narr = self.own[self.NECK][l]
        tg = self.tag[l]
        wide_ok = neck_ok = True
        can_neck = l == 0 and cls not in ("sig", "pwr")
        for s in range(n + 1):
            t = s / n
            i = self.cell(a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)
            if i is None:
                return None
            if forbid and tg[i] in forbid:
                return None
            v = arr[i]
            if not (v == FREE or v == net):
                wide_ok = False
            w = narr[i]
            if not (can_neck and self.neck[i] == net and (w == FREE or w == net)):
                neck_ok = False
            if not wide_ok and not neck_ok:
                return None
        return self.cls[cls] if wide_ok else self.NECK_W

    def to_segments(self, path, cls, net, forbid_tags):
        """path [(layer, cell)] -> runs per layer of points, string-pulled; returns (segments, vias)"""
        runs, cur = [], []
        for l, i in path:
            if cur and cur[-1][0] != l:   # layer change happens on one cell: a via
                runs.append(cur)
                cur = []
            cur.append((l, i))
        if cur:
            runs.append(cur)
        segs, vias = [], []
        for r_idx, run in enumerate(runs):
            l = run[-1][0]
            pts = [self.xy(i) for _, i in run]
            if r_idx > 0:
                vias.append(pts[0])
            pts = self._pull(pts, l, cls, net, forbid_tags.get(l, ()))
            for a, b in zip(pts, pts[1:]):
                if a != b:
                    w = self.seg_kind(l, a, b, cls, net, forbid_tags.get(l, ())) or self.cls[cls]
                    segs.append((l, a, b, w))
        return segs, vias

    def _pull(self, pts, l, cls, net, forbid):
        # drop collinear points first
        if len(pts) <= 2:
            return pts
        out = [pts[0]]
        i = 0
        while i < len(pts) - 1:
            j = len(pts) - 1
            while j > i + 1 and not self.seg_free(l, pts[i], pts[j], cls, net, forbid):
                j -= 1
            out.append(pts[j])
            i = j
        return out

    def commit(self, segs, vias, width, net):
        for seg in segs:
            l, a, b = seg[:3]
            self.mark_seg([l], a, b, seg[3] if len(seg) > 3 else width, net)
        for v in vias:
            self.mark_circle(range(self.L), v, self.via_d / 2, net)
            # hole-to-hole spacing for later vias of any net
            self.mark_via_hole(v)

    def mark_via_hole(self, c, hole_gap=0.5, hole_r=None):
        hole_r = self.via_drill / 2 if hole_r is None else hole_r
        rr = hole_r + self.via_drill / 2 + hole_gap      # centre spacing from this drill to a via drill
        for i, x, y in self._bbox_cells(c[0] - rr, c[1] - rr, c[0] + rr, c[1] + rr):
            if math.hypot(x - c[0], y - c[1]) < rr:
                self.novia[i] = 1


def poly_dist_edge(px, py, poly):
    d = 1e9
    n = len(poly)
    for i in range(n):
        ax, ay = poly[i]
        bx, by = poly[(i + 1) % n]
        d = min(d, seg_dist(px, py, ax, ay, bx, by))
    return d
