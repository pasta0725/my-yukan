"""Ending picture brought to life (2026-11-09 試作: 画像AIの一枚絵＋動き).
usage: python3 tools/end_scene_warp.py <picture.png> <out_dir> <seconds> [face_x face_y]
writes <out_dir>/0000.jpg ... (30 fps, 1080x1920): wind in the hair and braids (a ripple that runs from the head to the tips)
and in the grass (more in front, less far away). The page adds the slow camera push-in, the sun glow and floating light.
face_x/face_y: centre of her face in the 1080x1920 picture (hair moves more the farther it is from there)."""
import math, os, sys
import cv2
import numpy as np
from PIL import Image
from scipy import ndimage

src, out, secs = sys.argv[1], sys.argv[2], float(sys.argv[3])
FX, FY = (float(sys.argv[4]), float(sys.argv[5])) if len(sys.argv) > 5 else (546.0, 820.0)
FPS = 30
os.makedirs(out, exist_ok=True)
for f in os.listdir(out):
    if f.endswith(".jpg"): os.remove(os.path.join(out, f))
im = np.array(Image.open(src).convert("RGB").resize((1080, 1920), Image.LANCZOS)).astype(np.float32)
H, W = im.shape[:2]; yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
r, g, b = im[..., 0], im[..., 1], im[..., 2]
mx = im.max(2); mn = im.min(2); sat = (mx - mn) / np.maximum(mx, 1)

# hair: light, not saturated, a little blue; only the big piece connected to her (not the sky, sun or far hills)
hair = (mx > 150) & (b >= r - 12) & (sat < 0.32) & (yy > H * 0.28) & (yy < H * 0.78)
lab, n = ndimage.label(ndimage.binary_dilation(hair, iterations=6))
if n: keep = np.argmax(np.bincount(lab.ravel())[1:]) + 1; hair &= lab == keep
d = np.hypot(xx - FX, (yy - FY) * 1.2)
hair_w = ndimage.gaussian_filter(hair.astype(np.float32), 10) * np.clip((d - 150) / 300, 0, 1)   # face/fringe stays, tips move most
grass = ((g > r * 0.95) & (g > b * 1.15) & (yy > H * 0.45)).astype(np.float32)
grass_w = ndimage.gaussian_filter(grass, 6) * np.clip((yy - H * 0.5) / (H * 0.5), 0, 1) ** 1.5    # near grass moves more

n = int(math.ceil(secs * FPS))
for k in range(n):
    t = k / FPS
    gust = 0.75 + 0.25 * math.sin(2 * math.pi * t / 3.7)
    wave = np.sin(2 * math.pi * t / 1.45 - d / 140)                         # ripple running out along the hair
    hdx = hair_w * (6.5 * gust * (0.6 + 0.4 * wave))                       # wind blows to the left: content shifts left
    hdy = hair_w * (2.2 * np.sin(2 * math.pi * t / 1.45 - d / 140 + 1.3))
    gdx = grass_w * 7 * np.sin(2 * math.pi * t / 1.7 - xx / 90 - yy / 400) * gust
    mxp = xx + hdx + gdx; myp = yy + hdy
    f = cv2.remap(im, mxp, myp, cv2.INTER_CUBIC, borderMode=cv2.BORDER_REFLECT)
    Image.fromarray(np.clip(f, 0, 255).astype(np.uint8)).save(os.path.join(out, f"{k:04d}.jpg"), quality=93)
print("frames", n, "->", out)
