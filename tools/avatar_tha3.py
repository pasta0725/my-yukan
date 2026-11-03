"""Animate one anime character image so it talks to a WAV file, VTuber-like, on CPU.
Uses Talking Head Anime 3 (pkhungurn/talking-head-anime-3-demo); run with that repo as the
working directory (it needs its tha3 package and data/models/<mode>/).

usage: python3 tools/avatar_tha3.py <image.png 512x512 RGBA> <voice.wav> <out_dir> [fps] [mode]
writes <out_dir>/frames/%05d.png (RGBA) and prints timing.
Motion: mouth follows voice loudness, random blinks, eye glances, head/neck/body sway, breathing."""
import math, os, random, sys, time, wave
import numpy as np
import torch
from PIL import Image

sys.path.insert(0, os.getcwd())
from tha3.poser.modes.load_poser import load_poser  # noqa: E402
from tha3.util import extract_pytorch_image_from_PIL_image, convert_output_image_from_torch_to_numpy  # noqa: E402

img_path, wav_path, out = sys.argv[1], sys.argv[2], sys.argv[3]
fps = int(sys.argv[4]) if len(sys.argv) > 4 else 30
mode = sys.argv[5] if len(sys.argv) > 5 else "separable_float"
os.makedirs(f"{out}/frames", exist_ok=True)
torch.set_num_threads(os.cpu_count() or 2)
dev = torch.device("cpu")

poser = load_poser(mode, dev)
idx = {}
for g in poser.get_pose_parameter_groups():
    for k, name in enumerate(g.get_parameter_names()):
        idx[name] = g.get_parameter_index() + k
print("pose parameters:", sorted(idx), flush=True)

im = Image.open(img_path).convert("RGBA").resize((512, 512), Image.LANCZOS)
src = extract_pytorch_image_from_PIL_image(im).to(dev).to(poser.get_dtype())

# voice loudness per frame
w = wave.open(wav_path)
sr, n = w.getframerate(), w.getnframes()
pcm = np.frombuffer(w.readframes(n), dtype=np.int16).astype(np.float32)
if w.getnchannels() > 1:
    pcm = pcm.reshape(-1, w.getnchannels()).mean(axis=1)
dur = len(pcm) / sr
nf = int(dur * fps) + fps // 2  # small tail after the voice ends
hop = sr // fps
env = np.array([np.sqrt(np.mean(pcm[i * hop:(i + 1) * hop] ** 2)) if i * hop < len(pcm) else 0.0 for i in range(nf)])
env = env / (np.percentile(env[env > 0], 95) if (env > 0).any() else 1)
mouth = np.zeros(nf)
for i in range(nf):  # quick attack, slower release, like a real mouth
    target = min(1.0, max(0.0, (env[i] - 0.08) * 1.3))
    prev = mouth[i - 1] if i else 0
    mouth[i] = prev + (target - prev) * (0.7 if target > prev else 0.35)

rnd = random.Random(7)
blinks, t = [], rnd.uniform(1.0, 2.5)
while t < dur + 1:
    blinks.append(t); t += rnd.uniform(2.2, 4.8)
glances, t = [(0.0, 0.0, 0.0)], 0.0
while t < dur + 1:
    t += rnd.uniform(1.2, 2.8); glances.append((t, rnd.uniform(-0.5, 0.5), rnd.uniform(-0.25, 0.35)))


def set_(pose, name, v):
    if name in idx:
        pose[idx[name]] = v


def blink_amount(t):
    a = 0.0
    for b in blinks:
        d = t - b
        if 0 <= d < 0.18:
            a = max(a, math.sin(math.pi * d / 0.18))
    return a


def glance(t):
    cur = glances[0]
    for g in glances:
        if g[0] <= t:
            cur = g
    return cur[1], cur[2]


gx = gy = 0.0
t0 = time.time()
for i in range(nf):
    t = i / fps
    pose = torch.zeros(poser.get_num_parameters(), dtype=poser.get_dtype())
    talk = mouth[i]
    # head and body: slow, layered sines + a little nod while talking
    set_(pose, "head_x", 0.10 * math.sin(2 * math.pi * 0.23 * t) + 0.12 * talk * math.sin(2 * math.pi * 1.7 * t))
    set_(pose, "head_y", 0.18 * math.sin(2 * math.pi * 0.13 * t + 1.0))
    set_(pose, "neck_z", 0.12 * math.sin(2 * math.pi * 0.17 * t + 0.5))
    set_(pose, "body_y", 0.10 * math.sin(2 * math.pi * 0.11 * t + 2.0))
    set_(pose, "body_z", 0.06 * math.sin(2 * math.pi * 0.19 * t))
    set_(pose, "breathing", 0.5 + 0.5 * math.sin(2 * math.pi * 0.28 * t))
    # eyes: blinks, smooth glances, a soft smile
    b = blink_amount(t)
    set_(pose, "eye_wink_left", b); set_(pose, "eye_wink_right", b)
    tx, ty = glance(t); gx += (tx - gx) * 0.25; gy += (ty - gy) * 0.25
    set_(pose, "iris_rotation_y", gx); set_(pose, "iris_rotation_x", gy)
    set_(pose, "eyebrow_happy_left", 0.3); set_(pose, "eyebrow_happy_right", 0.3)
    set_(pose, "mouth_raised_corner_left", 0.25); set_(pose, "mouth_raised_corner_right", 0.25)
    # mouth: open with loudness, vary the vowel shape a little
    set_(pose, "mouth_aaa", talk * (0.75 + 0.25 * math.sin(2 * math.pi * 3.1 * t)))
    set_(pose, "mouth_ooo", talk * 0.25 * (0.5 + 0.5 * math.sin(2 * math.pi * 2.3 * t + 1)))
    with torch.no_grad():
        o = poser.pose(src, pose.unsqueeze(0).to(dev))[0].float()
    a = convert_output_image_from_torch_to_numpy(o)
    if a.dtype != np.uint8:
        a = (np.clip(a, 0, 1) * 255).astype(np.uint8)
    Image.fromarray(a, "RGBA").save(f"{out}/frames/{i:05d}.png")
    if i % 30 == 0:
        el = time.time() - t0
        print(f"frame {i}/{nf}  {el:.0f}s  {(i + 1) / max(el, 1e-6):.2f} fps", flush=True)
print(f"done {nf} frames in {time.time() - t0:.0f}s", flush=True)
