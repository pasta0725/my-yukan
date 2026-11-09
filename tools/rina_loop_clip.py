"""Big presenter from a past Colab clip (2026-11-09 試作C): its keyed frames played forward then backward
(seamless loop), and where the face is in each frame, so the page can paint this line's mouth over the old one.
usage: python3 tools/rina_loop_clip.py <frames_dir of a past clip (big_clip.py output)> <out_dir> <seconds>
writes <out_dir>/0000.png ... and face.js (window.FACE = per frame [mouth dx, dy, eye dx, dy] vs big_hq)."""
import json, math, os, shutil, sys
import cv2
import numpy as np

src, out, secs = sys.argv[1], sys.argv[2], float(sys.argv[3])
os.makedirs(out, exist_ok=True)
for f in os.listdir(out):
    if f.endswith(".png"): os.remove(os.path.join(out, f))
files = sorted(f for f in os.listdir(src) if f.endswith(".png"))
seq = files + files[-2:0:-1]                       # forward, then back (no jump at the turn)


def gray(p):
    a = cv2.imread(p, cv2.IMREAD_UNCHANGED).astype(np.float32)
    al = a[..., 3:4] / 255 if a.shape[2] == 4 else 1
    return cv2.cvtColor((a[..., :3] * al + 200 * (1 - al)).astype(np.uint8), cv2.COLOR_BGR2GRAY)


import PIL.Image as I
r = np.array(I.open("channel/rina_puppet/big_hq.webp").convert("RGBA")).astype(np.float32)
ref = cv2.cvtColor((r[..., :3] * r[..., 3:4] / 255 + 200 * (1 - r[..., 3:4] / 255)).astype(np.uint8), cv2.COLOR_RGB2GRAY)
X0, X1, Y0, Y1 = 430, 662, 330, 440                 # eyes and nose (not the mouth, which moves)
tpl = ref[Y0:Y1, X0:X1]
cache = {}


def where(f):
    if f in cache: return cache[f]
    gimg = gray(os.path.join(src, f)); m = 60
    win = gimg[Y0 - m:Y1 + m, X0 - m:X1 + m]
    res = cv2.matchTemplate(win, tpl, cv2.TM_CCOEFF_NORMED); _, sc, _, loc = cv2.minMaxLoc(res)
    cache[f] = (loc[0] - m, loc[1] - m, sc); return cache[f]


n = int(math.ceil(secs * 30)); face = []
for k in range(n):
    f = seq[k % len(seq)]
    shutil.copyfile(os.path.join(src, f), os.path.join(out, f"{k:04d}.png"))
    dx, dy, sc = where(f); face.append([dx, dy, dx, dy])
print("match scores min", round(min(c[2] for c in cache.values()), 3))
open(os.path.join(out, "face.js"), "w").write("window.FACE=" + json.dumps(face) + ";window.FACE_COVER=true;")
print("frames", n, "->", out)
