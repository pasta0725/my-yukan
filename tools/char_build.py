"""Presenter frames for a whole Short from two short LongCat clips (talk clip on base_green, finger-pose clip for the intro).
usage: python3 tools/char_build.py <plan.js> <talk.mp4> <fingers.mp4|-> <out_dir> [mouth_box] [fingers_offset_s] [speed]
1) the talk clip is un-letter-boxed to 720x1280 (like the still) and tools/char_track.py picks, for every frame of every
   "puppet" line, a clip frame whose mouth openness matches the narration (lip sync without a full-length clip).
2) intro line: from the comma on (「このニュース、」|「1分でまとめます」) the finger-pose clip is played instead, sampled at the
   narration speed, with a 0.25 s cross-fade (user, 2026-11-09: she moves into the finger pose as she says the number).
fingers_offset_s = seconds from the intro line's end back to where the fingers clip's audio starts (default 1.4)."""
import glob, json, os, subprocess, sys, tempfile
import numpy as np
from PIL import Image
from scipy import ndimage

plan_p, talk, fing, out = sys.argv[1:5]
mb = sys.argv[5] if len(sys.argv) > 5 else "325,285,425,355"
f_off = float(sys.argv[6]) if len(sys.argv) > 6 else 1.4
speed = float(sys.argv[7]) if len(sys.argv) > 7 else 1.15
BW, BH = 720, 1280
here = os.path.dirname(os.path.abspath(__file__))
txt = open(plan_p, encoding="utf-8").read(); P = json.loads(txt[txt.index("=") + 1:].rstrip(";\n ")); FPS = P["fps"]


def frames(clip):
    d = tempfile.mkdtemp(); subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", clip, os.path.join(d, "%04d.png")], check=True)
    fps = eval(subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v", "-show_entries", "stream=r_frame_rate", "-of", "csv=p=0", clip],
                              capture_output=True, text=True).stdout.strip())
    return sorted(glob.glob(os.path.join(d, "*.png"))), fps


def unbox(a):  # cut black bars, back to the still's 720x1280 layout (green padding)
    dark = (a.sum(2) < 60).mean(1); rows = np.where(dark < 0.9)[0]; a = a[rows.min():rows.max() + 1]
    h, w = a.shape[:2]
    if abs(w / h - BW / BH) < 0.01: return np.array(Image.fromarray(a).resize((BW, BH), Image.LANCZOS))
    nh = round(h * BW / w); a = np.array(Image.fromarray(a).resize((BW, nh), Image.LANCZOS))
    c = np.zeros((BH, BW, 3), np.uint8); c[...] = (0, 255, 0); top = (BH - nh) // 2
    s0, d0 = max(0, -top), max(0, top); n = min(nh - s0, BH - d0); c[d0:d0 + n] = a[s0:s0 + n]; return c


def keyed(a):
    a = a.astype(np.float32); r, g, b = a[..., 0], a[..., 1], a[..., 2]; k = g - np.maximum(r, b)
    alpha = np.clip(1 - (k - 35) / 70, 0, 1); near = ndimage.gaussian_filter(alpha, 2.5) < 0.995
    g2 = np.where(near, np.minimum(g, np.maximum(r, b)), g)
    return Image.fromarray(np.clip(np.dstack([r, g2, b, alpha * 255]), 0, 255).astype(np.uint8), "RGBA")


# 1) talk clip -> 720x1280 mp4 at its own fps (char_track assumes 24 fps)
src, fps = frames(talk)
tmpd = tempfile.mkdtemp()
for i, f in enumerate(src): Image.fromarray(unbox(np.array(Image.open(f).convert("RGB")))).save(os.path.join(tmpd, f"{i:04d}.png"))
norm = os.path.join(tmpd, "talk720.mp4")
subprocess.run(["ffmpeg", "-v", "error", "-y", "-framerate", "24", "-i", os.path.join(tmpd, "%04d.png"), "-c:v", "libx264", "-crf", "8", "-pix_fmt", "yuv444p", norm], check=True)
print("talk clip", len(src), "frames at", fps)
subprocess.run([sys.executable, os.path.join(here, "char_track.py"), norm, plan_p, out, mb, "0,255,0"], check=True)

# 2) intro: finger pose from the comma on
if fing != "-":
    li = next(i for i, l in enumerate(P["lines"]) if l["scene"] == "intro"); L = P["lines"][li]
    fsrc, ffps = frames(fing); t0 = L["end"] - f_off
    nxt = P["lines"][li + 1]["start"]; fade = 0.25
    k0, k1 = int(round((t0 - fade) * FPS)), int(round(nxt * FPS))
    for k in range(k0, k1):
        t = k / FPS; j = int(max(0, (t - t0)) * speed * ffps); j = min(max(j, 1), len(fsrc) - 1)
        im = keyed(unbox(np.array(Image.open(fsrc[j]).convert("RGB"))))
        a = min(1.0, max(0.0, (t - (t0 - fade)) / fade))
        p = os.path.join(out, f"f{k}.png")
        if a < 1 and os.path.exists(p): im = Image.blend(Image.open(p).convert("RGBA"), im, a)
        im.save(p)
    print("intro finger pose frames", k0, "-", k1)
# the logo card and the first frames: hold the nearest frame so every output frame exists
N = int(round(P["T"] * FPS)); have = sorted(int(os.path.basename(f)[1:-4]) for f in glob.glob(os.path.join(out, "f*.png")))
for k in range(N + 1):
    p = os.path.join(out, f"f{k}.png")
    if not os.path.exists(p):
        near = min(have, key=lambda h: abs(h - k)); os.link(os.path.join(out, f"f{near}.png"), p)
print("frames", N + 1)
