#!/usr/bin/env python3
"""Sweep alpha/offset ratios of the `wrap` tool and plot a grid of renders.

Columns are alpha ratios, rows are offset ratios (like the CGAL docs figure).
Needs: numpy, matplotlib. Runs `wrap` either from the Docker image or a local binary.

  python3 sweep.py o.stl --seed 0.5 1.2 0.8 \
      --alpha-ratios 10 20 40 --offset-ratios 500 2000
"""
import argparse
import os
import re
import subprocess
import sys

import numpy as np
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

RESULT_RE = re.compile(r"Result: (\d+) vertices, (\d+) faces in ([\d.eE+-]+) s")


def run_wrap(args, input_path, alpha_ratio, offset_ratio, out_path):
    """Run one wrap. Returns (faces, seconds) or None on failure."""
    seed_args = []
    for s in args.seed:
        seed_args += ["--seed", *map(str, s)]
    common = ["--alpha-ratio", str(alpha_ratio), "--offset-ratio", str(offset_ratio)] + seed_args

    if args.wrap_bin:
        cmd = [args.wrap_bin, input_path, *common, "--out", out_path]
    else:
        in_dir, in_name = os.path.split(os.path.abspath(input_path))
        out_dir, out_name = os.path.split(os.path.abspath(out_path))
        cmd = ["docker", "run", "--rm", "--user", f"{os.getuid()}:{os.getgid()}",
               "-v", f"{in_dir}:/in:ro", "-v", f"{out_dir}:/out",
               args.docker_image, f"/in/{in_name}", *common, "--out", f"/out/{out_name}"]

    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        print(f"  failed: {proc.stderr.strip() or proc.stdout.strip()}", file=sys.stderr)
        return None
    m = RESULT_RE.search(proc.stdout)
    return (int(m.group(2)), float(m.group(3))) if m else (0, 0.0)


def read_off(path):
    """Minimal OFF reader for triangulated meshes -> (vertices, faces)."""
    with open(path) as f:
        tokens = f.read().split()
    assert tokens[0] == "OFF", f"{path} is not an OFF file"
    nv, nf = int(tokens[1]), int(tokens[2])
    pos = 4
    verts = np.array(tokens[pos:pos + 3 * nv], dtype=float).reshape(nv, 3)
    pos += 3 * nv
    faces = []
    for _ in range(nf):
        n = int(tokens[pos])
        faces.append([int(t) for t in tokens[pos + 1:pos + 1 + n]])
        pos += 1 + n
    return verts, np.array(faces)


def clip_faces(verts, faces, clip):
    """Drop faces whose centroid is past the clip plane (cutaway view)."""
    if clip is None:
        return faces
    axis, value = clip
    centroids = verts[faces].mean(axis=1)
    return faces[centroids[:, axis] <= value]


def draw(ax, verts, faces, bounds, elev, azim):
    tris = verts[faces]
    n = np.cross(tris[:, 1] - tris[:, 0], tris[:, 2] - tris[:, 0])
    n /= np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-20)
    light = np.array([0.4, -0.5, 0.75])
    light /= np.linalg.norm(light)
    shade = 0.35 + 0.65 * np.abs(n @ light)  # abs: shell normals may point either way
    colors = np.stack([0.55 * shade, 0.70 * shade, 0.95 * shade, np.ones_like(shade)], axis=1)
    ax.add_collection3d(Poly3DCollection(tris, facecolors=colors, edgecolors="none"))
    lo, hi = bounds
    ax.set_xlim(lo[0], hi[0])
    ax.set_ylim(lo[1], hi[1])
    ax.set_zlim(lo[2], hi[2])
    ax.set_box_aspect(hi - lo)
    ax.view_init(elev=elev, azim=azim)
    ax.set_axis_off()


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("input")
    p.add_argument("--alpha-ratios", type=float, nargs="+", default=[10, 20, 40])
    p.add_argument("--offset-ratios", type=float, nargs="+", default=[500, 2000])
    p.add_argument("--seed", type=float, nargs=3, action="append", default=[],
                   metavar=("X", "Y", "Z"), help="interior seed point (repeatable)")
    p.add_argument("--outdir", default="sweep_out")
    p.add_argument("--image", default="sweep.png", help="output plot (png)")
    p.add_argument("--wrap-bin", help="path to a local `wrap` binary (default: use Docker)")
    p.add_argument("--docker-image", default="alpha-wrap", help="Docker image tag of the wrap tool")
    p.add_argument("--clip", nargs=2, metavar=("AXIS", "VALUE"),
                   help="cutaway: hide faces beyond VALUE on AXIS (x|y|z), to see inside a cavity")
    p.add_argument("--view", type=float, nargs=2, default=[25, -60], metavar=("ELEV", "AZIM"))
    p.add_argument("--reuse", action="store_true", help="skip runs whose output file already exists")
    args = p.parse_args()
    out_png = args.image

    clip = None
    if args.clip:
        clip = ("xyz".index(args.clip[0].lower()), float(args.clip[1]))

    os.makedirs(args.outdir, exist_ok=True)
    A, O = args.alpha_ratios, args.offset_ratios
    results = {}
    for o in O:
        for a in A:
            out = os.path.join(args.outdir, f"wrap_a{a:g}_o{o:g}.off")
            if args.reuse and os.path.exists(out):
                print(f"alpha_ratio={a:g} offset_ratio={o:g}: reusing {out}")
                results[(a, o)] = (None, None)
                continue
            print(f"alpha_ratio={a:g} offset_ratio={o:g} ...", flush=True)
            results[(a, o)] = run_wrap(args, args.input, a, o, out)

    meshes = {}
    for (a, o), r in results.items():
        path = os.path.join(args.outdir, f"wrap_a{a:g}_o{o:g}.off")
        if r is not None and os.path.exists(path):
            v, f = read_off(path)
            meshes[(a, o)] = (v, clip_faces(v, f, clip))
    if not meshes:
        sys.exit("No wrap succeeded; nothing to plot.")

    allv = np.vstack([v for v, _ in meshes.values()])
    lo, hi = allv.min(axis=0), allv.max(axis=0)

    fig = plt.figure(figsize=(4 * len(A), 4.2 * len(O)), dpi=150)
    for i, o in enumerate(O):
        for j, a in enumerate(A):
            ax = fig.add_subplot(len(O), len(A), i * len(A) + j + 1, projection="3d")
            if (a, o) in meshes:
                v, f = meshes[(a, o)]
                draw(ax, v, f, (lo, hi), *args.view)
                r = results[(a, o)]
                stats = f"\n{r[0]:,} faces, {r[1]:.1f} s" if r and r[0] is not None else ""
            else:
                ax.set_axis_off()
                ax.text2D(0.5, 0.5, "failed", transform=ax.transAxes, ha="center")
                stats = ""
            ax.set_title(f"alpha = diag/{a:g}, offset = diag/{o:g}{stats}", fontsize=9)
    fig.tight_layout()
    fig.savefig(out_png)
    print(f"Wrote {out_png}")


if __name__ == "__main__":
    main()
