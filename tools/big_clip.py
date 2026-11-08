"""Frames of the big presenter (登場・結論) from a LongCat talking clip (tools/shorts_rules.md 「りなの動かし方」, 2026-11-09).
usage: python3 tools/big_clip.py <out_dir> <clip.mp4> [--switch <sec> <clip_b.mp4> <between1.png> <between2.png>]
writes <out_dir>/0000.png ... : 30 fps, 1080x1920 (the 720x1280 pose layout x1.5), transparent background (green keyed), frame k = clip time k/30 s.
The clip was made from the line's own finished audio, so its time = the line's time (no picking or re-ordering of frames).
--switch: from <sec> on use clip_b (e.g. the finger pose); the 0.2 s before it shows the two in-between drawings, 0.1 s each
(channel/rina_puppet/big_ib_*.png), so she moves into the pose instead of cutting."""
import glob, os, subprocess, sys, tempfile
import numpy as np
from PIL import Image
from scipy import ndimage

BW, BH, FPS = 720, 1280, 30


def frames(clip):
    d = tempfile.mkdtemp()
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", clip, "-vf", f"fps={FPS}", os.path.join(d, "%05d.png")], check=True)
    return sorted(glob.glob(os.path.join(d, "*.png")))


def unbox(a):  # cut black bars, back to the still's 720x1280 layout (green padding)
    dark = (a.sum(2) < 60).mean(1); rows = np.where(dark < 0.9)[0]; a = a[rows.min():rows.max() + 1]
    h, w = a.shape[:2]
    if abs(w / h - BW / BH) < 0.01: return np.array(Image.fromarray(a).resize((BW, BH), Image.LANCZOS))
    nh = round(h * BW / w); a = np.array(Image.fromarray(a).resize((BW, nh), Image.LANCZOS))
    c = np.zeros((BH, BW, 3), np.uint8); c[...] = (0, 255, 0); top = (BH - nh) // 2
    s0, d0 = max(0, -top), max(0, top); n = min(nh - s0, BH - d0); c[d0:d0 + n] = a[s0:s0 + n]; return c


UP = 1.5  # frames are made 1.5x larger (1080x1920) before keying: the page draws her 1.45-1.75x, and scaling a keyed
          # 720px picture up made the outline jagged (user, 2026-11-09)


def keyed(a):
    im = Image.fromarray(a).resize((round(BW * UP), round(BH * UP)), Image.LANCZOS)
    a = np.asarray(im).astype(np.float32); r, g, b = a[..., 0], a[..., 1], a[..., 2]; k = g - np.maximum(r, b)
    alpha = np.clip(1 - (k - 30) / 80, 0, 1)
    alpha = ndimage.gaussian_filter(alpha, 1.1)                       # soft, smooth outline
    alpha[alpha < 0.03] = 0
    g2 = np.minimum(g, np.maximum(r, b) + 4)                          # remove the green tint (rina has no green in her design)
    return Image.fromarray(np.clip(np.dstack([r, g2, b, alpha * 255]), 0, 255).astype(np.uint8), "RGBA")


def main():
    out, clip = sys.argv[1], sys.argv[2]
    os.makedirs(out, exist_ok=True)
    for f in glob.glob(os.path.join(out, "*.png")): os.remove(f)
    A = frames(clip); B = None
    if "--switch" in sys.argv:
        i = sys.argv.index("--switch"); sw = float(sys.argv[i + 1]); B = frames(sys.argv[i + 2]); ib = sys.argv[i + 3:i + 5]
    n = len(A)
    for k in range(n):
        t = k / FPS
        if B is None or t < sw - 0.2: im = keyed(unbox(np.array(Image.open(A[k]).convert("RGB"))))
        elif t < sw: im = Image.open(ib[0 if t < sw - 0.1 else 1]).convert("RGBA").resize((round(BW * UP), round(BH * UP)), Image.LANCZOS)
        else: im = keyed(unbox(np.array(Image.open(B[min(k, len(B) - 1)]).convert("RGB"))))
        im.save(os.path.join(out, f"{k:04d}.png"))
    print("frames", n, "->", out)


if __name__ == "__main__":
    main()
