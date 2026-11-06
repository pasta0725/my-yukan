"""Presenter frames from a cleaned-up clip (tools/colab_refine_remote.py: x2 anime upscale + segmentation mask).
usage: python3 tools/char_from_refined.py <name_rgb.mp4> <name_a.mp4|-> <plan.js> <line_index|-1> <out_dir> <scale> [mode]
  scale = output size relative to the 720x1280 still (1.4 for the big presenter, 0.75 for the small one)
  mode  = key | seg | both (default both: inside the segmentation mask trust the green key, outside drop everything)
Writes out_dir/f<frame>.png (RGBA) laid out exactly like the still (letter-box / centre-crop undone)."""
import json, os, subprocess, sys
import numpy as np
from PIL import Image
from scipy import ndimage

rgb_p, a_p, plan_p, li, out, scale = sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4]), sys.argv[5], float(sys.argv[6])
mode = sys.argv[7] if len(sys.argv) > 7 else "both"
BW, BH = 720, 1280
OW, OH = round(BW * scale), round(BH * scale)
os.makedirs(out, exist_ok=True)
txt = open(plan_p, encoding="utf-8").read(); P = json.loads(txt[txt.index("=") + 1:].rstrip(";\n ")); FPS = P["fps"]
def probe(p, k): return subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v", "-show_entries", f"stream={k}", "-of", "csv=p=0", p], capture_output=True, text=True).stdout.strip()
W, H = [int(v) for v in probe(rgb_p, "width,height").split(",")]; src_fps = eval(probe(rgb_p, "r_frame_rate"))
def frames(p, gray=False):
    pr = subprocess.Popen(["ffmpeg", "-v", "error", "-i", p, "-f", "rawvideo", "-pix_fmt", "gray" if gray else "rgb24", "-"], stdout=subprocess.PIPE)
    n = W * H * (1 if gray else 3)
    while True:
        b = pr.stdout.read(n)
        if len(b) < n: break
        yield np.frombuffer(b, np.uint8).reshape(H, W) if gray else np.frombuffer(b, np.uint8).reshape(H, W, 3)
src = list(zip(frames(rgb_p), frames(a_p, True) if a_p != "-" else iter(lambda: None, 1)))

def to_base(a):  # undo the model's framing: scale by width to OW, centre on an OH canvas
    h, w = a.shape[:2]; nh = round(h * OW / w)
    im = Image.fromarray(a).resize((OW, nh), Image.LANCZOS); a = np.asarray(im).astype(np.float32)
    canvas = np.zeros((OH,) + a.shape[1:], np.float32)
    if a.ndim == 3: canvas[...] = (0, 255, 0)
    top = (OH - nh) // 2; s0, d0 = max(0, -top), max(0, top); n = min(nh - s0, OH - d0)
    canvas[d0:d0 + n] = a[s0:s0 + n]; return canvas

def rgba(rgb, seg):
    u = to_base(rgb); m = to_base(seg) / 255 if seg is not None else None
    r, g, b = u[..., 0], u[..., 1], u[..., 2]
    k = g - np.maximum(r, b); key = np.clip(1 - (k - 35) / 70, 0, 1) if scale >= 1 else np.clip(1 - (k - 6) / 36, 0, 1)  # small size: anything greenish is background
    if mode == "key" or m is None: alpha = key
    elif mode == "seg": alpha = m
    else: alpha = np.minimum(key, ndimage.maximum_filter(m, size=5))  # green never stays; nothing outside the character
    if scale < 1: alpha = ndimage.minimum_filter(alpha, size=3)  # small presenter: shave the 1px green rim off thin strands
    alpha = ndimage.gaussian_filter(alpha, max(0.6 * scale, 0.5))
    near = ndimage.gaussian_filter(alpha, max(2.0 * scale, 3.0)) < 0.995
    g2 = np.where(near, np.minimum(g, np.maximum(r, b)), g)
    if scale < 1:  # small presenter: semi-transparent edge pixels take the colour of the nearest solid pixel (no green/pink fringe)
        solid = alpha > 0.95
        if solid.any():
            _, (iy, ix) = ndimage.distance_transform_edt(~solid, return_indices=True)
            edge = ~solid
            r = np.where(edge, r[iy, ix], r); b = np.where(edge, b[iy, ix], b); g2 = np.where(edge, g2[iy, ix], g2)
    return Image.fromarray(np.clip(np.dstack([r, g2, b, alpha * 255]), 0, 255).astype(np.uint8), "RGBA")

if li < 0: f0, n = 0, int(round(P["T"] * FPS))
else:
    ln = P["lines"][li]; f0 = int(round(ln["start"] * FPS))
    nxt = P["lines"][li + 1]["start"] if li + 1 < len(P["lines"]) else P["voice_end"] + 0.35
    n = int(round(nxt * FPS)) - f0
cache = {}
for k in range(n):
    j = min(int(k * src_fps / FPS), len(src) - 1)
    if j not in cache: cache = {j: rgba(*src[j])}
    cache[j].save(os.path.join(out, f"f{f0 + k}.png"))
print(f"line {li}: {n} frames from {len(src)} clip frames, {OW}x{OH}, mode {mode}")
