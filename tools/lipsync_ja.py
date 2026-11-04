"""Japanese lip sync: mouth shape and openness per video frame, from the narration text + its WAV.
Needs pyopenjtalk (reading of kanji). usage: python3 tools/lipsync_ja.py "<text>" <voice.wav> <out.js> [fps]
writes window.VOICE = {fps, dur, mouth: [[shape, open], ...]}  shape in a,i,u,e,o,small,closed"""
import json, sys, wave
import numpy as np
import pyopenjtalk

text, wav_p, out_p = sys.argv[1], sys.argv[2], sys.argv[3]
fps = int(sys.argv[4]) if len(sys.argv) > 4 else 30

# 1) morae from the text: (vowel, starts with lips closed?)
ph = pyopenjtalk.g2p(text).split()
morae, groups, cur, lips = [], [], [], False
for p in ph:
    if p == "pau":
        if cur: groups.append(cur); cur = []
        continue
    if p in ("a", "i", "u", "e", "o", "A", "I", "U", "E", "O"):
        weak = p.isupper()  # devoiced, barely voiced
        cur.append(("u" if weak else p.lower(), lips, 0.5 if weak else 1.0)); lips = False
    elif p in ("N", "cl"):
        cur.append(("small" if p == "N" else "closed", False, 0.6))
    else:
        lips = p in ("m", "b", "p", "my", "by", "py")
if cur: groups.append(cur)

# 2) voiced stretches in the audio (100 frames per second)
w = wave.open(wav_p); sr = w.getframerate(); n = w.getnframes()
x = np.frombuffer(w.readframes(n), dtype=np.int16).astype(float)
if w.getnchannels() > 1: x = x.reshape(-1, w.getnchannels()).mean(axis=1)
hop = sr // 100
env = np.array([np.sqrt(np.mean(x[i:i + hop] ** 2)) for i in range(0, len(x) - hop, hop)])
env = env / (np.percentile(env[env > 0], 95) + 1e-9)
voiced = env > 0.08
segs, i = [], 0
while i < len(voiced):
    if voiced[i]:
        j = i
        while j < len(voiced) and (voiced[j] or (j + 12 < len(voiced) and voiced[j:j + 12].any())):
            j += 1
        if j - i > 5: segs.append([i, j])
        i = j
    else:
        i += 1

# 3) put the morae on the voiced stretches (group by group when the pauses line up)
timeline = []  # (start_s, end_s, shape, lips, weight)
if len(segs) == len(groups):
    pairs = list(zip(segs, groups))
else:
    allm = [m for g in groups for m in g]
    total = sum(b - a for a, b in segs) or 1
    pairs, k = [], 0
    for a, b in segs:
        cnt = round(len(allm) * (b - a) / total) if (a, b) != tuple(segs[-1]) else len(allm) - k
        pairs.append(([a, b], allm[k:k + cnt])); k += cnt
for (a, b), ms in pairs:
    if not ms: continue
    wsum = sum(m[2] for m in ms); t = a / 100
    for shape, lp, wt in ms:
        d = (b - a) / 100 * wt / wsum
        timeline.append((t, t + d, shape, lp)); t += d

# 4) per video frame: shape + openness (opens fast, eases a little before the next mora)
dur = len(x) / sr + 0.3
frames = []
for f in range(int(dur * fps)):
    t = f / fps; val = ["closed", 0.0]
    for s, e, shape, lp in timeline:
        if s <= t < e:
            u = (t - s) / max(e - s, 1e-3)
            if lp and u < 0.25: val = ["closed", 0.0]; break
            op = min(1.0, u / 0.3) * (1 - 0.35 * max(0, (u - 0.6) / 0.4))
            if shape in ("small", "closed"): op *= 0.5
            val = [shape, round(op, 3)]; break
    frames.append(val)
env30 = [float(min(1, env[min(int(f / fps * 100), len(env) - 1)])) for f in range(len(frames))]
open(out_p, "w").write("window.VOICE=" + json.dumps({"fps": fps, "dur": dur, "mouth": frames, "env": env30}) + ";")
print("morae", sum(len(g) for g in groups), "groups", len(groups), "voiced stretches", len(segs))
