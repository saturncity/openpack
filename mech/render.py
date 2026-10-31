"""Render PNGs for review: python mech/render.py -> mech/renders/*.png (needs matplotlib, trimesh)."""
import sys, tempfile, os
from pathlib import Path
import numpy as np, trimesh, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.collections import PolyCollection
import cadquery as cq
sys.path.insert(0, str(Path(__file__).parent))
import pack, panel

OUT = Path(__file__).parent / "renders"
COL = dict(base="#9aa5b1", lid="#c7d0da", door="#e8b04a", clip="#7a8a99", cell="#3a7bd5", holder="#222222",
           pcb="#1f8a4c", comps="#6fcf97", jack="#d94f4f", usbc="#d94f4f", whip="#f2c200")

def tri(wp):
    f = tempfile.mktemp(suffix=".stl"); cq.exporters.export(wp, f, tolerance=0.05, angularTolerance=0.2)
    return trimesh.load(f)

def scene(items, name, elev, azim, size, title, box=None):
    """painter's-algorithm render: all triangles projected and depth-sorted globally"""
    e, a = np.radians(elev), np.radians(azim)
    d = np.array([np.cos(e) * np.cos(a), np.cos(e) * np.sin(a), np.sin(e)])   # towards camera
    right = np.cross([0, 0, 1], d); right = right / np.linalg.norm(right) if np.linalg.norm(right) > 1e-6 else np.array([1, 0, 0])
    up = np.cross(d, right)
    P, C, Z = [], [], []
    for wp, col in items:
        m = tri(wp)
        v, f = trimesh.remesh.subdivide_to_size(m.vertices, m.faces, max_edge=3.0)
        m = trimesh.Trimesh(v, f); t = m.triangles; n = m.face_normals
        shade = 0.5 + 0.5 * np.clip(n @ (d + np.array([0.3, -0.4, 0.7])) / 1.6, 0, 1)
        rgb = np.array(matplotlib.colors.to_rgb(col))
        keep = (n @ d) > -0.05                          # backface cull
        P.append(np.stack([t[keep] @ right, t[keep] @ up], -1)); C.append(np.clip(shade[keep, None] * rgb, 0, 1)); Z.append(t[keep].mean(1) @ d)
    P, C, Z = np.concatenate(P), np.concatenate(C), np.concatenate(Z)
    o = np.argsort(Z)
    fig, ax = plt.subplots(figsize=size, dpi=110)
    ax.add_collection(PolyCollection(P[o], facecolors=C[o], edgecolors=C[o], linewidths=0.3))
    ax.set_xlim(P[..., 0].min(), P[..., 0].max()); ax.set_ylim(P[..., 1].min(), P[..., 1].max())
    ax.set_aspect("equal"); ax.set_axis_off(); ax.set_title(title, fontsize=9)
    fig.savefig(OUT / name, bbox_inches="tight"); plt.close(fig)

if __name__ == "__main__":
    OUT.mkdir(exist_ok=True)
    ps = pack.parts()
    pk = lambda keys: [(ps[k], COL[k]) for k in keys]
    inner = ["base", "clip", "cell", "holder", "pcb", "comps", "jack", "usbc"]
    scene(pk(inner), "pack_open_iso.png", 35, -60, (8, 6), "pack, lid and door removed (placeholder PCB envelope)")
    scene(pk(inner), "pack_open_top.png", 90, -90, (8, 5.5), "pack top view, lid removed")
    scene(pk(["base", "lid", "door", "clip", "jack", "usbc", "whip"]), "pack_closed_iso.png", 30, -50, (8, 7), "pack closed, 31 mm whip")
    scene(pk(["base", "lid", "door", "clip", "jack", "usbc", "whip"]), "pack_closed_back.png", 25, 20, (8, 7), "pack closed, rear (+x) face: TRS jack and recessed USB-C")
    scene([(panel.panel(), "#b8c2cc")], "panel_1u.png", 90, -90, (14, 1.8), "1U rear panel 482.6 x 44.45 x 3 mm")
