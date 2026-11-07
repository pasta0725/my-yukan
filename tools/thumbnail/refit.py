"""refit a 9:16 thumbnail so eyes and title fit the Shorts window.
usage: refit.py in.png out.png eye_y title_bottom_y  (y on 1080x1920 scale)"""
import sys, numpy as np
from PIL import Image, ImageFilter
src, dst, ey, tb = sys.argv[1], sys.argv[2], float(sys.argv[3]), float(sys.argv[4])
W, H = 1080, 1920; E, T = 645, 1300
im = Image.open(src).convert("RGB").resize((W, H), Image.LANCZOS)
s = min(1.0, (T - E) / (tb - ey))
# keep eyes at E (or above-window margin) after scaling
oy = E - ey * s if s < 1 else min(0, T - tb) if tb > T else max(0, E - ey)
if s == 1 and tb > T: oy = T - tb
sw, sh = round(W * s), round(H * s); ox = (W - sw) // 2; oy = round(oy)
sm = np.asarray(im.resize((sw, sh), Image.LANCZOS))
top, left = max(0, oy), ox; bot = max(0, H - (oy + sh)); right = W - sw - ox
crop = sm[max(0, -oy): sh - max(0, oy + sh - H)]
pad = np.pad(crop, ((top, bot if oy + sh < H else 0), (left, right), (0, 0)), mode="reflect")[:H, :W]
canvas = Image.fromarray(pad)
blur = canvas.filter(ImageFilter.GaussianBlur(14))
mask = Image.new("L", (W, H), 255)
inner = Image.new("L", (sw, crop.shape[0]), 0)
mask.paste(inner, (left, top)); mask = mask.filter(ImageFilter.GaussianBlur(10))
out = Image.composite(blur, canvas, mask)
out.save(dst)
print(f"scale {s:.3f} shift {oy}  eyes->{ey*s+oy:.0f} title->{tb*s+oy:.0f}")
