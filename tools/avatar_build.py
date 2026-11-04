"""Build Live2D-like layers from edited copies of one base illustration.
Each edited copy removes or changes one part (made with an image AI); the difference
against the base tells us where that part is, and the edited copy supplies what was hidden.

usage: python3 -I tools/avatar_build.py <base.png RGBA> <edits_dir> <mouth_a.png> <out_dir>
edits_dir holds: no_bangs, no_side_hair, no_ribbon_clips, no_buns_back, no_iris,
                 eyes_half, eyes_closed, mouth_small, mouth_i, mouth_u, mouth_e, mouth_o (.png)
writes PNG layers + rig.json (patch positions) into out_dir."""
import json, os, sys
import numpy as np
from PIL import Image, ImageFilter
from scipy import ndimage

base_p, ed, mouth_a_p, out = sys.argv[1:5]
os.makedirs(out, exist_ok=True)
base_img = Image.open(base_p).convert("RGBA")
W, H = base_img.size
B = np.array(base_img).astype(np.float32)
alpha = B[:, :, 3]


def load(name):
    im = Image.open(os.path.join(ed, name + ".png")).convert("RGB")
    if im.size != (W, H):
        im = im.resize((W, H), Image.LANCZOS)
    return np.array(im).astype(np.float32)


def diff(E):
    return np.abs(E - B[:, :, :3]).sum(axis=2)


def region(y0, y1, x0, x1):
    r = np.zeros((H, W), bool); r[y0:y1, x0:x1] = True; return r


def clean(m, min_area=400, close=4, open_=1):
    if open_:
        m = ndimage.binary_opening(m, iterations=open_)
    lab, n = ndimage.label(m)
    if n:
        sizes = ndimage.sum(m, lab, range(1, n + 1))
        m = np.isin(lab, [i + 1 for i, s in enumerate(sizes) if s >= min_area])
    m = ndimage.binary_closing(m, iterations=close)
    return ndimage.binary_fill_holes(m)


def soft(m, r=2.0):
    return np.clip(ndimage.gaussian_filter(m.astype(np.float32), r) * 1.4 - 0.2, 0, 1)


def color_match(E, ring):
    """shift the edited image's colours so they match the base around the part"""
    if ring.sum() < 50:
        return E
    d = (B[:, :, :3][ring] - E[ring]).mean(axis=0)
    return np.clip(E + d, 0, 255)


def save(rgb, a, name):
    img = np.dstack([np.clip(rgb, 0, 255), np.clip(a, 0, 255)]).astype(np.uint8)
    Image.fromarray(img, "RGBA").save(os.path.join(out, name + ".png"))


def ring_of(m, w=10):
    return ndimage.binary_dilation(m, iterations=w) & ~ndimage.binary_dilation(m, iterations=3) & (alpha > 250)


rig = {"size": [W, H]}
# --- hair parts: where the edit differs strongly from the base -----------------
parts = {}
for name, edit, box, thr in [
    ("bangs", "no_bangs", (120, 620, 250, 780), 90),
    ("side", "no_side_hair", (250, 900, 120, 900), 90),
    ("ribbon", "no_ribbon_clips", (60, 620, 120, 900), 90),
    ("back", "no_buns_back", (0, 700, 80, 950), 120),
]:
    E = load(edit)
    m = clean((diff(E) > thr) & region(*box) & (alpha > 20), min_area=1200, close=5, open_=2)
    parts[name] = (m, color_match(E, ring_of(m)))
# side hair, ribbon and buns must not swallow the bangs
for k in ("side", "ribbon", "back"):
    parts[k] = (parts[k][0] & ~parts["bangs"][0], parts[k][1])

# layer under all hair: base, with each hidden area painted from its edit
under = B[:, :, :3].copy()
under_a = alpha.copy()
for k in ("ribbon", "side", "bangs"):
    m, E = parts[k]
    s = soft(m, 1.5)[..., None]
    under = under * (1 - s) + E * s
for k in ("back", "side", "ribbon", "bangs"):
    m, E = parts[k]
    white = ndimage.binary_opening(E.min(axis=2) > 232, iterations=2)
    under_a = np.where(m & white, 0, under_a)  # the edit painted background here
save(under, under_a, "under")
for k, order in (("back", "back"), ("side", "side"), ("bangs", "bangs"), ("ribbon", "ribbon")):
    m, _ = parts[k]
    save(B[:, :, :3], soft(m, 1.2) * alpha, order)

# --- eyes -----------------------------------------------------------------------
eye_box = (300, 500, 330, 720)
Ec = load("eyes_closed")
eye_m = clean((diff(Ec) > 60) & region(*eye_box), min_area=300, close=6)
lab, n = ndimage.label(eye_m)
if n > 2:
    sizes = ndimage.sum(eye_m, lab, range(1, n + 1))
    eye_m = np.isin(lab, list(np.argsort(sizes)[-2:] + 1))
eye_m = ndimage.binary_dilation(eye_m, iterations=6)
ys, xs = np.where(eye_m)
ex0, ey0, ex1, ey1 = xs.min(), ys.min(), xs.max() + 1, ys.max() + 1
rig["eyes"] = [int(ex0), int(ey0)]
fe = soft(eye_m, 3)
for name in ("eyes_half", "eyes_closed"):
    E = color_match(load(name), ring_of(eye_m))
    save(E[ey0:ey1, ex0:ex1], fe[ey0:ey1, ex0:ex1] * 255, name)
# iris layer (moves for glances) and empty eye whites under it
Ei = color_match(load("no_iris"), ring_of(eye_m))
iris_m = clean((diff(Ei) > 80) & eye_m, min_area=150, close=2, open_=1)
whites_m = ndimage.binary_dilation(iris_m, iterations=3) & eye_m
save(Ei[ey0:ey1, ex0:ex1], soft(whites_m, 1)[ey0:ey1, ex0:ex1] * 255, "eye_whites")
save(B[ey0:ey1, ex0:ex1, :3], soft(iris_m, 1)[ey0:ey1, ex0:ex1] * 255, "iris")
rig["whites_clip"] = "eye_whites"

# --- mouth ----------------------------------------------------------------------
mouth_box = (395, 560, 420, 640)
mouth_names = ["mouth_small", "mouth_i", "mouth_u", "mouth_e", "mouth_o"]
Es = {n: load(n) for n in mouth_names}
A_img = Image.open(mouth_a_p).convert("RGB")
if A_img.size != (W, H):
    A_img = A_img.resize((W, H), Image.LANCZOS)
Es["mouth_a"] = np.array(A_img).astype(np.float32)
ma = clean((diff(Es["mouth_a"]) > 70) & region(*mouth_box), min_area=60, close=3)
lab, n = ndimage.label(ma)
sizes = ndimage.sum(ma, lab, range(1, n + 1)); ma = lab == (np.argmax(sizes) + 1)
cy, cx = [int(v) for v in ndimage.center_of_mass(ma)]
yy, xx = np.mgrid[0:H, 0:W]
mm = ((xx - cx) / 68.0) ** 2 + ((yy - cy) / 50.0) ** 2 <= 1
ys, xs = np.where(mm)
mx0, my0, mx1, my1 = xs.min(), ys.min(), xs.max() + 1, ys.max() + 1
rig["mouth"] = [int(mx0), int(my0)]
fm = soft(mm, 3)
save(B[my0:my1, mx0:mx1, :3], fm[my0:my1, mx0:mx1] * 255, "mouth_closed")
for n, E in Es.items():
    E = color_match(E, ring_of(mm))
    save(E[my0:my1, mx0:mx1], fm[my0:my1, mx0:mx1] * 255, n)

# --- pivots (in image pixels) ---------------------------------------------------
fy = int(np.where(region(0, H, 0, W) & eye_m)[0].mean())
rig["neck"] = [W // 2, int(my1 + 70)]          # head rotates around the neck
rig["head_center"] = [W // 2, fy]
for k in ("bangs", "side", "ribbon", "back"):
    ys, xs = np.where(parts[k][0])
    rig[k + "_box"] = [int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())] if len(xs) else None
json.dump(rig, open(os.path.join(out, "rig.json"), "w"), indent=1)
print(json.dumps(rig))
