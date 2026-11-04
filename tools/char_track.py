"""Make a lip-synced character track from a green-screen "talking" clip made by a video AI.
The clip's own mouth moves on its own, so for every output frame we PICK a clip frame whose
mouth openness matches the narration (closed when silent), preferring to keep playing forward
so the head motion stays smooth (dynamic programming).

usage: python3 tools/char_track.py <clip.mp4> <plan.js> <out_dir> [mouth_box x0,y0,x1,y1] [key_rgb r,g,b]
writes <out_dir>/f<frame>.png (RGBA, green removed) for every output frame of the lines with "puppet": true"""
import glob, json, os, subprocess, sys, tempfile
import numpy as np
from PIL import Image
from scipy import ndimage

clip, plan_p, out = sys.argv[1], sys.argv[2], sys.argv[3]
mb = [int(v) for v in (sys.argv[4] if len(sys.argv) > 4 else "250,300,470,460").split(",")]
key = np.array([float(v) for v in (sys.argv[5] if len(sys.argv) > 5 else "33,197,53").split(",")])
os.makedirs(out, exist_ok=True)
txt = open(plan_p, encoding="utf-8").read(); P = json.loads(txt[txt.index("=") + 1:].rstrip(";\n "))
FPS = P["fps"]

tmp = tempfile.mkdtemp()
subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", clip, os.path.join(tmp, "%04d.png")], check=True)
src = sorted(glob.glob(os.path.join(tmp, "*.png")))
frames = [np.array(Image.open(f).convert("RGB")).astype(np.float32) for f in src]

# 1) how open is the mouth in each clip frame (dark / red pixels of the mouth inside)
def openness(a):
    w = a[mb[1]:mb[3], mb[0]:mb[2]]; r, g, b = w[..., 0], w[..., 1], w[..., 2]
    inside = ((r > 120) & (g < 110) & (b < 120) & (r - g > 60)) | ((r < 90) & (g < 60) & (b < 70))
    return inside.sum()
s = np.array([openness(a) for a in frames], float)
lo, hi = np.percentile(s, 10), np.percentile(s, 90)
op = np.clip((s - lo) / max(hi - lo, 1), 0, 1)
closed_ok = op < 0.25


# 2) green key with spill removal
def keyed(a):
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    k = g - np.maximum(r, b)
    alpha = np.clip(1 - (k - 35) / 70, 0, 1)
    # green fringe: on and near the cut edge, green may not exceed the other two channels
    near = ndimage.gaussian_filter(alpha, 2.5) < 0.995
    g2 = np.where(near, np.minimum(g, np.maximum(r, b)), g)
    rgba = np.dstack([r, g2, b, alpha * 255])
    return Image.fromarray(np.clip(rgba, 0, 255).astype(np.uint8), "RGBA")


N = len(frames); step = 24 / FPS  # clip is 24 fps, output 30 fps
idx = np.arange(N)
for li, ln in enumerate(P["lines"]):
    if not ln.get("puppet"): continue
    V = P["voices"].get(str(li)) or P["voices"].get(li)
    f0 = int(round(ln["start"] * FPS))
    nxt = P["lines"][li + 1]["start"] if li + 1 < len(P["lines"]) else P["voice_end"] + 0.35
    n = int(round(nxt * FPS)) - f0
    target = []
    for k in range(n):
        m = V["mouth"][k] if V and k < len(V["mouth"]) else ["closed", 0]
        target.append(0.0 if m[0] == "closed" else (0.45 if m[0] in ("small", "u") else 1.0) * m[1])
    target = np.array(target)
    # DP over clip frames: match openness, keep moving forward ~0.8 frame per output frame
    cost = np.full(N, 0.0); back = np.zeros((n, N), int)
    start_pen = 0.002 * np.abs(idx - 0)  # start near the beginning (same pose as the base image)
    cost = start_pen + 4 * (op - target[0]) ** 2 + np.where((target[0] < 0.05) & ~closed_ok, 3, 0)
    for k in range(1, n):
        # transition: from i to j; natural move j-i in {0,1}; jumps cost more
        d = idx[None, :] - idx[:, None]   # d[i,j] = j - i
        trans = np.where((d == 1) | (d == 0), 0.0 if True else 0, 1.6 + 0.05 * np.abs(d))
        trans = np.where(d == 0, 0.05, trans)
        tot = cost[:, None] + trans
        back[k] = np.argmin(tot, axis=0)
        cost = tot[back[k], idx] + 4 * (op - target[k]) ** 2 + np.where((target[k] < 0.05) & ~closed_ok, 3, 0)
    path = [int(np.argmin(cost))]
    for k in range(n - 1, 0, -1): path.append(int(back[k][path[-1]]))
    path = path[::-1]
    jumps = sum(1 for a, b in zip(path, path[1:]) if b - a not in (0, 1))
    prev = None
    for k, j in enumerate(path):
        img = keyed(frames[j])
        if prev is not None and (j - prev_j) not in (0, 1):  # soften a jump with a quick blend
            img = Image.blend(prev, img, 0.6)
        img.save(os.path.join(out, f"f{f0 + k}.png")); prev, prev_j = img, j
    print(f"line {li}: {n} frames, jumps {jumps}, mean |open-target| {np.abs(op[path] - target).mean():.2f}")
