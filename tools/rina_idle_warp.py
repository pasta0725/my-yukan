"""Big presenter without Colab: the big still moved part by part, Live2D-like (2026-11-09 試作A).
usage: python3 tools/rina_idle_warp.py <out_dir> <seconds> [still.webp]
writes <out_dir>/0000.png ... (30 fps, 1080x1920 RGBA) and <out_dir>/face.json:
  per frame [mouth_dx, mouth_dy, eye_dx, eye_dy] = how far the face moved, so the page can draw the mouth
  and the blink (Puppet.mouthBig) on the moving face.
Motion (all slow and smooth, nothing follows the mouth frame by frame):
  breathing (chest and everything above rise and fall), head tilt and a small nod around the neck,
  a slight sway of the whole body around the feet, and hair/braids that follow the head a little late."""
import json, math, os, sys
import cv2
import numpy as np
from PIL import Image
from scipy import ndimage

out, secs = sys.argv[1], float(sys.argv[2])
src = sys.argv[3] if len(sys.argv) > 3 else "channel/rina_puppet/big_hq.webp"
FPS = 30
os.makedirs(out, exist_ok=True)
for f in os.listdir(out):
    if f.endswith(".png"): os.remove(os.path.join(out, f))

im = np.array(Image.open(src).convert("RGBA")).astype(np.float32)
H, W = im.shape[:2]
# premultiply so the transparent edge does not bleed dark/green when resampled
pm = im.copy(); pm[..., :3] *= pm[..., 3:4] / 255

yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
NECK = (546.0, 600.0)     # head turns around here (1080x1920 layout of big_hq)
FEET = (546.0, 1920.0)
MOUTH = (545.7, 468.8); EYE = (545.7, 384.0)


def smooth(e0, e1, v):  # 1 below e0 .. 0 above e1 (e0 < e1), smooth
    s = np.clip((v - e0) / (e1 - e0), 0, 1); return 1 - s * s * (3 - 2 * s)


w_head = smooth(500, 690, yy)                                  # head, hair and neck move together
w_breath = smooth(760, 1180, yy)                               # chest up: rises with the breath
r, g, b, a = [im[..., i] for i in range(4)]
hair = ((a > 20) & (r > 165) & (g > 160) & (b > 185) & (b >= r - 4) & (np.abs(r - g) < 40)).astype(np.float32)
hair[:, 420:670] *= 0                                          # not the face/fringe column: only the side hair and braids swing
hair = ndimage.gaussian_filter(hair, 18)
hair = np.clip(hair * 1.6, 0, 1) * np.clip((yy - 150) / 450, 0, 1)   # tips move more than roots
side = np.sign(xx - 546)


def rot_field(cx, cy, ang):  # where each output pixel comes from for a turn of ang (rad) around (cx, cy)
    c, s = math.cos(-ang), math.sin(-ang)
    dx, dy = xx - cx, yy - cy
    return cx + c * dx - s * dy - xx, cy + s * dx + c * dy - yy


def motion(t):
    head = math.radians(1.5 * math.sin(2 * math.pi * t / 3.4) + 0.5 * math.sin(2 * math.pi * t / 1.9 + 1.1))
    nod = 2.2 * math.sin(2 * math.pi * t / 2.6 + 0.4)
    breath = 3.2 * (0.5 - 0.5 * math.cos(2 * math.pi * t / 3.2))
    body = math.radians(0.35 * math.sin(2 * math.pi * t / 4.3 + 0.7))
    lag = math.radians(1.5 * math.sin(2 * math.pi * (t - 0.3) / 3.4) + 0.5 * math.sin(2 * math.pi * (t - 0.3) / 1.9 + 1.1))
    return head, nod, breath, body, lag


def face_shift(t):
    head, nod, breath, body, _ = motion(t)
    res = []
    for (px, py) in (MOUTH, EYE):
        x, y = px, py
        c, s = math.cos(head), math.sin(head); dx, dy = x - NECK[0], y - NECK[1]
        x, y = NECK[0] + c * dx - s * dy, NECK[1] + s * dx + c * dy + nod
        y -= breath
        c, s = math.cos(body), math.sin(body); dx, dy = x - FEET[0], y - FEET[1]
        x, y = FEET[0] + c * dx - s * dy, FEET[1] + s * dx + c * dy
        res += [round(x - px, 2), round(y - py, 2)]
    return res


n = int(math.ceil(secs * FPS)); face = []
for k in range(n):
    t = k / FPS
    head, nod, breath, body, lag = motion(t)
    hx, hy = rot_field(*NECK, head)
    bx, by = rot_field(*FEET, body)
    sway = (lag - head) * 260 + 2.5 * math.sin(2 * math.pi * t / 2.1)    # hair is late and swings a little on its own
    mx = xx + bx + w_head * hx - hair * sway
    my = yy + by + w_head * (hy - nod) + w_breath * breath
    frame = cv2.remap(pm, mx, my, cv2.INTER_CUBIC, borderMode=cv2.BORDER_CONSTANT, borderValue=0)
    al = np.clip(frame[..., 3:4], 0, 255)
    rgb = np.where(al > 0, frame[..., :3] * 255 / np.maximum(al, 1e-3), 0)
    Image.fromarray(np.clip(np.dstack([rgb, al]), 0, 255).astype(np.uint8), "RGBA").save(os.path.join(out, f"{k:04d}.png"))
    face.append(face_shift(t))
json.dump(face, open(os.path.join(out, "face.json"), "w"))
open(os.path.join(out, "face.js"), "w").write("window.FACE=" + json.dumps(face) + ";")
print("frames", n, "->", out)
