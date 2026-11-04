"""Turn a Wan2.2-S2V or LongCat-Video-Avatar clip (green background) into the presenter frames that short.html draws.
usage: python3 tools/char_from_s2v.py <clip.mp4> <plan.js> <line_index|-1> <out_dir> [base_w,base_h]   (-1 = whole video)
The clip is letter-boxed by the model; the black bars are cut and the picture is scaled back to the
base image size (720x1280) so it lines up exactly like the still. Writes out_dir/f<frame>.png (RGBA)
for every 30 fps frame of that line, holding the last clip frame if the clip is shorter."""
import glob, json, os, subprocess, sys, tempfile
import numpy as np
from PIL import Image
from scipy import ndimage

clip, plan_p, li, out = sys.argv[1], sys.argv[2], int(sys.argv[3]), sys.argv[4]
BW, BH = [int(v) for v in (sys.argv[5] if len(sys.argv) > 5 else "720,1280").split(",")]
os.makedirs(out, exist_ok=True)
txt = open(plan_p, encoding="utf-8").read(); P = json.loads(txt[txt.index("=") + 1:].rstrip(";\n "))
FPS = P["fps"]
SKIP = int(os.environ.get("S2V_SKIP", "3"))  # Wan2.2-S2V: 3, LongCat-Avatar: 0
KEY_FILL = (0, 255, 0)  # padding is made "green" so it keys out
src_fps = eval(subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v", "-show_entries", "stream=r_frame_rate",
                               "-of", "csv=p=0", clip], capture_output=True, text=True).stdout.strip())
tmp = tempfile.mkdtemp()
subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", clip, os.path.join(tmp, "%04d.png")], check=True)
src = sorted(glob.glob(os.path.join(tmp, "*.png")))


def keyed(a):
    dark = (a.sum(2) < 60).mean(1); rows = np.where(dark < 0.9)[0]
    a = a[rows.min():rows.max() + 1]                       # cut the black bars
    h, w = a.shape[:2]
    if abs(w / h - BW / BH) < 0.01:
        a = np.array(Image.fromarray(a.astype(np.uint8)).resize((BW, BH), Image.LANCZOS)).astype(np.float32)
    else:  # model centre-cropped the still to its own aspect: scale back by width and put it at the same height
        nh = round(h * BW / w); a = np.array(Image.fromarray(a.astype(np.uint8)).resize((BW, nh), Image.LANCZOS)).astype(np.float32)
        canvas = np.zeros((BH, BW, 3), np.float32); canvas[...] = KEY_FILL; top = (BH - nh) // 2
        src0, dst0 = max(0, -top), max(0, top); n = min(nh - src0, BH - dst0)
        canvas[dst0:dst0 + n] = a[src0:src0 + n]; a = canvas
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    k = g - np.maximum(r, b)
    alpha = np.clip(1 - (k - 35) / 70, 0, 1)
    near = ndimage.gaussian_filter(alpha, 2.5) < 0.995      # green fringe on/near the edge
    g2 = np.where(near, np.minimum(g, np.maximum(r, b)), g)
    return Image.fromarray(np.clip(np.dstack([r, g2, b, alpha * 255]), 0, 255).astype(np.uint8), "RGBA")


if li < 0:  # -1 = one clip for the whole narration (its time 0 = video time 0): every frame of the video
    f0, n, absolute = 0, int(round(P["T"] * FPS)), True
else:
    ln = P["lines"][li]
    f0 = int(round(ln["start"] * FPS))
    nxt = P["lines"][li + 1]["start"] if li + 1 < len(P["lines"]) else P["voice_end"] + 0.35
    n = int(round(nxt * FPS)) - f0
    absolute = False
cache = {}
for k in range(n):
    j = max(SKIP, min(int(k * src_fps / FPS), len(src) - 1))  # first frames: the still, then the arm sweeping in (blurred) - skip them
    if j not in cache: cache[j] = keyed(np.array(Image.open(src[j]).convert("RGB")).astype(np.float32))
    cache[j].save(os.path.join(out, f"f{f0 + k}.png"))
print(f"line {li}: {n} frames from {len(src)} clip frames ({src_fps} fps)" + (" [whole video]" if absolute else ""))
