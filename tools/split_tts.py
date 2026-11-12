"""Split narration made in groups (several lines in one TTS request, joined by newlines) back into one WAV per line.
Saves the daily TTS quota: 16 lines -> 4 requests.
usage: python3 tools/split_tts.py <lines.json of the groups> <dir with s1.wav..sN.wav of the groups> <out_dir>
writes out_dir/s1.wav ... one per line (numbered across all groups) and prints each length.
Cut points: the silent gaps nearest to where each line should end (by its share of the characters), longer gaps preferred.
Prints CHECK when a line is much slower/faster than the others or was cut at a very short pause (a cut in the wrong place;
listen to it / compare with the voice check). Exit code 3 if any CHECK (2026-11-12: groups grew to 6-8 lines)."""
import json, os, re, sys, wave
import numpy as np

cfg = json.load(open(sys.argv[1], encoding="utf-8")); src, out = sys.argv[2], sys.argv[3]
os.makedirs(out, exist_ok=True)


def readw(p):
    w = wave.open(p); sr = w.getframerate(); x = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)
    if w.getnchannels() == 2: x = x.reshape(-1, 2).mean(axis=1).astype(np.int16)
    return x, sr


n = bad = 0
for gi, group in enumerate(cfg["lines"], 1):
    lines = [l for l in group.split("\n") if l.strip()]
    x, sr = readw(os.path.join(src, f"s{gi}.wav"))
    win = int(sr * 0.01); m = len(x) // win
    db = 20 * np.log10(np.sqrt((x[: m * win].astype(np.float32) / 32768).reshape(m, win).__pow__(2).mean(1)) + 1e-9)
    quiet = db < -40
    gaps, i = [], 0
    while i < m:
        j = i
        while j < m and quiet[j] == quiet[i]: j += 1
        if quiet[i] and i > 0 and j < m and (j - i) >= 12: gaps.append((i, j))
        i = j
    w = [len(re.sub(r"[、。「」 \s]", "", l)) for l in lines]; tot = sum(w)
    voiced = np.where(~quiet)[0]; a0, a1 = voiced[0], voiced[-1]
    cuts, used = [], set()
    for k in range(1, len(lines)):
        want = a0 + (a1 - a0) * sum(w[:k]) / tot
        best = min((g for g in gaps if g not in used), key=lambda g: abs((g[0] + g[1]) / 2 - want) / 100 - (g[1] - g[0]) / 40)
        used.add(best); cuts.append((best[0] + best[1]) // 2)
    gap_of = {(g[0] + g[1]) // 2: g for g in used}
    cuts = sorted(cuts)
    bounds = [0] + [c * win for c in cuts] + [len(x)]
    rate = (a1 - a0) * win / sr / tot   # seconds per character in this group
    for k, l in enumerate(lines):
        n += 1; seg = x[bounds[k]:bounds[k + 1]]
        with wave.open(os.path.join(out, f"s{n}.wav"), "wb") as o:
            o.setnchannels(1); o.setsampwidth(2); o.setframerate(sr); o.writeframes(seg.tobytes())
        r = len(seg) / sr / max(w[k], 1) / rate
        note = []
        if w[k] >= 6 and not 0.6 < r < 1.7: note.append(f"speed x{r:.2f} vs the other lines")
        if k < len(cuts) and (gap_of[cuts[k]][1] - gap_of[cuts[k]][0]) < 15: note.append("cut at a short pause")
        if note: bad += 1
        print(f"s{n}.wav {len(seg) / sr:.2f}s  {l}" + ("   CHECK: " + ", ".join(note) if note else ""))
if bad: print(f"{bad} line(s) to check"); sys.exit(3)
